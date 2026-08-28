import json
import logging
import os

from agent.llm_client import build_client
from agent.prompts import SYSTEM_PROMPT
from agent.state import Session
from tools.registry import TOOL_SCHEMAS, call_tool

MODEL = os.environ.get("GEMINI_MODEL", os.environ.get("OPENAI_MODEL", "gemini-2.5-flash"))
MAX_TOOL_ITERATIONS = 8

logger = logging.getLogger("investigator")

CONCLUDE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_conclusion",
        "description": (
            "Submit the final answer once enough evidence has been gathered, "
            "or once the available tools cannot answer the question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "conclusion": {"type": "string", "description": "The final answer for the user."},
                "confidence": {"type": "number", "description": "0 to 1."},
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Observed facts that support the conclusion.",
                },
            },
            "required": ["conclusion", "confidence", "evidence"],
        },
    },
}


class Investigator:
    def __init__(self, client=None, model: str = None):
        self.client = client or build_client()
        self.model = model or MODEL

    def investigate(self, user_message: str, session: Session) -> dict:
        logger.info("USER: %s", user_message)
        session.conversation.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.conversation
        tools = TOOL_SCHEMAS + [CONCLUDE_TOOL_SCHEMA]
        evidence_log = []

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, tools=tools, tool_choice="auto"
                )
            except Exception:
                logger.exception("LLM call failed during investigation")
                return {
                    "conclusion": "I ran into a technical error while investigating. Please try again.",
                    "confidence": 0.0,
                    "evidence": [e["result"] for e in evidence_log],
                }
            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                session.conversation.append({"role": "assistant", "content": message.content})
                return {"conclusion": message.content, "confidence": None, "evidence": evidence_log}

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if name == "submit_conclusion":
                    logger.info(
                        "REASONING: %s (confidence %.2f)", args["conclusion"], args["confidence"]
                    )
                    session.investigation = args
                    session.conversation.append({"role": "assistant", "content": args["conclusion"]})
                    return args

                logger.info("TOOL -> %s(%s)", name, args)
                result = call_tool(name, args)
                logger.info("TOOL <- %s", result)
                evidence_log.append({"tool": name, "arguments": args, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

        return {
            "conclusion": "Investigation did not reach a conclusion within the allowed steps.",
            "confidence": 0.0,
            "evidence": [e["result"] for e in evidence_log],
        }
