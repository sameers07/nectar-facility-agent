"""Runs a routing evaluation set against a REAL LLM and reports accuracy
plus per-call latency/token cost. Unlike scripts/eval_scenarios.py, this
can't be proven with a scripted client -- classifying natural language into
capabilities is exactly the behavior under test, so mocking the LLM would
just be checking against my own scripted answer. Requires
GEMINI_API_KEY/OPENAI_API_KEY.
"""
import os

from dotenv import load_dotenv

from agent.router import Router
from agent.state import Session

load_dotenv()

RESET, GREEN, RED = "\033[0m", "\033[32m", "\033[31m"

# (category, question, check) -- check receives the parsed contract dict.
SCENARIOS = [
    # A. Knowledge / RAG
    ("RAG", "What is an AHU?", lambda c: c["sources"] == ["rag"]),
    ("RAG", "How does a chiller work?", lambda c: "rag" in c["sources"]),
    ("RAG", "What does low airflow mean?", lambda c: "rag" in c["sources"]),
    # B. Live data
    ("Live data", "What is Chiller-01's current temperature?", lambda c: "live_data" in c["sources"]),
    ("Live data", "Is AHU-02 running?", lambda c: "live_data" in c["sources"]),
    ("Live data", "What is Building A's temperature?", lambda c: "live_data" in c["sources"]),
    # C. Combined (diagnosis)
    ("Combined", "Why is Chiller-01 failing?", lambda c: "live_data" in c["sources"] and "rag" in c["sources"]),
    ("Combined", "Why is Building A overheating?", lambda c: "live_data" in c["sources"] and "rag" in c["sources"]),
    ("Combined", "What's causing the AHU problem?", lambda c: "live_data" in c["sources"] and "rag" in c["sources"]),
    # D. Action
    ("Action", "Create a maintenance request for AHU-02.", lambda c: c["action_required"] or "action" in c["sources"]),
    ("Action", "Open a service request for Chiller-01.", lambda c: c["action_required"] or "action" in c["sources"]),
    # E. Ambiguous -- should be low confidence, not a guess
    ("Ambiguous", "Something is wrong.", lambda c: c["confidence"] < 0.6),
    ("Ambiguous", "Can you check it?", lambda c: c["confidence"] < 0.6),
    ("Ambiguous", "What's happening?", lambda c: c["confidence"] < 0.6),
    # F. Unavailable capability (still correctly routed -- Orchestrator declines it downstream)
    (
        "Unavailable",
        "Can you show me the camera feed for the loading dock?",
        lambda c: "video_surveillance" in c["sources"],
    ),
]


def main():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("GEMINI_API_KEY is not set -- this script needs a real LLM to evaluate routing decisions.")
        return 1

    router = Router()
    results = []

    for category, question, check in SCENARIOS:
        contract = router.route(question, Session())
        passed = check(contract)
        tokens = getattr(router.last_usage, "total_tokens", None)
        results.append((category, question, passed, contract, router.last_latency_ms, tokens))

    name_width = max(len(q) for _, q, *_ in results)
    print(f"{'Category':<11} {'Query':<{name_width}}  {'Latency':>8}  {'Tokens':>7}  Result")
    print("-" * (11 + name_width + 35))
    for category, question, passed, contract, latency_ms, tokens in results:
        mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"{category:<11} {question:<{name_width}}  {latency_ms:>6.0f}ms  {str(tokens):>7}  {mark}")
        print(
            f"{'':<{11 + name_width}}    intent={contract['intent']!r} sources={contract['sources']} "
            f"complexity={contract['complexity']} confidence={contract['confidence']:.2f}"
        )

    correct = sum(1 for r in results if r[2])
    total = len(results)
    accuracy = correct / total
    avg_latency = sum(r[4] for r in results) / total

    print()
    print(f"Routing accuracy: {correct}/{total} ({accuracy:.0%})")
    print(f"Average latency: {avg_latency:.0f}ms")
    print("Meets >=90% accuracy target." if accuracy >= 0.9 else "Below 90% accuracy target.")
    return 0 if accuracy >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
