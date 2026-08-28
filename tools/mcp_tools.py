"""The Investigator's default facility tools, backed by the real MCP
client/server (mcp_client/, mcp_server/) rather than direct calls into
tools/facility_tools.py -- the agent only ever talks to the facility
through the MCP protocol now. tools/facility_tools.py still exists, but
only mcp_server/server.py calls it directly.
"""
from mcp_client.client import MCPClient, MCPError
from tools import facility_tools


def _building_param(description: str) -> dict:
    known = ", ".join(facility_tools.list_buildings())
    return {"building": {"type": "string", "description": f"{description} One of: {known}."}}


def _asset_param(description: str, param_name: str = "asset_id") -> dict:
    known = ", ".join(facility_tools.list_assets())
    return {param_name: {"type": "string", "description": f"{description} One of: {known}."}}


MCP_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_asset_details",
            "description": "Get static details (type, building, floor) for a facility asset.",
            "parameters": {"type": "object", "properties": _asset_param("Asset ID."), "required": ["asset_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_status",
            "description": "Get the current operating status of a facility asset.",
            "parameters": {"type": "object", "properties": _asset_param("Asset ID."), "required": ["asset_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_data",
            "description": "Get sensor readings for a building (temperature) or an asset (its operating metrics).",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "A building or asset name/ID."}},
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_energy_consumption",
            "description": "Get energy consumption for a building.",
            "parameters": {"type": "object", "properties": _building_param("Building name."), "required": ["building"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alerts",
            "description": "Get active alerts for a building.",
            "parameters": {"type": "object", "properties": _building_param("Building name."), "required": ["building"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_relationships",
            "description": "Get the HVAC assets in a building and how they relate (e.g. which chiller serves which AHUs).",
            "parameters": {"type": "object", "properties": _building_param("Building name."), "required": ["building"]},
        },
    },
]

_client = None


def get_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client


def call_mcp_tool(name: str, arguments: dict) -> dict:
    try:
        return get_client().call_tool(name, arguments)
    except MCPError as e:
        return {"error": f"Could not reach the facility system: {e}"}
