"""Tests the real MCP server/client over an actual subprocess + stdio
transport -- deliberately not mocked, since this is exactly the boundary
Task 4 requires to be a genuine protocol, not a decorative wrapper around
direct function calls. Slower than the rest of the suite (spawns a
subprocess per test module) but that's the honest cost of testing this
layer for real.
"""
import pytest

from mcp_client.client import MCPClient, MCPError

EXPECTED_TOOLS = {
    "get_asset_details",
    "get_asset_status",
    "get_sensor_data",
    "get_energy_consumption",
    "get_active_alerts",
    "get_asset_relationships",
    "create_service_request",
    "update_service_request",
}


@pytest.fixture(scope="module")
def client():
    c = MCPClient()
    yield c
    c.close()


def test_server_starts_and_client_connects(client):
    assert client.list_tools()


def test_tool_discovery_exposes_all_eight_tools(client):
    assert set(client.list_tools()) == EXPECTED_TOOLS


def test_get_asset_details(client):
    result = client.call_tool("get_asset_details", {"asset_id": "AHU-02"})
    assert result == {"asset_id": "AHU-02", "type": "ahu", "building": "Building A", "floor": 2}


def test_get_asset_status(client):
    result = client.call_tool("get_asset_status", {"asset_id": "AHU-02"})
    assert result["status"] == "warning"


def test_get_sensor_data_for_building(client):
    result = client.call_tool("get_sensor_data", {"target": "Building A"})
    assert result["readings"]["temperature"] == 28.4


def test_get_sensor_data_for_asset(client):
    result = client.call_tool("get_sensor_data", {"target": "AHU-02"})
    assert result["readings"]["airflow"] == 41


def test_get_energy_consumption(client):
    result = client.call_tool("get_energy_consumption", {"building": "Building A"})
    assert result["consumption_kwh"] == 842


def test_get_active_alerts(client):
    result = client.call_tool("get_active_alerts", {"building": "Building A"})
    assert result["alerts"][0]["type"] == "LOW_AIRFLOW"


def test_get_asset_relationships(client):
    result = client.call_tool("get_asset_relationships", {"building": "Building A"})
    assert {"chiller": "Chiller-01", "serves": ["AHU-01", "AHU-02"]} in result["relationships"]


def test_create_and_update_service_request(client):
    created = client.call_tool(
        "create_service_request",
        {"asset_id": "AHU-02", "issue": "Low airflow", "priority": "high", "description": "test"},
    )
    assert created["status"] == "created"
    assert created["request_id"].startswith("SR-")

    updated = client.call_tool("update_service_request", {"request_id": created["request_id"], "status": "in_progress"})
    assert updated["status"] == "in_progress"


def test_invalid_asset_returns_error_not_crash(client):
    result = client.call_tool("get_asset_status", {"asset_id": "NOPE-99"})
    assert "error" in result


def test_update_unknown_request_id_returns_error(client):
    result = client.call_tool("update_service_request", {"request_id": "SR-9999", "status": "closed"})
    assert "error" in result


def test_unreachable_server_raises_mcp_error():
    with pytest.raises(MCPError):
        MCPClient(command="nonexistent-binary-xyz", args=[], connect_timeout=5)
