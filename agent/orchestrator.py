import logging

from agent.investigator import Investigator
from agent.router import CAPABILITIES, CONFIDENCE_THRESHOLD, FAST_MODEL, STRONG_MODEL, Router
from agent.state import Session

logger = logging.getLogger("orchestrator")


def _say(session: Session, user_message: str, reply: str) -> dict:
    session.conversation.append({"role": "user", "content": user_message})
    session.conversation.append({"role": "assistant", "content": reply})
    return {"conclusion": reply, "confidence": None, "evidence": []}


class Orchestrator:
    """Routes a request to the capabilities it needs before handing off to
    Task 1's Investigator (unchanged) for anything that touches live_data.
    "rag" and "action" are placeholders until Tasks 3/4 build the real
    knowledge base and MCP action layer -- this proves routing decisions
    are correct without pretending those capabilities exist yet.
    """

    def __init__(self, router: Router = None, investigator_factory=None):
        self.router = router or Router()
        self.investigator_factory = investigator_factory or (lambda model: Investigator(model=model))

    def handle(self, user_message: str, session: Session) -> dict:
        contract = self.router.route(user_message, session)

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

        if "live_data" in contract["sources"]:
            model = STRONG_MODEL if contract["complexity"] == "high" else FAST_MODEL
            logger.info("Delegating to Investigator with model=%s", model)
            investigator = self.investigator_factory(model)
            return investigator.investigate(user_message, session)

        if "rag" in contract["sources"]:
            return _say(
                session,
                user_message,
                "I'd answer that from the facility knowledge base, but that capability isn't built yet.",
            )

        return _say(session, user_message, "I'm not sure how to help with that yet.")
