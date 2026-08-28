# Nectar Autonomous Facility Agent

Voice-driven AI agent for facility operations: it investigates reported
problems, answers questions from facility documentation, checks live
building/HVAC data, and creates maintenance requests — autonomously
deciding what it needs at each step, never guessing when it doesn't know,
and never taking a write action without your explicit confirmation.

See also: [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) (concise summary),
[docs/mcp_api.md](docs/mcp_api.md) (MCP tool reference), [evaluation/](evaluation/) (results + raw traces).

## 1. Problem

A facility manager shouldn't have to know which system holds which piece
of information. "The office on the second floor feels hot, do we need
maintenance?" should not require manually checking a temperature sensor,
then an HVAC asset list, then an alert log, then a troubleshooting manual,
then filing a ticket by hand. That's five different lookups across (in a
real deployment) five different systems, and a facility manager doing
this by voice while walking a building doesn't have a keyboard for any of
them.

## 2. Solution

One voice-driven agent that decides for itself what a request needs —
live data, documentation, an action, or some combination — gathers that
evidence autonomously through tool calls, reasons over it, and only ever
takes a state-changing action after you've explicitly said yes.

```
"The office on the second floor of Building A feels very hot.
 Can you investigate and let me know if we need maintenance?"
        |
        v
[reads Building A's temperature, checks HVAC relationships, checks
 AHU-02's status, checks active alerts -- 6 autonomous tool calls,
 no hardcoded sequence]
        |
        v
"The office on the second floor of Building A is hot because AHU-02,
 which serves that floor, is operating with low airflow. There is a
 high-severity alert for this issue, so maintenance is likely needed."
 (confidence 100%)
```

Full raw trace: [evaluation/sample_traces/full_autonomous_scenario.txt](evaluation/sample_traces/full_autonomous_scenario.txt)

## 3. Architecture

Built incrementally, one capability at a time, into a single system —
not five separate demos glued together at the end.

```
                              USER
                               |
                               v
                          MICROPHONE
                               |
                               v
                     Whisper (local STT)
                               |
                               v
                          ┌─────────┐
                          │ ROUTER  │  one structured-output LLM call:
                          └────┬────┘  intent, sources, complexity, confidence
                               |
                       REQUEST CONTRACT
                               |
                 confidence < 0.6 ──────────► "Could you clarify...?"
                 source unavailable ────────► "I can't access X right now."
                               |
                               v
                      ┌─────────────────┐
                      │   INVESTIGATOR  │  tool-calling loop (Task 1, unchanged)
                      └────────┬────────┘
                               |
             ┌─────────────────┼─────────────────┐
             v                 v                  v
       RAG TOOL           MCP CLIENT          SESSION
    (retrieve_facility_  (call_mcp_tool)     (conversation
        docs)                 |               history +
             |                v               pending_action)
             |          ┌────────────┐
             |          │ MCP SERVER │  real stdio subprocess,
             |          └─────┬──────┘  8 tools, owns facility.json
             |                |
        local vector    get_asset_details / get_asset_status /
        store (numpy,   get_sensor_data / get_energy_consumption /
        sentence-        get_active_alerts / get_asset_relationships /
        transformers)    create_service_request / update_service_request
             |                |
             └────────┬───────┘
                       v
                   EVIDENCE
                       |
                       v
                   REASONING
                       |
              ┌────────┴────────┐
              v                 v
          submit_conclusion  propose_action
              |                 |
              |            SAFETY GATE
              |          (session.pending_action,
              |           deterministic yes/no
              |           classifier -- no LLM)
              |                 |
              |            user says "yes"
              |                 |
              |                 v
              |            MCP CLIENT
              |                 |
              |                 v
              |          create_service_request()
              |                 |
              |            request_id (e.g. SR-1001)
              |                 |
              └────────┬────────┘
                       v
              pyttsx3 (local TTS)
                       |
                       v
                     USER
```

Code map:

| Layer | File |
|---|---|
| Voice I/O | `voice/stt.py`, `voice/tts.py` |
| Session loop | `agent/voice_agent.py` |
| Routing | `agent/router.py` |
| Orchestration | `agent/orchestrator.py` |
| Investigation | `agent/investigator.py` |
| Safety gate | `agent/action_gate.py` |
| RAG | `rag/loader.py`, `rag/store.py`, `tools/rag_tool.py`, `knowledge/*.md` |
| MCP server | `mcp_server/server.py`, `mcp_server/service_requests.py` |
| MCP client | `mcp_client/client.py` |
| Facility data | `data/facility.json`, `tools/facility_tools.py` |
| Session state | `agent/state.py` |

