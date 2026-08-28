# Nectar Facility Agent — Task 1

Voice-driven facility investigation agent. STT (Whisper) → Investigator (LLM +
tool calling) → TTS. See architecture notes in the project discussion.

## Status

Steps 1-3 done: project scaffold, mock facility data (`data/facility.json`),
and the four facility tools (`tools/facility_tools.py`) exposed through a
tool registry (`tools/registry.py`) for LLM function calling.

Next: build the investigator loop (`agent/investigator.py`) — Understand →
Plan → Investigate → Decide.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your API keys
```

## Run

```bash
python app.py
```

## Test

```bash
pytest
```
