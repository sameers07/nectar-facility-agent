"""Facility data access functions.

The LLM never touches facility.json directly — it can only call these
functions. Each one answers exactly one question, mirroring how a real
building-management system API would be scoped.
"""
import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "facility.json"


def _load():
    with open(DATA_PATH) as f:
        return json.load(f)


def _normalize(name: str) -> str:
    return re.sub(r"[\s\-_]+", "", name).upper()


def _lookup(mapping: dict, name: str):
    """Exact match first, then a formatting-tolerant match (case, spacing,
    hyphens) so 'ahu02' or 'AHU 02' still resolves to 'AHU-02' -- voice
    transcripts and model-generated arguments rarely match the JSON key
    exactly."""
    if name in mapping:
        return name, mapping[name]
    normalized = _normalize(name)
    for key, value in mapping.items():
        if _normalize(key) == normalized:
            return key, value
    return None, None


def get_building_temperature(building: str) -> dict:
    data = _load()
    canonical, info = _lookup(data["buildings"], building)
    if info is None:
        return {"error": f"Unknown building: {building}"}
    return {"building": canonical, "temperature": info["temperature"]}


def get_hvac_assets(building: str) -> dict:
    data = _load()
    canonical, info = _lookup(data["buildings"], building)
    if info is None:
        return {"error": f"Unknown building: {building}"}
    return {"building": canonical, "hvac_assets": info["hvac_assets"]}


def get_asset_status(asset: str) -> dict:
    data = _load()
    canonical, info = _lookup(data["assets"], asset)
    if info is None:
        return {"error": f"Unknown asset: {asset}"}
    return {"asset": canonical, **info}


def get_active_alerts(building: str) -> dict:
    data = _load()
    canonical, info = _lookup(data["buildings"], building)
    if info is None:
        return {"error": f"Unknown building: {building}"}
    alerts = [a for a in data["alerts"] if a.get("building") == canonical]
    return {"building": canonical, "alerts": alerts}


def list_buildings() -> list:
    return list(_load()["buildings"].keys())


def list_assets() -> list:
    return list(_load()["assets"].keys())


def list_known_terms() -> list:
    """Building and asset names, e.g. to bias speech recognition toward them."""
    return list_buildings() + list_assets()
