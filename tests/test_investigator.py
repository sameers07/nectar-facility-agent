import json
from types import SimpleNamespace

from agent.investigator import Investigator
from agent.state import Session


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _response(tool_calls=None, content=None):
    message = SimpleNamespace(tool_calls=tool_calls, content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ScriptedClient:
    """Fake OpenAI client that replays a fixed sequence of responses."""

    def __init__(self, responses):
        self._responses = iter(responses)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return next(self._responses)


def test_multi_step_investigation_reaches_conclusion():
    responses = [
        _response(tool_calls=[_tool_call("1", "get_building_temperature", {"building": "Building A"})]),
        _response(tool_calls=[_tool_call("2", "get_hvac_assets", {"building": "Building A"})]),
        _response(tool_calls=[_tool_call("3", "get_asset_status", {"asset": "AHU-02"})]),
        _response(tool_calls=[_tool_call("4", "get_active_alerts", {"building": "Building A"})]),
        _response(
            tool_calls=[
                _tool_call(
                    "5",
                    "submit_conclusion",
                    {
                        "conclusion": "AHU-02 low airflow is the likely cause.",
                        "confidence": 0.91,
                        "evidence": ["Building A is at 28.4C", "AHU-02 airflow is 41%"],
                    },
                )
            ]
        ),
    ]
    investigator = Investigator(client=ScriptedClient(responses))
    session = Session()

    result = investigator.investigate("The temperature in Building A is too high.", session)

    assert result["confidence"] == 0.91
    assert "AHU-02" in result["conclusion"]
    assert session.investigation == result


def test_insufficient_data_does_not_hallucinate():
    responses = [
        _response(
            tool_calls=[
                _tool_call(
                    "1",
                    "submit_conclusion",
                    {
                        "conclusion": "I don't have sufficient facility data to determine the cause of the vibration.",
                        "confidence": 0.1,
                        "evidence": [],
                    },
                )
            ]
        )
    ]
    investigator = Investigator(client=ScriptedClient(responses))
    session = Session()

    result = investigator.investigate("Why is Building A experiencing unusual vibration?", session)

    assert result["confidence"] < 0.5
    assert "sufficient" in result["conclusion"].lower()


def test_iteration_limit_returns_fallback():
    responses = [
        _response(tool_calls=[_tool_call(str(i), "get_building_temperature", {"building": "Building A"})])
        for i in range(20)
    ]
    investigator = Investigator(client=ScriptedClient(responses))
    session = Session()

    result = investigator.investigate("Why is Building A hot?", session)

    assert result["confidence"] == 0.0
    assert "did not reach a conclusion" in result["conclusion"]
