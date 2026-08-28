# Nectar Facility Agent

Voice-driven facility operations agent, built up task by task.

```
User voice -> Whisper (local STT) -> Router -> Orchestrator -> Investigator (LLM + tool calling) -> local TTS -> User
```

The only external API is the LLM (Gemini, via its OpenAI-compatible
endpoint). STT and TTS both run locally, so no ElevenLabs/Deepgram key is
required.

## Architecture

### Task 1 — voice-driven investigation

- `data/facility.json` — mock facility data (buildings, HVAC assets, alerts).
- `tools/facility_tools.py` — four read-only functions over the mock data:
  `get_building_temperature`, `get_hvac_assets`, `get_asset_status`,
  `get_active_alerts`. The LLM never touches the JSON directly.
- `tools/registry.py` — OpenAI function-calling schemas for those tools plus
  a dispatcher.
- `agent/investigator.py` — the investigation loop: understand the question,
  decide what evidence is needed, call a tool, evaluate, repeat until there's
  enough evidence, then call `submit_conclusion` with an answer, confidence
  score, and supporting evidence. Never invents data — if the tools can't
  answer the question, it says so with low confidence instead of guessing.
- `agent/state.py` — per-session `Session` (conversation history +
  investigation state) so follow-up questions resolve against the prior
  investigation.
- `agent/prompts.py` — the system prompt that makes the LLM investigate
  rather than answer immediately.
- `voice/stt.py` — local Whisper transcription (from the microphone, biased
  toward the facility's own vocabulary so asset codes transcribe correctly).
- `voice/tts.py` — local text-to-speech via `pyttsx3`.

### Task 2 — LLM routing & orchestration

Before the investigator runs, a router decides *what the request needs*
rather than picking one fixed agent:

- `agent/router.py` — `Router` makes one structured-output LLM call
  (forced tool call, so the shape is schema-enforced, not parsed from free
  text) that classifies a request into a contract: `intent` (a constrained
  enum — `INTENTS` — not free text, so downstream code branches on a fixed
  set rather than whatever label the model invents), `sources` (`rag` /
  `live_data` / `action` / `energy`), `action_required`, `complexity`,
  `confidence`. `CAPABILITIES` marks which sources actually exist today —
  `energy` is deliberately `False` to prove unavailable capabilities are
  declined instead of hallucinated. Also records `last_latency_ms` and
  `last_usage` (token counts) per call for cost/latency visibility.
- `agent/orchestrator.py` — `Orchestrator` takes that contract and decides
  what to do: below `CONFIDENCE_THRESHOLD` it asks for clarification
  instead of guessing; if a required source is unavailable it says so; for
  `live_data` it delegates to Task 1's `Investigator` unchanged, picking a
  fast or strong model based on `complexity`; `rag`/`action` currently
  return a placeholder reply (Tasks 3/4 build the real knowledge base and
  MCP action layer) so routing correctness is provable before those exist.
- `agent/errors.py` — `LLMProviderError` (the API call itself failed) vs.
  `RoutingError` (it responded but not with a valid contract) are kept
  distinct so `Orchestrator` gives a different message for each ("try
  again" vs. "could you rephrase that") instead of one generic fallback.
- `agent/llm_client.py` — shared client construction (API key + base URL)
  used by both `Investigator` and `Router`.
- `agent/voice_agent.py` — `VoiceAgent` ties the `Orchestrator`, session,
  and I/O (text or voice) together into one runnable loop; `app.py` is a
  thin CLI wrapper around it. `step()` has a final catch-all so an
  unexpected error degrades to a message instead of crashing the loop.

## Setup

```bash
uv sync
cp .env.example .env  # fill in GEMINI_API_KEY
```

## Run

```bash
uv run app.py            # text mode
uv run app.py --voice    # microphone in, spoken response out
```

Voice mode records until you pause rather than a fixed duration, and biases
Whisper toward the facility's own vocabulary (building/asset names) so codes
like "AHU-02" transcribe correctly. If it says "No audio detected", your
system's default input device may be wrong — override it:

```bash
AUDIO_INPUT_DEVICE=MacBook uv run app.py --voice   # matches by device name substring
```

and check System Settings -> Privacy & Security -> Microphone if that
doesn't help. `WHISPER_MODEL` (default `base`) can be set to `small` for
better accuracy at the cost of a slower, larger model download.

## Test

```bash
uv run pytest
```

## Evaluation

`uv run python -m scripts.eval_scenarios` runs the 5 review scenarios (basic
query, autonomous multi-tool investigation, asset-specific investigation,
follow-up context, unknown information) against a scripted LLM and prints a
pass/fail table. This proves the loop's mechanics — tool dispatch, evidence
handling, session memory — deterministically, without needing an API key.

It does not by itself prove the model autonomously *chooses* its own tool
sequence; that requires a real LLM. To see that, set `GEMINI_API_KEY` and run
`uv run app.py` — it logs every `TOOL ->` / `TOOL <-` / `REASONING` step so
you can watch the investigation unfold live.

`uv run python -m scripts.eval_routing` evaluates the router against 15
scenarios across 6 categories (RAG, live data, combined/diagnosis, action,
ambiguous, unavailable capability), reporting per-call latency, token
usage, and an overall accuracy score (fails below 90%). Unlike
`eval_scenarios`, this **requires a real API key** — classifying natural
language into the right capabilities is exactly the behavior under test, so
a scripted LLM would just be checking against its own scripted answer. Last
run: 15/15 (100%), ~1.9s average latency on `gemini-2.5-flash`.
