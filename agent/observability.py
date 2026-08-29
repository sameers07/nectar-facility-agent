"""Per-request observability: a request ID that correlates every log line
for one user turn (STT -> router -> investigator -> tools -> TTS), plus
timing helpers and a per-turn metrics summary.

Uses a contextvar rather than threading a request_id parameter through
every function signature -- request_id_var is set once per turn
(VoiceAgent.step) and every logger.info() call anywhere in that turn picks
it up automatically via RequestIdFilter.
"""
import contextvars
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

request_id_var = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


@dataclass
class Metrics:
    request_id: str
    stt_ms: float = None
    route_ms: float = None
    route_tokens: int = None
    llm_calls: list = field(default_factory=list)  # [{"stage": "investigator", "model": ..., "ms": ..., "tokens": ...}]
    tool_calls: list = field(default_factory=list)  # [{"name": ..., "ms": ...}]
    tts_ms: float = None
    model: str = None
    errors: list = field(default_factory=list)  # [{"stage": ..., "error": ...}]

    def record_llm_call(self, stage: str, model: str, ms: float, tokens: int = None):
        self.llm_calls.append({"stage": stage, "model": model, "ms": round(ms, 1), "tokens": tokens})

    def record_tool_call(self, name: str, ms: float):
        self.tool_calls.append({"name": name, "ms": round(ms, 1)})

    def record_error(self, stage: str, error: str):
        self.errors.append({"stage": stage, "error": error})

    def summary(self) -> str:
        total_llm_ms = sum(c["ms"] for c in self.llm_calls) + (self.route_ms or 0)
        total_tool_ms = sum(c["ms"] for c in self.tool_calls)
        return (
            f"request_id={self.request_id} model={self.model} "
            f"stt_ms={_fmt(self.stt_ms)} route_ms={_fmt(self.route_ms)} "
            f"llm_calls={len(self.llm_calls)} llm_ms_total={total_llm_ms:.0f} "
            f"tool_calls={len(self.tool_calls)} tool_ms_total={total_tool_ms:.0f} "
            f"tts_ms={_fmt(self.tts_ms)} errors={len(self.errors)}"
        )


def _fmt(value):
    return f"{value:.0f}" if value is not None else "-"


_metrics_var = contextvars.ContextVar("metrics", default=None)


def current_metrics() -> Metrics:
    return _metrics_var.get()


@contextmanager
def new_request():
    """Starts a new correlated request: fresh request_id + fresh Metrics,
    both available for the duration of the `with` block via
    request_id_var/current_metrics()."""
    rid = uuid.uuid4().hex[:8]
    id_token = request_id_var.set(rid)
    metrics = Metrics(request_id=rid)
    metrics_token = _metrics_var.set(metrics)
    try:
        yield metrics
    finally:
        request_id_var.reset(id_token)
        _metrics_var.reset(metrics_token)


@contextmanager
def timed():
    """`with timed() as t: ...` then read t.ms afterward."""
    start = time.perf_counter()
    box = _Elapsed()
    try:
        yield box
    finally:
        box.ms = (time.perf_counter() - start) * 1000


class _Elapsed:
    ms = None
