import json
import logging
import os

from agent.llm_client import build_client
from agent.state import Session

logger = logging.getLogger("router")

# What this system can actually back today. "rag" and "action" have
# placeholder handlers (Tasks 3/4 build the real thing); "energy" is
# deliberately False to prove unavailable capabilities are handled instead
# of hallucinated.
CAPABILITIES = {
    "rag": True,
    "live_data": True,
    "action": True,
    "energy": False,
}

CONFIDENCE_THRESHOLD = 0.6

ROUTER_MODEL = os.environ.get("GEMINI_ROUTER_MODEL", "gemini-2.5-flash")
FAST_MODEL = os.environ.get("GEMINI_MODEL", os.environ.get("OPENAI_MODEL", "gemini-2.5-flash"))
STRONG_MODEL = os.environ.get("GEMINI_STRONG_MODEL", "gemini-2.5-pro")

ROUTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "route",
        "description": "Classify what capabilities are needed to handle the user's request.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Short label, e.g. 'knowledge_question', 'live_status', 'diagnosis', 'action_request', 'unknown'.",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(CAPABILITIES.keys())},
                    "description": "Capabilities needed to answer the request.",
                },
                "action_required": {
                    "type": "boolean",
                    "description": "True if the request asks to change facility state (e.g. create a maintenance request).",
                },
                "complexity": {
                    "type": "string",
                    "enum": ["low", "high"],
                    "description": "'high' if it needs reasoning across multiple sources (e.g. diagnosing why), 'low' for a direct lookup.",
                },
                "confidence": {
                    "type": "number",
                    "description": "0 to 1, how confident you are in this classification.",
                },
            },
            "required": ["intent", "sources", "action_required", "complexity", "confidence"],
        },
    },
}

ROUTER_PROMPT = """You are the request router for a facility operations assistant.

Given the user's message and the conversation so far, classify what the
request needs by calling `route`. Do not answer the request yourself.

Capabilities:
- rag: facility documentation and general knowledge (e.g. "what is an AHU?").
- live_data: live building/HVAC data (temperature, asset status, alerts).
- action: taking an action in the facility (e.g. creating a maintenance request).
- energy: live energy consumption data.

Set "complexity" to "high" when the request needs reasoning across
multiple sources (e.g. diagnosing *why* something happened), and "low" for
a direct lookup or simple fact. If the request is ambiguous, missing a
required detail (e.g. which building), or you're otherwise unsure what it
needs, still call `route` but give it a confidence below 0.6 instead of
guessing.
"""


class Router:
    def __init__(self, client=None, model: str = None):
        self.client = client or build_client()
        self.model = model or ROUTER_MODEL

    def route(self, user_message: str, session: Session) -> dict:
        messages = (
            [{"role": "system", "content": ROUTER_PROMPT}]
            + session.conversation
            + [{"role": "user", "content": user_message}]
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[ROUTE_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "route"}},
            )
            tool_call = response.choices[0].message.tool_calls[0]
            contract = json.loads(tool_call.function.arguments)
        except Exception:
            # A failed/malformed routing call shouldn't crash the app -- a
            # confidence of 0 naturally routes into Orchestrator's existing
            # low-confidence clarification path.
            logger.exception("Routing call failed, falling back to clarification")
            contract = {
                "intent": "unknown",
                "sources": [],
                "action_required": False,
                "complexity": "low",
                "confidence": 0.0,
            }
        logger.info("ROUTE: %s", contract)
        return contract
