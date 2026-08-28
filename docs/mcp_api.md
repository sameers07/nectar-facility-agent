# MCP Server API Reference

Server: `mcp_server/server.py` (`mcp.server.mcpserver.MCPServer`, name
`nectar-facility`). Transport: stdio — the client (`mcp_client/client.py`)
spawns `python -m mcp_server.server` as a subprocess and speaks MCP over
its stdin/stdout.

```bash
uv run python -m mcp_server.server   # run standalone for manual testing
```

Backing data: `data/facility.json`, accessed only by this server via
`tools/facility_tools.py`. Callers never read the file directly.

All read tools use `tools/facility_tools.py`'s formatting-tolerant lookup
— `"ahu02"`, `"AHU 02"`, and `"AHU-02"` all resolve to the same asset.
Unknown names return `{"error": "Unknown asset: ..."}` / `{"error":
"Unknown building: ..."}` rather than raising.

## Read tools

### `get_asset_details(asset_id: str) -> dict`
Static metadata: type, building, floor.
```json
// get_asset_details("AHU-02")
{"asset_id": "AHU-02", "type": "ahu", "building": "Building A", "floor": 2}
```

### `get_asset_status(asset_id: str) -> dict`
Current operating status and metric (chillers: `power_deviation`; AHUs:
`airflow`).
```json
// get_asset_status("AHU-02")
{"asset": "AHU-02", "type": "ahu", "building": "Building A", "floor": 2,
 "status": "warning", "airflow": 41}
```

### `get_sensor_data(target: str) -> dict`
Sensor readings for a **building** (temperature) or an **asset** (its
operating metrics) — one tool for both, dispatched by whether `target`
matches a building or asset name.
```json
// get_sensor_data("Building A")
{"target": "Building A", "readings": {"temperature": 28.4}}

// get_sensor_data("AHU-02")
{"target": "AHU-02", "readings": {"status": "warning", "airflow": 41}}
```

### `get_energy_consumption(building: str) -> dict`
```json
// get_energy_consumption("Building A")
{"building": "Building A", "consumption_kwh": 842, "period": "today"}
```

### `get_active_alerts(building: str) -> dict`
```json
// get_active_alerts("Building A")
{"building": "Building A", "alerts": [
  {"asset": "AHU-02", "building": "Building A", "type": "LOW_AIRFLOW", "severity": "high"}
]}
```

### `get_asset_relationships(building: str) -> dict`
Which HVAC assets are in a building and which chiller serves which AHUs.
```json
// get_asset_relationships("Building A")
{"building": "Building A",
 "assets": ["Chiller-01", "AHU-01", "AHU-02"],
 "relationships": [{"chiller": "Chiller-01", "serves": ["AHU-01", "AHU-02"]}]}
```

## Write tools

Never called directly by the LLM — only reachable through the safety gate
in `agent/orchestrator.py` after explicit user confirmation of a
`propose_action` proposal (see README section 8).

### `create_service_request(asset_id: str, issue: str, priority: str, description: str) -> dict`
`priority` is one of `low` / `medium` / `high`. Assigns an incrementing ID
starting at `SR-1001`, held in-memory for the server process's lifetime
(`mcp_server/service_requests.py`) — not persisted across restarts.
```json
// create_service_request("AHU-02", "Low airflow", "high", "AHU-02 has an active low-airflow alert.")
{"request_id": "SR-1001", "asset_id": "AHU-02", "issue": "Low airflow",
 "priority": "high", "description": "AHU-02 has an active low-airflow alert.",
 "status": "created"}
```

### `update_service_request(request_id: str, status: str) -> dict`
```json
// update_service_request("SR-1001", "in_progress")
{"request_id": "SR-1001", "asset_id": "AHU-02", "issue": "Low airflow",
 "priority": "high", "description": "...", "status": "in_progress"}

// unknown request_id
{"error": "Unknown request_id: SR-9999"}
```

## Error behavior

| Failure | Response |
|---|---|
| Unknown building/asset name | `{"error": "Unknown building/asset: <name>"}` — a normal tool result, not a protocol error |
| Missing/invalid arguments | MCP SDK's pydantic validation rejects the call before it reaches the tool function; the client surfaces this as `{"error": "...validation error..."}` |
| Server process unreachable | `mcp_client.client.MCPError` raised at the client; `tools/mcp_tools.py`'s `call_mcp_tool` catches it and returns `{"error": "Could not reach the facility system: ..."}` instead of raising further |

See [evaluation/mcp_results.md](../evaluation/mcp_results.md) for live
traces of each of these.
