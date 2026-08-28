# Nectar Facility Agent — Task 1

Voice-driven facility investigation agent:

```
User voice -> Whisper (local STT) -> Investigator (LLM + tool calling) -> local TTS -> User
```

The only external API is the LLM (Gemini, via its OpenAI-compatible
endpoint). STT and TTS both run locally, so no ElevenLabs/Deepgram key is
required.

## Architecture

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
- `agent/voice_agent.py` — `VoiceAgent` ties the investigator, session, and
  I/O (text or voice) together into one runnable loop; `app.py` is a thin
  CLI wrapper around it.
- `voice/stt.py` — local Whisper transcription (from a file or the
  microphone).
- `voice/tts.py` — local text-to-speech via `pyttsx3`.

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
