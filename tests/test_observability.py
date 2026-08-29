import time

from agent.observability import current_metrics, new_request, timed


def test_new_request_provides_a_unique_id_and_metrics():
    with new_request() as metrics:
        assert metrics.request_id
        assert current_metrics() is metrics

    with new_request() as metrics2:
        assert metrics2.request_id != metrics.request_id


def test_current_metrics_is_none_outside_a_request():
    assert current_metrics() is None


def test_metrics_record_llm_call():
    with new_request() as metrics:
        metrics.record_llm_call("investigator", "gemini-2.5-flash", 123.456, tokens=42)
    assert metrics.llm_calls == [{"stage": "investigator", "model": "gemini-2.5-flash", "ms": 123.5, "tokens": 42}]


def test_metrics_record_tool_call():
    with new_request() as metrics:
        metrics.record_tool_call("get_asset_status", 55.0)
    assert metrics.tool_calls == [{"name": "get_asset_status", "ms": 55.0}]


def test_metrics_record_error():
    with new_request() as metrics:
        metrics.record_error("router", "boom")
    assert metrics.errors == [{"stage": "router", "error": "boom"}]


def test_metrics_summary_includes_key_fields():
    with new_request() as metrics:
        metrics.model = "gemini-2.5-pro"
        metrics.stt_ms = 200.0
        metrics.route_ms = 150.0
        metrics.record_llm_call("investigator", "gemini-2.5-pro", 300.0, tokens=100)
        metrics.record_tool_call("get_sensor_data", 10.0)
        metrics.record_error("router", "transient")
        summary = metrics.summary()

    assert f"request_id={metrics.request_id}" in summary
    assert "model=gemini-2.5-pro" in summary
    assert "stt_ms=200" in summary
    assert "route_ms=150" in summary
    assert "llm_calls=1" in summary
    assert "tool_calls=1" in summary
    assert "errors=1" in summary


def test_timed_measures_elapsed_time():
    with timed() as t:
        time.sleep(0.01)
    assert t.ms >= 10
