from agent.investigator import Investigator
from agent.orchestrator import Orchestrator
from agent.voice_agent import VoiceAgent
from tests.support import ScriptedClient, llm_response, tool_call


class FixedRouter:
    def __init__(self, contract=None, on_route=None):
        self.contract = contract
        self.on_route = on_route

    def route(self, user_message, session):
        if self.on_route:
            return self.on_route(user_message, session)
        return self.contract


def _never_called_router():
    def on_route(user_message, session):
        raise AssertionError("router should not be called")

    return FixedRouter(on_route=on_route)


def test_step_updates_session_across_turns(monkeypatch, capsys):
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_building_temperature", {"building": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {"conclusion": "Building A is at 28.4C.", "confidence": 0.9, "evidence": ["28.4C"]},
                )
            ]
        ),
    ]
    investigator = Investigator(client=ScriptedClient(responses))
    contract = {
        "intent": "live_status",
        "sources": ["live_data"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.95,
    }
    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=lambda model: investigator)
    agent = VoiceAgent(voice=False, orchestrator=orchestrator)

    monkeypatch.setattr("builtins.input", lambda prompt="": "What is the temperature in Building A?")
    keep_going = agent.step()

    assert keep_going is True
    assert len(agent.session.conversation) == 2
    assert "28.4C" in capsys.readouterr().out


def test_step_returns_false_on_keyboard_interrupt(monkeypatch):
    orchestrator = Orchestrator(router=_never_called_router())
    agent = VoiceAgent(voice=False, orchestrator=orchestrator)

    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    assert agent.step() is False


def test_step_skips_empty_input(monkeypatch):
    orchestrator = Orchestrator(router=_never_called_router())
    agent = VoiceAgent(voice=False, orchestrator=orchestrator)

    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    keep_going = agent.step()

    assert keep_going is True
    assert agent.session.conversation == []


class ExplodingOrchestrator:
    def handle(self, user_message, session):
        raise RuntimeError("simulated unexpected failure")


def test_step_survives_an_unexpected_orchestrator_error(monkeypatch, capsys):
    agent = VoiceAgent(voice=False, orchestrator=ExplodingOrchestrator())

    monkeypatch.setattr("builtins.input", lambda prompt="": "What is the temperature in Building A?")
    keep_going = agent.step()

    assert keep_going is True
    assert "went wrong" in capsys.readouterr().out
