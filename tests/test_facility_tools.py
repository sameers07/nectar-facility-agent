from tools.facility_tools import (
    get_active_alerts,
    get_asset_status,
    get_building_temperature,
    get_hvac_assets,
    list_known_terms,
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


def test_asset_lookup_tolerates_formatting_variants():
    for variant in ["AHU02", "ahu-02", "ahu 02", "AHU_02"]:
        result = get_asset_status(variant)
        assert result["asset"] == "AHU-02", f"{variant!r} should resolve to AHU-02"
        assert result["status"] == "warning"


def test_building_lookup_tolerates_case():
    result = get_building_temperature("building a")
    assert result["building"] == "Building A"
    assert result["temperature"] == 28.4


def test_list_known_terms():
    terms = list_known_terms()
    assert "Building A" in terms
    assert "AHU-02" in terms
