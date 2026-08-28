import logging

from agent.action_gate import PROPOSE_ACTION_SCHEMA, classify_confirmation
from agent.errors import LLMProviderError, RoutingError
from agent.investigator import Investigator
from agent.router import CAPABILITIES, CONFIDENCE_THRESHOLD, FAST_MODEL, STRONG_MODEL, Router
from agent.state import Session
from tools.mcp_tools import call_mcp_tool
from tools.rag_tool import RAG_TOOL_SCHEMA, retrieve_facility_docs

logger = logging.getLogger("orchestrator")


def _say(session: Session, user_message: str, reply: str) -> dict:
    session.conversation.append({"role": "user", "content": user_message})
    session.conversation.append({"role": "assistant", "content": reply})
    return {"conclusion": reply, "confidence": None, "evidence": []}


def _default_investigator_factory(model, extra_tool_schemas=None, extra_tool_dispatch=None):
    return Investigator(model=model, extra_tool_schemas=extra_tool_schemas, extra_tool_dispatch=extra_tool_dispatch)


class Orchestrator:
    """Routes a request to the capabilities it needs before handing off to
    Task 1's Investigator (unchanged) for anything that touches live_data
    or rag -- both are exposed as tools in the SAME investigation loop
    rather than separate pipelines, so the model can interleave live
    lookups and documentation retrieval within one continuous reasoning
    chain (e.g. check an alert, then look up what that alert code means).

    Write actions never execute directly from a single turn: the
    Investigator can only PROPOSE one (propose_action), which is stored as
    session.pending_action and surfaced as a question. The actual MCP
    write call only happens if the user's next turn is unambiguously "yes"
    -- see handle()'s pending-action check, which runs before routing.
    """

    def __init__(self, router: Router = None, investigator_factory=None):
        self.router = router or Router()
        self.investigator_factory = investigator_factory or _default_investigator_factory

    def handle(self, user_message: str, session: Session) -> dict:
        if session.pending_action is not None:
            return self._handle_pending_action(user_message, session)

        try:
            contract = self.router.route(user_message, session)
        except LLMProviderError:
            return _say(session, user_message, "I'm having trouble processing your request right now. Please try again.")
        except RoutingError:
            return _say(session, user_message, "Your request couldn't be safely classified. Could you rephrase it?")

        if contract["confidence"] < CONFIDENCE_THRESHOLD:
            return _say(session, user_message, "Could you clarify what you'd like me to look into?")

        missing = [s for s in contract["sources"] if not CAPABILITIES.get(s, False)]
        if missing:
            return _say(
                session,
                user_message,
                f"I can't access {', '.join(missing)} right now, so I'm not able to help with that part of the request.",
            )

        needs_rag = "rag" in contract["sources"]
        needs_action = contract["action_required"] or "action" in contract["sources"]
        needs_live_data = "live_data" in contract["sources"]

        if needs_action or needs_live_data or needs_rag:
            model = STRONG_MODEL if contract["complexity"] == "high" else FAST_MODEL
            logger.info("Delegating to Investigator with model=%s, rag=%s, action=%s", model, needs_rag, needs_action)
            extra_schemas = []
            extra_dispatch = {}
            if needs_rag:
                extra_schemas.append(RAG_TOOL_SCHEMA)
                extra_dispatch["retrieve_facility_docs"] = retrieve_facility_docs
            if needs_action:
                extra_schemas.append(PROPOSE_ACTION_SCHEMA)
            investigator = self.investigator_factory(model, extra_schemas, extra_dispatch)
            result = investigator.investigate(user_message, session)
            if result.get("pending_action"):
                session.pending_action = result["pending_action"]
            return result

        return _say(session, user_message, "I'm not sure how to help with that yet.")

    def _handle_pending_action(self, user_message: str, session: Session) -> dict:
        decision = classify_confirmation(user_message)

        if decision == "unrelated":
            # don't let a stale proposal linger and get accidentally
            # confirmed by an unrelated later "yes" -- drop it and treat
            # this turn as a normal new request instead.
            session.pending_action = None
            return self.handle(user_message, session)

        action = session.pending_action
        session.pending_action = None

        if decision == "no":
            return _say(session, user_message, "No problem, I won't create that request.")

        if action["action"] == "create_service_request":
            mcp_args = {
                "asset_id": action["asset_id"],
                "issue": action["issue"],
                "priority": action["priority"],
                "description": action["description"],
            }
        else:
            mcp_args = {"request_id": action["request_id"], "status": action["status"]}

        result = call_mcp_tool(action["action"], mcp_args)

        if "error" in result:
            return _say(session, user_message, f"I couldn't do that: {result['error']}")

        if action["action"] == "create_service_request":
            reply = f"Done -- created service request {result['request_id']} for {action['asset_id']}."
        else:
            reply = f"Done -- updated {result['request_id']} to {result['status']}."
        return _say(session, user_message, reply)
