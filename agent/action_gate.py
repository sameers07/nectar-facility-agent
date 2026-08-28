"""Safety gate for write actions. The LLM can PROPOSE a service request via
propose_action, but that only records session.pending_action and asks the
user to confirm -- the actual MCP write call happens exactly once, in
Orchestrator, only after the user's *next* turn is classified as a clear
"yes", using the details already stored (not re-derived from the LLM, so
it can't drift between proposal and execution).
"""
import re

PROPOSE_ACTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_action",
        "description": (
            "Propose creating or updating a facility service request once you've "
            "identified a fault that needs maintenance. This does NOT create the "
            "request -- the user must explicitly confirm on their next turn first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_service_request", "update_service_request"]},
                "asset_id": {"type": "string"},
                "request_id": {
                    "type": "string",
                    "description": "Existing request ID, required when action is update_service_request.",
                },
                "issue": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "description": {"type": "string"},
                "status": {
                    "type": "string",
                    "description": "New status, required when action is update_service_request (e.g. 'in_progress', 'resolved').",
                },
                "confirmation_prompt": {
                    "type": "string",
                    "description": (
                        "Natural-language question asking the user to confirm, e.g. "
                        "'I found a likely AHU-02 airflow issue. Would you like me to "
                        "create a maintenance request?'"
                    ),
                },
                "confidence": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "action",
                "asset_id",
                "issue",
                "priority",
                "description",
                "confirmation_prompt",
                "confidence",
                "evidence",
            ],
        },
    },
}

_YES = re.compile(r"^\s*(yes|yeah|yep|sure|confirm(ed)?|go ahead|do it|okay|ok|please do)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|nah|don'?t|cancel|never ?mind|stop)\b", re.I)


def classify_confirmation(message: str) -> str:
    """'yes', 'no', or 'unrelated'. Deliberately simple/deterministic (no
    LLM call) rather than fuzzy -- this gates a write action, so an
    ambiguous reply must default to NOT executing anything, not to a
    best-effort guess."""
    if _YES.match(message):
        return "yes"
    if _NO.match(message):
        return "no"
    return "unrelated"