## 4. Autonomous Investigation

`agent/investigator.py`'s loop is Task 1's original design, unchanged
through every later task: understand the question, decide what evidence
is needed, call a tool, evaluate the result, decide whether more is
needed, repeat, then call `submit_conclusion` with an answer, a
confidence score, and the supporting evidence — or `propose_action` if a
write is warranted. `tool_choice="required"` forces a tool call every
turn (including the terminal ones), so the model can't silently reply
with free text instead of finishing the loop properly.

No step in the sequence is hardcoded. The same investigator produces a
1-tool trace for "What's Chiller-01's status?" and a 6-tool trace for the
full autonomous scenario above, purely because the model decided it
needed more evidence in the second case.

## 5. LLM Routing

`agent/router.py`'s `Router` makes one structured-output call (forced
tool call, so the output shape is schema-enforced, not parsed from free
text) that classifies a request into a contract:

```json
{
  "intent": "diagnosis",
  "sources": ["live_data", "rag"],
  "action_required": false,
  "complexity": "high",
  "confidence": 0.94
}
```

`intent` is a constrained enum (`knowledge_question`, `live_status`,
`diagnosis`, `action_request`, `data_summary`, `general_conversation`,
`unknown`) rather than free text, so downstream code branches on a fixed
set instead of whatever label the model happens to invent that call.
`agent/orchestrator.py` then decides what to do with the contract:

- **Ambiguous** (`confidence < 0.6`) -> ask for clarification, never guess.
- **Unavailable capability** (checked against `CAPABILITIES` in
  `agent/router.py`) -> decline that part explicitly.
- **Complexity** picks the investigation model: `gemini-2.5-flash` for
  low, `gemini-2.5-pro` for high. The router itself always uses the fast
  model, independent of the target complexity — classification should
  always be cheap regardless of how hard the downstream work is.
- Anything requiring `live_data` or `rag` -> delegates to the
  Investigator, attaching the RAG/action tools only when the contract
  says they're needed.

Live evaluation: **15/15 (100%)** across 6 categories, ~1.9s average
routing latency. Full table: [evaluation/routing_results.md](evaluation/routing_results.md).

## 6. RAG

Deliberately not a separate "RAG agent" pipeline. Retrieval is exposed as
one more tool (`retrieve_facility_docs`) in the *same* investigation loop
Task 1 already has, so the model can interleave live-data calls and
documentation lookups within one continuous reasoning chain — check an
alert, then look up what that alert code means, then conclude — instead
of stitching together two disconnected subsystems' outputs afterward.

```
knowledge/*.md  -->  rag/loader.py        -->  rag/store.py
(8 docs,             (chunk by each doc's      (embed locally with
 written to           own "## " sections,       sentence-transformers,
 reference the        not a fixed char           store as a numpy
 same mock            window)                     array, retrieve by
 entities as                                       cosine similarity,
 facility.json)                                    filter below a
                                                     0.35 score threshold)
```

A full ANN index (FAISS/Chroma) would be solving a problem this dataset
doesn't have — a few dozen chunks don't need one; exact cosine similarity
over a numpy array is just as correct and adds no infrastructure.

Retrieved passages are cited by source/heading in the same `evidence`
list the Investigator already produces for live-data facts — no separate
citation mechanism. "Not found" handling is the same "never invent, say
so with low confidence" system-prompt instruction that already governs
live-data gaps, not new logic.

