"""Sync Neptune Fusion manual measurements to Home Assistant sensors.

Fetches the latest manually-logged water parameters from Neptune Fusion
(NO3, PO4, Ammonia, Nitrite, Alk, Ca, Mg, Salinity, pH) and creates/updates
corresponding sensor entities in Home Assistant via the REST API.

Run periodically (e.g. every 6 hours) via cron or Task Scheduler.

Required environment variables:
    FUSION_USER     Neptune Fusion username
    FUSION_PASS     Neptune Fusion password
    FUSION_APEX_ID  Your Apex ID (from the Fusion URL)
    HA_URL          Home Assistant URL (e.g. http://192.168.1.100:8123)
    HA_TOKEN        Home Assistant long-lived access token
"""

import os
import sys
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fusion_client import FusionClient

# ── Configuration ──────────────────────────────────────────────────

HA_URL = os.environ["HA_URL"]
HA_TOKEN = os.environ["HA_TOKEN"]
FUSION_USER = os.environ["FUSION_USER"]
FUSION_PASS = os.environ["FUSION_PASS"]
FUSION_APEX_ID = os.environ["FUSION_APEX_ID"]

PARAM_CONFIG = {
    "Alkalinity": {
        "entity_id": "sensor.reef_manual_alkalinity",
        "friendly_name": "Reef Alkalinity (Manual)",
        "unit": "dKH",
        "icon": "mdi:flask",
    },
    "Calcium": {
        "entity_id": "sensor.reef_manual_calcium",
        "friendly_name": "Reef Calcium (Manual)",
        "unit": "ppm",
        "icon": "mdi:flask",
    },
    "Magnesium": {
        "entity_id": "sensor.reef_manual_magnesium",
        "friendly_name": "Reef Magnesium (Manual)",
        "unit": "ppm",
        "icon": "mdi:flask",
    },
    "Nitrate": {
        "entity_id": "sensor.reef_manual_nitrate",
        "friendly_name": "Reef Nitrate (Manual)",
        "unit": "ppm",
        "icon": "mdi:test-tube",
    },
    "Phosphate": {
        "entity_id": "sensor.reef_manual_phosphate",
        "friendly_name": "Reef Phosphate (Manual)",
        "unit": "ppm",
        "icon": "mdi:test-tube",
    },
    "Salinity": {
        "entity_id": "sensor.reef_manual_salinity",
        "friendly_name": "Reef Salinity (Manual)",
        "unit": "ppt",
        "icon": "mdi:waves",
    },
    "pH": {
        "entity_id": "sensor.reef_manual_ph",
        "friendly_name": "Reef pH (Manual)",
        "unit": "pH",
        "icon": "mdi:ph",
    },
    "Ammonia": {
        "entity_id": "sensor.reef_manual_ammonia",
        "friendly_name": "Reef Ammonia (Manual)",
        "unit": "ppm",
        "icon": "mdi:alert-circle",
    },
    "Nitrite": {
        "entity_id": "sensor.reef_manual_nitrite",
        "friendly_name": "Reef Nitrite (Manual)",
        "unit": "ppm",
        "icon": "mdi:alert-circle",
    },
}

# ── Main sync logic ───────────────────────────────────────────────


def push_sensor(entity_id: str, state, attributes: dict) -> bool:
    """Create or update a sensor entity in Home Assistant."""
    url = f"{HA_URL}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"state": state, "attributes": attributes}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    return r.status_code in (200, 201)


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
        config = PARAM_CONFIG.get(param_name)
        if config is None:
            print(f"  Skipping unknown parameter: {param_name}")
            continue

        attributes = {
            "friendly_name": config["friendly_name"],
            "unit_of_measurement": config["unit"],
            "icon": config["icon"],
            "device_class": "measurement",
            "state_class": "measurement",
            "last_tested": data["date"],
            "source": "Neptune Fusion (manual)",
        }

        ok = push_sensor(config["entity_id"], data["value"], attributes)
        status = "OK" if ok else "FAILED"
        print(f"  {config['entity_id']}: {data['value']} {config['unit']} ({data['date']}) - {status}")
        if ok:
            success += 1

    print(f"Updated {success}/{len(latest)} sensors.")


if __name__ == "__main__":
    main()
