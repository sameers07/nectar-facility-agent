"""In-memory service request store -- the mock MCP server's write state.
Separate from tools/facility_tools.py since it's mutable, unlike the
read-only facility data there."""

_requests = {}
_next_id = 1001


def create(asset_id: str, issue: str, priority: str, description: str) -> dict:
    global _next_id
    request_id = f"SR-{_next_id}"
    _next_id += 1
    record = {
        "request_id": request_id,
        "asset_id": asset_id,
        "issue": issue,
        "priority": priority,
        "description": description,
        "status": "created",
    }
    _requests[request_id] = record
    return record


def update(request_id: str, status: str) -> dict:
    record = _requests.get(request_id)
    if record is None:
        return {"error": f"Unknown request_id: {request_id}"}
    record["status"] = status
    return record
