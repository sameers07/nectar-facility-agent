"""Automated pass/fail report for the 5 Task 1 review scenarios.

Runs the investigator loop against a scripted (offline, no API key) LLM to
prove the tool-dispatch, evidence, confidence, and session-memory mechanics
work deterministically. This does NOT prove the model autonomously chooses
its own tool sequence against a real LLM -- for that, run `app.py` with
OPENAI_API_KEY set and inspect the TOOL/REASONING log lines it prints.
"""
from agent.investigator import Investigator
from agent.state import Session
from tests.support import ScriptedClient, llm_response, tool_call

RESET, GREEN, RED = "\033[0m", "\033[32m", "\033[31m"


def scenario_basic_query():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_building_temperature", {"building": "Building A"})]),
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
    investigator = Investigator(client=ScriptedClient(responses))
    result = investigator.investigate("What is the temperature in Building A?", Session())
    return "28.4" in result["conclusion"], result["conclusion"]


def scenario_autonomous_investigation():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_building_temperature", {"building": "Building A"})]),
        llm_response(tool_calls=[tool_call("2", "get_hvac_assets", {"building": "Building A"})]),
        llm_response(tool_calls=[tool_call("3", "get_asset_status", {"asset": "AHU-02"})]),
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
    investigator = Investigator(client=ScriptedClient(responses))
    result = investigator.investigate("The temperature in Building A is too high, what's happening?", Session())
    return result["confidence"] > 0.8 and "AHU-02" in result["conclusion"], result["conclusion"]


def scenario_specific_asset():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_asset_status", {"asset": "AHU-02"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {
                        "conclusion": "AHU-02 is in a warning state with low airflow.",
                        "confidence": 0.85,
                        "evidence": ["AHU-02 airflow is 41%"],
                    },
                )
            ]
        ),
    ]
    investigator = Investigator(client=ScriptedClient(responses))
    result = investigator.investigate("Can you check AHU-02?", Session())
    return "AHU-02" in result["conclusion"], result["conclusion"]


def scenario_follow_up_context():
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_building_temperature", {"building": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {"conclusion": "Building A is at 28.4C.", "confidence": 0.7, "evidence": []},
                )
            ]
        ),
        llm_response(
            tool_calls=[
                tool_call(
                    "3",
                    "submit_conclusion",
                    {"conclusion": "Chiller-01 has an 18% power deviation.", "confidence": 0.6, "evidence": []},
                )
            ]
        ),
    ]
    client = ScriptedClient(responses)
    investigator = Investigator(client=client)
    session = Session()
    investigator.investigate("Why is Building A hot?", session)
    investigator.investigate("What about the chiller?", session)
    messages = client.calls[-1]["messages"]
    carried_context = any(m.get("content") == "Why is Building A hot?" for m in messages if isinstance(m, dict))
    return carried_context, "prior turn present in follow-up call" if carried_context else "context lost"


def scenario_unknown_information():
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
    investigator = Investigator(client=ScriptedClient(responses))
    result = investigator.investigate("Why is Building A experiencing unusual vibration?", Session())
    return result["confidence"] < 0.5 and "sufficient" in result["conclusion"].lower(), result["conclusion"]


SCENARIOS = [
    ("Temperature query", "Correct temperature returned", scenario_basic_query),
    ("Autonomous HVAC investigation", "Finds AHU-02 with high confidence", scenario_autonomous_investigation),
    ("Specific asset investigation", "Investigates AHU-02 directly", scenario_specific_asset),
    ("Follow-up question", "Maintains prior conversation context", scenario_follow_up_context),
    ("Unknown information", "No hallucination, low confidence", scenario_unknown_information),
]


def main():
    print(__doc__.strip().splitlines()[0])
    print()
    name_width = max(len(name) for name, _, _ in SCENARIOS)
    header = f"{'Test Case':<{name_width}}  {'Expected':<40}  Pass"
    print(header)
    print("-" * len(header))

    all_passed = True
    for name, expected, run in SCENARIOS:
        passed, actual = run()
        all_passed &= passed
        mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"{name:<{name_width}}  {expected:<40}  {mark}")
        print(f"{'':<{name_width}}  -> {actual}")

    print()
    print("All scenarios passed." if all_passed else "Some scenarios failed.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
