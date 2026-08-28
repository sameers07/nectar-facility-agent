from agent.investigator import Investigator
from agent.voice_agent import VoiceAgent
from tests.support import ScriptedClient, llm_response, tool_call


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
    agent = VoiceAgent(voice=False, investigator=investigator)

    monkeypatch.setattr("builtins.input", lambda prompt="": "What is the temperature in Building A?")
    keep_going = agent.step()

    assert keep_going is True
    assert len(agent.session.conversation) == 2
    assert "28.4C" in capsys.readouterr().out


def test_step_returns_false_on_keyboard_interrupt(monkeypatch):
    investigator = Investigator(client=ScriptedClient([]))
    agent = VoiceAgent(voice=False, investigator=investigator)

    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    assert agent.step() is False


def test_step_skips_empty_input(monkeypatch):
    investigator = Investigator(client=ScriptedClient([]))
    agent = VoiceAgent(voice=False, investigator=investigator)

    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    keep_going = agent.step()

    assert keep_going is True
    assert agent.session.conversation == []