Tested and live-verified: grounded answer with citation, and a genuinely
unsupported question ("What is the recommended lubricant viscosity for
Chiller-01's compressor?") correctly refused rather than hallucinated,
even retrying with a rephrased query first. Details:
[evaluation/rag_results.md](evaluation/rag_results.md).

## 7. MCP

Facility reads and writes go through a real MCP server over stdio, not a
direct Python function call. `tools/facility_tools.py` still exists, but
only `mcp_server/server.py` calls it — the Investigator's default tool
source is `tools/mcp_tools.py`, which only talks to the facility through
`mcp_client/client.py`.

```
mcp_server/server.py     8 tools (mcp.server.mcpserver.MCPServer, stdio transport):
                           get_asset_details, get_asset_status, get_sensor_data,
                           get_energy_consumption, get_active_alerts,
                           get_asset_relationships, create_service_request,
                           update_service_request

mcp_client/client.py     Synchronous wrapper around the SDK's async client --
                          a background thread owns one persistent event loop
                          and one long-lived coroutine holding the connection
                          open for its lifetime (anyio's cancel scopes require
                          entering/exiting a task group in the same task, so a
                          fresh coroutine per call doesn't work).
```

`tests/test_mcp_integration.py` runs 13 tests against a real subprocess,
deliberately not mocked — that's exactly the boundary that needs to be a
genuine protocol, not a decorative wrapper, to actually satisfy the
requirement. Full tool-by-tool results: [evaluation/mcp_results.md](evaluation/mcp_results.md).
API reference for all 8 tools: [docs/mcp_api.md](docs/mcp_api.md).

## 8. Safety & Confirmation

The Investigator can never execute a write directly. It can only call
`propose_action` (`agent/action_gate.py`) — a terminal tool alongside
`submit_conclusion`, handled the same way in the investigation loop —
which stores the proposed action in `session.pending_action` and asks the
user to confirm. Nothing is created yet.

`Orchestrator.handle()` checks `session.pending_action` *before* routing
on every subsequent turn:

- A clear **"yes"** executes the MCP write using the exact details
  captured at proposal time (never re-derived from the LLM on the
  confirmation turn, so they can't drift between proposal and execution).
- A clear **"no"** cancels — no MCP call happens.
- Anything else drops the stale proposal and routes the message as a
  normal new request, so an old proposal can't be accidentally confirmed
  by an unrelated later "yes".

`classify_confirmation()` is a small regex, deliberately not an LLM call
— a gate on a write action needs predictable yes/no/neither, not a
best-effort classification.

Verified live: confirm -> real `create_service_request` call -> `SR-1001`
returned; reject -> zero MCP writes; "yes" with no pending action ->
routes normally instead of guessing at a request to create. Raw traces in
[evaluation/sample_traces/](evaluation/sample_traces/).

## 9. Conversation Memory

`agent/state.py`'s `Session` holds `conversation` (full history across
turns), `investigation` (last conclusion), and `pending_action`. Each
`Investigator.investigate()` call sends `[system prompt] + session.conversation`,
so follow-ups resolve against prior turns — "what about the chiller?"
after a Building A investigation correctly infers you mean Building A's
chiller, without re-stating it.

Within a single investigation, the tool-call/result exchange stays local
to that call; only the final conclusion is appended back into session
history, so multi-step tool chatter doesn't compound the token cost of
every future turn — only the final answer does.

## 10. Failure Handling

Every external boundary degrades to a clear spoken message, never a
traceback:

| Failure | Where | Result |
|---|---|---|
| LLM API call fails (router) | `agent/router.py` | `LLMProviderError` -> "having trouble processing your request, please try again" |
| LLM returns a malformed/missing contract | `agent/router.py` | `RoutingError` -> "couldn't be safely classified, could you rephrase?" |
| LLM API call fails (investigation) | `agent/investigator.py` | "ran into a technical error... please try again" |
| MCP server unreachable | `mcp_client/client.py`, `tools/mcp_tools.py` | `{"error": ...}` tool result -> model explains it can't access the facility system |
| Invalid tool arguments | MCP SDK's own pydantic validation | clean `{"error": ...}`, no crash |
| Unknown asset/building name | `tools/facility_tools.py`'s formatting-tolerant lookup | `{"error": "Unknown asset: ..."}`, model asks the user to confirm |
| Unavailable capability (routed but not implemented) | `agent/orchestrator.py`'s `CAPABILITIES` check | explicit decline, never silently ignored |
| Ambiguous/low-confidence request | `agent/router.py` confidence gate | clarifying question, not a guess |

A genuine transient Gemini 503 was hit live during acceptance testing and
handled exactly as designed — see [evaluation/e2e_results.md](evaluation/e2e_results.md).

## 11. Setup

```bash
uv sync
cp .env.example .env  # fill in GEMINI_API_KEY
```

## 12. Environment Variables

Only `GEMINI_API_KEY` is required — STT and TTS both run locally. See
`.env.example` for the full list of optional overrides (alternate models
per complexity tier, Whisper model size, microphone device override).

## 13. Running the Agent

```bash
uv run app.py            # text mode
uv run app.py --voice    # microphone in, spoken response out
```

Voice mode records until you pause rather than a fixed duration, and
biases Whisper toward the facility's own vocabulary (building/asset
names) so codes like "AHU-02" transcribe correctly. If it reports no
audio detected, your system's default input device may be wrong:

