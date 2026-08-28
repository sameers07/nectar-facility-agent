# Nectar Facility Agent — Task 1

Voice-driven facility investigation agent:

```
User voice -> Whisper (local STT) -> Investigator (LLM + tool calling) -> local TTS -> User
```

The only external API is the LLM (OpenAI). STT and TTS both run locally, so
no ElevenLabs/Deepgram key is required.

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
- `voice/stt.py` — local Whisper transcription (from a file or the
  microphone).
- `voice/tts.py` — local text-to-speech via `pyttsx3`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in OPENAI_API_KEY
```

## Run

```bash
python app.py            # text mode
python app.py --voice    # microphone in, spoken response out
```

## Test

```bash
pytest
```
