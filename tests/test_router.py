from agent.router import Router
from agent.state import Session
from tests.support import ScriptedClient, llm_response, tool_call


def _route_response(contract):
    return llm_response(tool_calls=[tool_call("1", "route", contract)])


def test_route_parses_forced_tool_call():
    contract = {
        "intent": "knowledge_question",
        "sources": ["rag"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.98,
    }
    client = ScriptedClient([_route_response(contract)])
    router = Router(client=client)

    result = router.route("What is an AHU?", Session())

    assert result == contract


def test_route_sees_prior_conversation():
    contract = {
        "intent": "live_status",
        "sources": ["live_data"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.9,
    }
    client = ScriptedClient([_route_response(contract)])
    router = Router(client=client)
    session = Session()
    session.conversation.append({"role": "user", "content": "Why is Building A hot?"})
    session.conversation.append({"role": "assistant", "content": "Building A is at 28.4C."})

    router.route("What about the chiller?", session)

    sent_messages = client.calls[-1]["messages"]
    contents = [m["content"] for m in sent_messages if isinstance(m, dict)]
    assert "Why is Building A hot?" in contents
    assert "What about the chiller?" in contents
