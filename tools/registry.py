"""Tool registry: exposes facility_tools functions to the LLM as callable
tools, and dispatches by name when the LLM requests one.
"""
from tools import facility_tools


def _building_param(description: str) -> dict:
    known = ", ".join(facility_tools.list_buildings())
    return {"building": {"type": "string", "description": f"{description} One of: {known}."}}


def _asset_param(description: str) -> dict:
    known = ", ".join(facility_tools.list_assets())
    return {"asset": {"type": "string", "description": f"{description} One of: {known}."}}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_building_temperature",
            "description": "Get the current temperature of a building.",
            "parameters": {
                "type": "object",
                "properties": _building_param("Building name."),
                "required": ["building"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hvac_assets",
            "description": "List the HVAC assets (chillers, AHUs) installed in a building.",
            "parameters": {
                "type": "object",
                "properties": _building_param("Building name."),
                "required": ["building"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_status",
            "description": "Get the status and operating metrics of a specific HVAC asset.",
            "parameters": {
                "type": "object",
                "properties": _asset_param("Asset name."),
                "required": ["asset"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alerts",
            "description": "Get active alerts for a building.",
            "parameters": {
                "type": "object",
                "properties": _building_param("Building name."),
                "required": ["building"],
            },
        },
    },
]

TOOL_DISPATCH = {
    "get_building_temperature": facility_tools.get_building_temperature,
    "get_hvac_assets": facility_tools.get_hvac_assets,
    "get_asset_status": facility_tools.get_asset_status,
    "get_active_alerts": facility_tools.get_active_alerts,
}


def call_tool(name: str, arguments: dict) -> dict:
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**arguments)
    except TypeError as e:
        # e.g. the model passed a wrong/missing argument name -- surface it
        # as a tool error the LLM can react to, not a crash.
        return {"error": f"Invalid arguments for {name}: {e}"}
