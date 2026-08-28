from tools.facility_tools import (
    get_active_alerts,
    get_asset_status,
    get_building_temperature,
    get_hvac_assets,
)


def test_get_building_temperature():
    result = get_building_temperature("Building A")
    assert result["temperature"] == 28.4


def test_get_hvac_assets():
    result = get_hvac_assets("Building A")
    assert "AHU-02" in result["hvac_assets"]


def test_get_asset_status():
    result = get_asset_status("AHU-02")
    assert result["status"] == "warning"
    assert result["airflow"] == 41


def test_get_active_alerts():
    result = get_active_alerts("Building A")
    assert any(a["type"] == "LOW_AIRFLOW" for a in result["alerts"])


def test_unknown_building():
    result = get_building_temperature("Building Z")
    assert "error" in result