```bash
AUDIO_INPUT_DEVICE=MacBook uv run app.py --voice   # matches by device name substring
```

and check System Settings -> Privacy & Security -> Microphone if that
doesn't help.

## 14. Evaluation

```bash
uv run pytest                          # 57 tests, ~10s (13 of these spawn a real MCP subprocess)
uv run python -m scripts.eval_scenarios   # Task 1 loop mechanics, scripted LLM, no API key needed
uv run python -m scripts.eval_routing     # Task 2 router, REAL LLM required, 15 scenarios
```

Full results and raw traces: [evaluation/](evaluation/) —
`routing_results.md`, `rag_results.md`, `mcp_results.md`, `e2e_results.md`,
`sample_traces/`.

## 15. Sample Conversations

See [evaluation/sample_traces/full_autonomous_scenario.txt](evaluation/sample_traces/full_autonomous_scenario.txt)
(the full investigate-then-confirm-then-create flow) and
[evaluation/sample_traces/safety_gate_reject.txt](evaluation/sample_traces/safety_gate_reject.txt)
(the rejection path) for complete raw logs, and `evaluation/e2e_results.md`
for eight more scenarios covering RAG, live data, combined reasoning,
unsupported questions, and failure injection.

## 16. Design Decisions

- **Investigator-centric, not a five-agent system.** Router, RAG, and MCP
  are all capabilities the one Investigator can draw on, not separate
  agents with their own orchestration.
- **RAG is a tool, not an agent.** Lets the model interleave live-data and
  documentation lookups in one reasoning chain instead of merging two
  pipelines' outputs after the fact.
- **MCP as a tool boundary, not an "MCP agent".** The Investigator remains
  the reasoning engine; MCP is how it reaches the facility.
- **LLM produces a contract; Python validates and executes it.**
  Deterministic dispatch on a structured decision is not "hard-coded
  routing" — the judgment (what does this need) is the LLM's; the
  execution (do exactly that, safely) is ordinary code.
- **Confirmation uses a regex, not an LLM call.** A safety gate needs
  predictable yes/no/neither, not a best-effort classification.
- **Right-sized infrastructure.** Local embeddings instead of an
  embeddings API, plain numpy instead of a vector database, a background
  event loop thread instead of rewriting the Investigator as async —
  each chosen because the simpler option is still correct at this scale,
  not as a shortcut.

## 17. Limitations

- Mock facility data covers 2 buildings, 5 assets, floors 0-2 — a
  floor-only reference beyond that range won't resolve (correctly asks
  for clarification instead of guessing; see the third-floor test in
  `evaluation/e2e_results.md`).
- `update_service_request` exists and is tested at the MCP layer but
  isn't exercised by the headline demo scenario (which creates, not
  updates, a request).
- No document-versioning/conflict resolution in RAG (e.g. two docs giving
  different instructions for the same procedure) — out of scope for this
  corpus size, not attempted.
- Service requests are in-memory per MCP server process, not persisted to
  disk — acceptable for a prototype, would need a real store in
  production.
- LLM investigation depth shows some run-to-run variance (documented
  honestly in `evaluation/e2e_results.md` rather than hidden) — inherent
  to LLM sampling, not something a retry-once fix fully eliminates.

## 18. Future Improvements

- Persist service requests and session history across restarts.
- Hybrid (semantic + keyword) retrieval to reduce sensitivity to how a
  query is phrased.
- Structured cost/latency telemetry aggregated across a session, not just
  per-call (`Router.last_latency_ms`/`last_usage` already exist per-call).
- Multi-turn action editing (e.g. "actually make that medium priority"
  before confirming) rather than confirm-as-proposed-or-cancel.
