from tools.registry import call_tool


def test_call_tool_dispatches_to_facility_function():
    result = call_tool("get_building_temperature", {"building": "Building A"})
    assert result["temperature"] == 28.4


def test_call_tool_unknown_tool_returns_error():
    result = call_tool("nonexistent_tool", {})
    assert "error" in result


def test_call_tool_invalid_arguments_returns_error_instead_of_raising():
    result = call_tool("get_building_temperature", {"wrong_param": "Building A"})
    assert "error" in result
