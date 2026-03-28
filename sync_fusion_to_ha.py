"""Sync Neptune Fusion manual measurements to Home Assistant.

Fetches the latest manually-logged water parameters from Neptune Fusion
and pushes them into the existing input_number + input_datetime helpers
in HA. The template sensors (sensor.reef_alk, sensor.reef_calcium, etc.)
automatically pick up the new values and record history.

Run weekly via Windows Task Scheduler, or on-demand via the MCP tool.

Required environment variables:
    FUSION_USER, FUSION_PASS, FUSION_APEX_ID
    HA_TOKEN (long-lived access token)
    HA_URL (optional, defaults to http://192.168.7.253:8123)
"""

import os
import sys
import requests
from datetime import datetime

# Add parent dir so we can import fusion_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fusion_client import FusionClient

# ── Configuration ──────────────────────────────────────────────────

HA_URL = os.environ.get("HA_URL", "http://192.168.7.253:8123")
HA_TOKEN = os.environ["HA_TOKEN"]
FUSION_USER = os.environ["FUSION_USER"]
FUSION_PASS = os.environ["FUSION_PASS"]
FUSION_APEX_ID = os.environ["FUSION_APEX_ID"]

HEADERS = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# Map Fusion parameter names → existing HA input_number and input_datetime entities
PARAM_MAP = {
    "Alkalinity": {
        "input_number": "input_number.water_alk_dkh",
        "input_datetime": "input_datetime.last_log_alk",
    },
    "Calcium": {
        "input_number": "input_number.water_calcium",
        "input_datetime": "input_datetime.last_log_calcium",
    },
    "Magnesium": {
        "input_number": "input_number.water_magnesium",
        "input_datetime": "input_datetime.last_log_magnesium",
    },
    "Nitrate": {
        "input_number": "input_number.water_nitrate",
        "input_datetime": "input_datetime.last_log_nitrate",
    },
    "Phosphate": {
        "input_number": "input_number.water_phosphate",
        "input_datetime": "input_datetime.last_log_phosphate",
    },
    "pH": {
        "input_number": "input_number.water_ph",
        "input_datetime": "input_datetime.last_log_ph",
    },
    "Ammonia": {
        "input_number": "input_number.water_ammonia_hanna",
        "input_datetime": "input_datetime.last_log_ammonia_hanna",
    },
    "Salinity": {
        "input_number": "input_number.water_salinity",
        "input_datetime": "input_datetime.last_log_salinity_hanna",
    },
}


def call_service(domain: str, service: str, entity_id: str, data: dict) -> bool:
    """Call an HA service."""
    url = f"{HA_URL}/api/services/{domain}/{service}"
    payload = {"entity_id": entity_id, **data}
    r = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    return r.status_code == 200


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fetching Fusion measurements...")
    client = FusionClient(FUSION_USER, FUSION_PASS, FUSION_APEX_ID)

    try:
        latest = client.get_latest_measurements()
    finally:
        client.close()

    if not latest:
        print("No measurements returned from Fusion.")
        sys.exit(1)

    print(f"Got {len(latest)} parameters: {', '.join(latest.keys())}")

    success = 0
    for param_name, data in latest.items():
        mapping = PARAM_MAP.get(param_name)
        if mapping is None:
            print(f"  Skipping unmapped parameter: {param_name}")
            continue

        value = float(data["value"])

        # Set the input_number value
        ok_val = call_service(
            "input_number", "set_value",
            mapping["input_number"],
            {"value": value},
        )

        # Set the timestamp
        try:
            dt = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, KeyError):
            dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ok_ts = call_service(
            "input_datetime", "set_datetime",
            mapping["input_datetime"],
            {"datetime": dt_str},
        )

        status = "OK" if (ok_val and ok_ts) else f"val={'OK' if ok_val else 'FAIL'} ts={'OK' if ok_ts else 'FAIL'}"
        print(f"  {mapping['input_number']}: {value} ({dt_str}) - {status}")
        if ok_val:
            success += 1

    print(f"Updated {success}/{len(latest)} parameters.")


if __name__ == "__main__":
    main()
