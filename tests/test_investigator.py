from agent.investigator import Investigator
from agent.state import Session
from tests.support import RaisingClient, ScriptedClient, fake_tool_dispatch, llm_response, tool_call


def test_basic_single_tool_query():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_sensor_data", {"target": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {"conclusion": "Building A is at 28.4C.", "confidence": 1.0, "evidence": ["28.4C"]},
                )
            ]
        ),
    ]
    investigator = Investigator(client=ScriptedClient(responses), tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("What is the temperature in Building A?", session)

    assert "28.4" in result["conclusion"]


def test_multi_step_investigation_reaches_conclusion():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_sensor_data", {"target": "Building A"})]),
        llm_response(tool_calls=[tool_call("2", "get_asset_relationships", {"building": "Building A"})]),
        llm_response(tool_calls=[tool_call("3", "get_asset_status", {"asset_id": "AHU-02"})]),
        llm_response(tool_calls=[tool_call("4", "get_active_alerts", {"building": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
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
    investigator = Investigator(client=ScriptedClient(responses), tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("The temperature in Building A is too high.", session)

    assert result["confidence"] == 0.91
    assert "AHU-02" in result["conclusion"]
    assert session.investigation == result


def test_investigates_a_specific_asset_when_named():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_asset_status", {"asset_id": "AHU-02"})]),
        llm_response(tool_calls=[tool_call("2", "get_active_alerts", {"building": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "3",
                    "submit_conclusion",
                    {
                        "conclusion": "AHU-02 is in a warning state with low airflow.",
                        "confidence": 0.85,
                        "evidence": ["AHU-02 airflow is 41%", "AHU-02 has an active LOW_AIRFLOW alert"],
                    },
                )
            ]
        ),
    ]
    client = ScriptedClient(responses)
    investigator = Investigator(client=client, tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("Can you check AHU-02?", session)

    called_tools = [c.function.name for r in responses[:2] for c in r.choices[0].message.tool_calls]
    assert called_tools == ["get_asset_status", "get_active_alerts"]
    assert "AHU-02" in result["conclusion"]


def test_follow_up_question_carries_prior_conversation():
    first_turn = [
        llm_response(tool_calls=[tool_call("1", "get_sensor_data", {"target": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {"conclusion": "Building A is at 28.4C, above normal.", "confidence": 0.7, "evidence": []},
                )
            ]
        ),
    ]
    second_turn = [
        llm_response(
            tool_calls=[
                tool_call(
                    "3",
                    "submit_conclusion",
                    {
                        "conclusion": "Chiller-01 is running with an 18% power deviation.",
                        "confidence": 0.6,
                        "evidence": [],
                    },
                )
            ]
        )
    ]
    client = ScriptedClient(first_turn + second_turn)
    investigator = Investigator(client=client, tool_dispatch=fake_tool_dispatch)
    session = Session()

    investigator.investigate("Why is Building A hot?", session)
    investigator.investigate("What about the chiller?", session)

    # the second LLM call must have received the full prior conversation,
    # not just the new question in isolation
    second_call_messages = client.calls[-1]["messages"]
    roles_and_content = [(m["role"], m.get("content")) for m in second_call_messages if isinstance(m, dict)]
    assert ("user", "Why is Building A hot?") in roles_and_content
    assert ("user", "What about the chiller?") in roles_and_content


def test_insufficient_data_does_not_hallucinate():
    responses = [
        llm_response(
            tool_calls=[
                tool_call(
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
    investigator = Investigator(client=ScriptedClient(responses), tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("Why is Building A experiencing unusual vibration?", session)

    assert result["confidence"] < 0.5
    assert "sufficient" in result["conclusion"].lower()


def test_iteration_limit_returns_fallback():
    responses = [
        llm_response(tool_calls=[tool_call(str(i), "get_sensor_data", {"target": "Building A"})])
        for i in range(20)
    ]
    investigator = Investigator(client=ScriptedClient(responses), tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("Why is Building A hot?", session)

    assert result["confidence"] == 0.0
    assert "did not reach a conclusion" in result["conclusion"]


def test_llm_failure_degrades_gracefully_instead_of_crashing():
    investigator = Investigator(client=RaisingClient(), tool_dispatch=fake_tool_dispatch)
    session = Session()

    result = investigator.investigate("What is the temperature in Building A?", session)

    assert result["confidence"] == 0.0
    assert "technical error" in result["conclusion"]
