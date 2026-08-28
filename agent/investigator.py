import json
import logging
import os

from agent.llm_client import build_client
from agent.prompts import SYSTEM_PROMPT
from agent.state import Session
from tools.mcp_tools import MCP_TOOL_SCHEMAS, call_mcp_tool

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
    def __init__(
        self,
        client=None,
        model: str = None,
        tool_schemas: list = None,
        tool_dispatch=None,
        extra_tool_schemas: list = None,
        extra_tool_dispatch: dict = None,
    ):
        self.client = client or build_client()
        self.model = model or MODEL
        # base facility tools: real MCP by default. Tests inject a fast fake
        # here so the loop-mechanics tests don't pay for a subprocess.
        base_schemas = MCP_TOOL_SCHEMAS if tool_schemas is None else tool_schemas
        self.tool_dispatch = tool_dispatch or call_mcp_tool
        self.tool_schemas = base_schemas + (extra_tool_schemas or [])
        self.extra_tool_dispatch = extra_tool_dispatch or {}

    def investigate(self, user_message: str, session: Session) -> dict:
        logger.info("USER: %s", user_message)
        session.conversation.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.conversation
        tools = self.tool_schemas + [CONCLUDE_TOOL_SCHEMA]
        evidence_log = []

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, tools=tools, tool_choice="required"
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

                if name == "propose_action":
                    logger.info("PROPOSED ACTION: %s", args)
                    session.conversation.append({"role": "assistant", "content": args["confirmation_prompt"]})
                    return {
                        "conclusion": args["confirmation_prompt"],
                        "confidence": args.get("confidence"),
                        "evidence": args.get("evidence", []),
                        "pending_action": args,
                    }

                logger.info("TOOL -> %s(%s)", name, args)
                if name in self.extra_tool_dispatch:
                    result = self.extra_tool_dispatch[name](**args)
                else:
                    result = self.tool_dispatch(name, args)
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
