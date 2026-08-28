"""Facility data access functions.

The LLM never touches facility.json directly — it can only call these
functions. Each one answers exactly one question, mirroring how a real
building-management system API would be scoped.
"""
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "facility.json"


def _load():
    with open(DATA_PATH) as f:
        return json.load(f)


def get_building_temperature(building: str) -> dict:
    data = _load()
    info = data["buildings"].get(building)
    if info is None:
        return {"error": f"Unknown building: {building}"}
    return {"building": building, "temperature": info["temperature"]}


def get_hvac_assets(building: str) -> dict:
    data = _load()
    info = data["buildings"].get(building)
    if info is None:
        return {"error": f"Unknown building: {building}"}
    return {"building": building, "hvac_assets": info["hvac_assets"]}


def get_asset_status(asset: str) -> dict:
    data = _load()
    info = data["assets"].get(asset)
    if info is None:
        return {"error": f"Unknown asset: {asset}"}
    return {"asset": asset, **info}


def get_active_alerts(building: str) -> dict:
    data = _load()
    alerts = [a for a in data["alerts"] if a.get("building") == building]
    return {"building": building, "alerts": alerts}


def list_known_terms() -> list:
    """Building and asset names, e.g. to bias speech recognition toward them."""
    data = _load()
    return list(data["buildings"].keys()) + list(data["assets"].keys())
