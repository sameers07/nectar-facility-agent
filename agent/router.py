import json
import logging
import os
import time

from agent.errors import LLMProviderError, RoutingError
from agent.llm_client import build_client
from agent.state import Session

logger = logging.getLogger("router")

# Constrained rather than free text: an LLM inventing new labels
# ("equipment_diagnosis_request") each call would be unreliable to branch
# on downstream. "unknown" is the deliberate escape hatch for anything
# that doesn't fit -- paired with a low confidence, it's what drives
# clarification instead of a forced, wrong guess.
INTENTS = [
    "knowledge_question",
    "live_status",
    "diagnosis",
    "action_request",
    "data_summary",
    "general_conversation",
    "unknown",
]

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
                    "enum": INTENTS,
                    "description": "What kind of request this is.",
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

Intents:
- knowledge_question: asking what something is or how it works (-> rag).
- live_status: asking for a current live value (-> live_data).
- diagnosis: asking *why* something is happening (-> live_data + rag).
- action_request: asking to change facility state (-> action).
- data_summary: asking to summarize data over a period (-> live_data).
- general_conversation: not about the facility at all.
- unknown: anything ambiguous -- pair this with low confidence.

Set "complexity" to "high" when the request needs reasoning across
multiple sources (e.g. diagnosing *why* something happened), and "low" for
a direct lookup or simple fact. If the request is ambiguous, missing a
required detail (e.g. which building), or you're otherwise unsure what it
needs, still call `route` but give it a confidence below 0.6 instead of
guessing.
"""


REQUIRED_CONTRACT_FIELDS = ("intent", "sources", "action_required", "complexity", "confidence")


class Router:
    def __init__(self, client=None, model: str = None):
        self.client = client or build_client()
        self.model = model or ROUTER_MODEL
        self.last_latency_ms = None
        self.last_usage = None

    def route(self, user_message: str, session: Session) -> dict:
        """Returns a routing contract, or raises LLMProviderError (the API
        call itself failed) / RoutingError (it responded but not with a
        valid contract) -- kept distinct so Orchestrator can give the user
        a different message for "try again" vs. "rephrase that"."""
        messages = (
            [{"role": "system", "content": ROUTER_PROMPT}]
            + session.conversation
            + [{"role": "user", "content": user_message}]
        )
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[ROUTE_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "route"}},
            )
        except Exception as e:
            logger.exception("Router LLM call failed")
            raise LLMProviderError(str(e)) from e
        self.last_latency_ms = (time.perf_counter() - start) * 1000
        self.last_usage = getattr(response, "usage", None)

        try:
            tool_call = response.choices[0].message.tool_calls[0]
            contract = json.loads(tool_call.function.arguments)
            missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in contract]
            if missing:
                raise ValueError(f"missing fields: {missing}")
        except (IndexError, AttributeError, TypeError, ValueError) as e:
            logger.exception("Router returned an invalid contract")
            raise RoutingError(str(e)) from e

        logger.info(
            "ROUTE: %s (latency_ms=%.0f, tokens=%s)",
            contract,
            self.last_latency_ms,
            getattr(self.last_usage, "total_tokens", None),
        )
        return contract
