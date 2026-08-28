"""Runs the 6 Task 2 routing scenarios against a REAL LLM and reports what
the router decided. Unlike scripts/eval_scenarios.py, this can't be proven
with a scripted client -- classifying natural language into capabilities is
exactly the behavior under test, so mocking the LLM would just be checking
against my own scripted answer. Requires GEMINI_API_KEY/OPENAI_API_KEY.
"""
import os
import sys

from dotenv import load_dotenv

from agent.router import Router
from agent.state import Session

load_dotenv()

RESET, GREEN, RED, YELLOW = "\033[0m", "\033[32m", "\033[31m", "\033[33m"

SCENARIOS = [
    ("What is an AHU?", lambda c: "rag" in c["sources"] and c["complexity"] == "low" and c["confidence"] >= 0.6),
    (
        "What is Chiller-01's current temperature?",
        lambda c: "live_data" in c["sources"] and c["complexity"] == "low" and c["confidence"] >= 0.6,
    ),
    (
        "Why did Chiller-01 fail?",
        lambda c: "live_data" in c["sources"] and "rag" in c["sources"] and c["complexity"] == "high",
    ),
    (
        "Create a maintenance request for AHU-02.",
        lambda c: c["action_required"] or "action" in c["sources"],
    ),
    ("Something is wrong.", lambda c: c["confidence"] < 0.6),
    (
        "What's the current energy consumption?",
        lambda c: "energy" in c["sources"],
    ),
]


def main():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("GEMINI_API_KEY is not set -- this script needs a real LLM to evaluate routing decisions.")
        return 1

    router = Router()
    all_passed = True

    for question, check in SCENARIOS:
        contract = router.route(question, Session())
        passed = check(contract)
        all_passed &= passed
        mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f'{mark}  "{question}"')
        print(
            f"      intent={contract['intent']!r} sources={contract['sources']} "
            f"complexity={contract['complexity']} confidence={contract['confidence']:.2f}"
        )

    print()
    print("All scenarios passed." if all_passed else "Some scenarios failed.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
