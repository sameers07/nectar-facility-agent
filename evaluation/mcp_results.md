# MCP Evaluation (Task 4)

All tests run against the real MCP server over a real stdio subprocess —
`tests/test_mcp_integration.py` (13 tests, not mocked) plus the live traces
below via `mcp_client/client.py`.

## Server starts, client connects

```
Connecting...
8 tools discovered via MCP protocol:
 - get_asset_details
 - get_asset_status
 - get_sensor_data
 - get_energy_consumption
 - get_active_alerts
 - get_asset_relationships
 - create_service_request
 - update_service_request
```

Discovered through the protocol (`ClientSession.list_tools()`), not
imported directly from Python — `agent/investigator.py` only imports
`tools.mcp_tools.call_mcp_tool`, which only imports `mcp_client.client`;
it never imports `tools.facility_tools` directly. Only
`mcp_server/server.py` calls `tools/facility_tools.py`.

## Each read tool, real round trip

```
get_asset_status(AHU-02) -> {'asset': 'AHU-02', 'type': 'ahu', 'building': 'Building A', 'floor': 2, 'status': 'warning', 'airflow': 41}
get_asset_details(AHU-02) -> {'asset_id': 'AHU-02', 'type': 'ahu', 'building': 'Building A', 'floor': 2}
get_sensor_data(Building A) -> {'target': 'Building A', 'readings': {'temperature': 28.4}}
get_sensor_data(AHU-02) -> {'target': 'AHU-02', 'readings': {'status': 'warning', 'airflow': 41}}
get_energy_consumption(Building A) -> {'building': 'Building A', 'consumption_kwh': 842, 'period': 'today'}
get_active_alerts(Building A) -> {'building': 'Building A', 'alerts': [{'asset': 'AHU-02', 'type': 'LOW_AIRFLOW', 'severity': 'high'}]}
get_asset_relationships(Building A) -> {'building': 'Building A', 'assets': [...], 'relationships': [{'chiller': 'Chiller-01', 'serves': ['AHU-01', 'AHU-02']}]}
```

## Write tools + safety gate

```
create_service_request(AHU-02, "Low airflow", high, ...) -> {'request_id': 'SR-1001', 'status': 'created'}
update_service_request(SR-1001, in_progress) -> {'request_id': 'SR-1001', 'status': 'in_progress'}
```

The Investigator never calls these directly — it can only call
`propose_action`, which stores `session.pending_action` and asks the user
to confirm. `agent/orchestrator.py` checks `pending_action` *before*
routing on every turn; only a deterministic (regex, not LLM) "yes"
executes the write, using the details captured at proposal time.

**Confirmation = YES** (`e2e_results.md` Test D/E2E-04/E2E-08):
```
PROPOSED ACTION: {'action': 'create_service_request', 'asset_id': 'AHU-02', ...}
Agent: I found a likely AHU-02 airflow issue. Would you like me to create a maintenance request?
[Yes.]
Agent: Done -- created service request SR-1001 for AHU-02.
```

**Confirmation = NO** (E2E-05): agent asks, user says "No, don't do that." ->
`Agent: No problem, I won't create that request.` — no `create_service_request`
call in the log.

**No pending action + "Yes."**: since there's no `session.pending_action`,
this routes through the normal Router path, not the confirmation path — the
router itself scores an unqualified "Yes" as low-confidence/unclear and the
system asks for clarification rather than creating anything. Zero writes.

## Failure handling

**Invalid asset**:
```
Query: "Check the status of AHU-999."
Agent: I can't find AHU-999 in the facility's asset registry. Could you
please double-check the asset ID? The recognized AHU assets are AHU-01,
AHU-02, and AHU-03.
```

**Invalid tool arguments** (MCP SDK's own pydantic validation):
```
call_mcp_tool('get_asset_status', {'wrong_param_name': 'AHU-02'})
-> {'error': "Error executing tool get_asset_status: 1 validation error...
    asset_id\n  Field required [type=missing, input_value={'wrong_param_name': 'AHU-02'}...]"}
```
No crash — the client wraps the validation error into a normal `{"error":
...}` result the LLM can react to.

**MCP server unreachable** (`test_unreachable_server_raises_mcp_error` +
live reproduction with a monkeypatched client):
```
call_mcp_tool result when server is unreachable:
{'error': 'Could not reach the facility system: Connection refused: MCP server is not running'}
```
Through the full Investigator loop with a real LLM call:
```
Agent: I am unable to retrieve the status of AHU-02 at this moment because
the facility system's MCP server is not running. Please try again later.
Confidence: 0.9
```

**LLM provider failure** (genuine transient Gemini 503 hit during live
testing, not simulated):
```
openai.InternalServerError: Error code: 503 - ... 'This model is currently
experiencing high demand...'
Agent: I ran into a technical error while investigating. Please try again.
Confidence: 0%
```

## Design decisions

- `mcp_client/client.py` wraps the SDK's async client in a synchronous
  interface for the synchronous Investigator loop: a background thread
  owns one event loop, and a single long-lived coroutine holds the
  `stdio_client`/`ClientSession` context managers open for the
  connection's lifetime (anyio's cancel scopes require entering/exiting a
  task group in the same task — a fresh coroutine per call doesn't work).
- `tools/registry.py` (direct facility_tools.py calls) still exists but is
  no longer the Investigator's default tool source — `tools/mcp_tools.py`
  is, genuinely going through the protocol in production.
