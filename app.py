"""Entry point (stub). Steps 1-3 only: verifies the facility tools work
end-to-end before the investigator/tool-calling loop is built on top.
"""
from tools.registry import call_tool


def main():
    print(call_tool("get_building_temperature", {"building": "Building A"}))
    print(call_tool("get_hvac_assets", {"building": "Building A"}))
    print(call_tool("get_asset_status", {"asset": "AHU-02"}))
    print(call_tool("get_active_alerts", {"building": "Building A"}))


if __name__ == "__main__":
    main()
