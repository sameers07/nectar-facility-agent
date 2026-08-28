import logging

from agent.errors import LLMProviderError, RoutingError
from agent.investigator import Investigator
from agent.router import CAPABILITIES, CONFIDENCE_THRESHOLD, FAST_MODEL, STRONG_MODEL, Router
from agent.state import Session
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
    or rag -- rag is exposed as one more tool in the SAME investigation
    loop rather than a separate pipeline, so the model can interleave live
    lookups and documentation retrieval within one continuous reasoning
    chain (e.g. check an alert, then look up what that alert code means).
    "action" is still a placeholder until Task 4 builds the real MCP layer.
    """

    def __init__(self, router: Router = None, investigator_factory=None):
        self.router = router or Router()
        self.investigator_factory = investigator_factory or _default_investigator_factory

    def handle(self, user_message: str, session: Session) -> dict:
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

        if contract["action_required"] or "action" in contract["sources"]:
            return _say(
                session,
                user_message,
                "I'd create that action through the facility's live systems, but that capability isn't built yet.",
            )

        needs_rag = "rag" in contract["sources"]
        needs_live_data = "live_data" in contract["sources"]

        if needs_live_data or needs_rag:
            model = STRONG_MODEL if contract["complexity"] == "high" else FAST_MODEL
            logger.info("Delegating to Investigator with model=%s, rag=%s", model, needs_rag)
            extra_schemas = [RAG_TOOL_SCHEMA] if needs_rag else None
            extra_dispatch = {"retrieve_facility_docs": retrieve_facility_docs} if needs_rag else None
            investigator = self.investigator_factory(model, extra_schemas, extra_dispatch)
            return investigator.investigate(user_message, session)

        return _say(session, user_message, "I'm not sure how to help with that yet.")
