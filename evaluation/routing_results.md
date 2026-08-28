# Routing Evaluation (Task 2)

Live run against `gemini-2.5-flash`, `uv run python -m scripts.eval_routing`.

## Result: 15/15 (100%), average latency 1897ms

| Category | Query | intent | sources | complexity | confidence | Result |
|---|---|---|---|---|---|---|
| RAG | What is an AHU? | knowledge_question | [rag] | low | 1.00 | PASS |
| RAG | How does a chiller work? | knowledge_question | [rag] | low | 1.00 | PASS |
| RAG | What does low airflow mean? | knowledge_question | [rag] | low | 1.00 | PASS |
| Live data | What is Chiller-01's current temperature? | live_status | [live_data] | low | 1.00 | PASS |
| Live data | Is AHU-02 running? | live_status | [live_data] | low | 1.00 | PASS |
| Live data | What is Building A's temperature? | live_status | [live_data] | low | 1.00 | PASS |
| Combined | Why is Chiller-01 failing? | diagnosis | [live_data, rag] | high | 1.00 | PASS |
| Combined | Why is Building A overheating? | diagnosis | [live_data, rag] | high | 1.00 | PASS |
| Combined | What's causing the AHU problem? | diagnosis | [live_data, rag] | high | 1.00 | PASS |
| Action | Create a maintenance request for AHU-02. | action_request | [action] | low | 1.00 | PASS |
| Action | Open a service request for Chiller-01. | action_request | [action] | low | 1.00 | PASS |
| Ambiguous | Something is wrong. | unknown | [] | low | 0.30 | PASS |
| Ambiguous | Can you check it? | unknown | [] | low | 0.30 | PASS |
| Ambiguous | What's happening? | unknown | [] | low | 0.30 | PASS |
| Unavailable capability | What's the current energy consumption? | live_status | [energy] | low | 1.00 | PASS |

Ambiguous requests correctly scored below `CONFIDENCE_THRESHOLD = 0.6`, which
routes to a clarification response rather than a guess (see
`agent/orchestrator.py`).

## Cost/latency design

- Router always uses the fast model (`gemini-2.5-flash`) regardless of the
  target complexity — classification itself should always be cheap.
- The *investigation* that follows uses `gemini-2.5-flash` for low
  complexity and `gemini-2.5-pro` for high complexity (confirmed live in
  `e2e_results.md` — Test D used `gemini-2.5-pro`).
- Per-call latency and token usage are captured on `Router.last_latency_ms`
  / `Router.last_usage` for every routing decision.

## Live E2E routing decisions (fresh acceptance run, see `e2e_results.md`)

```
"What should I check if AHU airflow is low?"
  -> intent=knowledge_question sources=[rag] complexity=low confidence=1.0

"What's Chiller-01's current status?"
  -> intent=live_status sources=[live_data] complexity=low confidence=1.0

"Why did Chiller-01 fail?"
  -> intent=diagnosis sources=[live_data, rag] complexity=high confidence=1.0

"Create a maintenance request for AHU-02."
  -> intent=action_request sources=[action] complexity=low confidence=1.0

"The office on the second floor of Building A feels very hot..."
  -> intent=diagnosis sources=[live_data] complexity=high confidence=1.0
```
