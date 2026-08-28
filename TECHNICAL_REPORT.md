# Technical Report — Nectar Autonomous Facility Agent

## Summary

A voice-driven agent that autonomously investigates facility problems,
answers questions from documentation, checks live building/HVAC data, and
creates maintenance requests — deciding for itself at each step what
evidence it needs, never guessing when it lacks information, and never
executing a write action without explicit user confirmation. Built
incrementally across five stages (voice + investigation, LLM routing,
RAG, MCP, end-to-end integration), each stage extending the same system
rather than bolting on a separate one.

## Architecture, in one sentence

Voice -> local Whisper STT -> a router that classifies each request into
a structured contract (intent, needed capabilities, complexity,
confidence) -> a single tool-calling Investigator that can call live
facility data (via a real MCP server), documentation retrieval (RAG), or
propose a write action -> a safety gate that only executes that action
after an explicit "yes" -> local TTS.

Full diagram and per-capability detail: [README.md](README.md).

## Key design decisions

| Decision | Why |
|---|---|
| One Investigator, capabilities as tools | RAG and MCP are tools in the same tool-calling loop, not separate agents — lets the model interleave a live-data check and a documentation lookup within one reasoning chain instead of merging two pipelines' outputs afterward. |
| LLM produces a contract; code executes it | The router's job is judgment (what does this need); dispatch on that contract is deterministic Python. That's not "hard-coded routing" — the classification is genuinely LLM-driven, only the resulting action is deterministic. |
| Confirmation via regex, not LLM | A safety gate on a write action needs predictable yes/no/neither, not a best-effort classification. |
| Local embeddings + numpy, not FAISS/an embeddings API | The knowledge base is a few dozen chunks; a full vector database solves a problem this dataset doesn't have. Right-sized, not a shortcut. |
| MCP as a tool boundary | The Investigator stays the reasoning engine; MCP is only how it reaches the facility, not a separate "MCP agent." |

## Evaluation results

- **Routing**: 15/15 (100%) live accuracy across 6 categories (knowledge,
  live data, combined diagnosis, action, ambiguous, unavailable
  capability), ~1.9s average latency. [evaluation/routing_results.md](evaluation/routing_results.md)
- **RAG**: correct retrieval and citation on supported questions; correct
  refusal (no hallucination) on unsupported ones, including a
  near-miss case where a marginally-relevant chunk passed the similarity
  threshold but the model still recognized it didn't answer the question.
  [evaluation/rag_results.md](evaluation/rag_results.md)
- **MCP**: all 8 required tools verified against a real subprocess (not
  mocked) — `tests/test_mcp_integration.py`, 13 tests. [evaluation/mcp_results.md](evaluation/mcp_results.md)
- **End-to-end**: 8 acceptance scenarios covering RAG, live data,
  combined reasoning, confirmed and rejected actions, unsupported
  questions, and MCP failure injection. [evaluation/e2e_results.md](evaluation/e2e_results.md)
- **Unit tests**: 57 passing (`uv run pytest`, ~10s).

## Bugs found and fixed during acceptance testing

Both found by running real scenarios against the real LLM, not assumed
from unit tests passing:

1. **RAG query-phrasing sensitivity** — a bare keyword query ("AHU")
   scored 0.30 against a document that scores 0.83 for the equivalent
   full question, causing a false "not found." Fixed by requiring
   full-question queries in the tool description and prompting a retry
   with different phrasing before giving up.
2. **Action requests skipping a proactive status check** — when routed
   with `sources=['action']` alone, the investigator sometimes asked the
   user to describe a named asset's problem instead of checking its
   status itself, despite having the tool to do so. Fixed by requiring
   that check in the system prompt.

Both are documented with before/after traces in
[evaluation/e2e_results.md](evaluation/e2e_results.md).

## Limitations

- Mock facility data covers 2 buildings, 5 assets, floors 0-2 only.
- No document-versioning/conflict resolution in RAG.
- Service requests are in-memory per server process, not persisted.
- LLM investigation depth shows some run-to-run sampling variance,
  documented rather than hidden (see `evaluation/e2e_results.md`).

Full detail, including future-improvement ideas: [README.md](README.md#17-limitations).
