"""MCP server exposing facility operations over the real MCP protocol
(stdio transport). This owns access to the facility data -- the agent
talks to it only through mcp_client/client.py, never reads
data/facility.json directly.
"""
from mcp.server.mcpserver import MCPServer

from mcp_server import service_requests
from tools import facility_tools

server = MCPServer("nectar-facility")


@server.tool(description="Get static details (type, building, floor) for a facility asset.")
def get_asset_details(asset_id: str) -> dict:
    return facility_tools.get_asset_details(asset_id)


@server.tool(description="Get the current operating status of a facility asset.")
def get_asset_status(asset_id: str) -> dict:
    return facility_tools.get_asset_status(asset_id)


@server.tool(description="Get sensor readings for a building (temperature) or an asset (its operating metrics).")
def get_sensor_data(target: str) -> dict:
    return facility_tools.get_sensor_data(target)


@server.tool(description="Get energy consumption for a building.")
def get_energy_consumption(building: str) -> dict:
    return facility_tools.get_energy_consumption(building)


@server.tool(description="Get active alerts for a building.")
def get_active_alerts(building: str) -> dict:
    return facility_tools.get_active_alerts(building)


@server.tool(
    description="Get the HVAC assets in a building and how they relate (e.g. which chiller serves which AHUs)."
)
def get_asset_relationships(building: str) -> dict:
    return facility_tools.get_asset_relationships(building)


@server.tool(description="Create a facility maintenance/service request.")
def create_service_request(asset_id: str, issue: str, priority: str, description: str) -> dict:
    return service_requests.create(asset_id, issue, priority, description)


@server.tool(description="Update the status of an existing service request.")
def update_service_request(request_id: str, status: str) -> dict:
    return service_requests.update(request_id, status)


if __name__ == "__main__":
    server.run()
