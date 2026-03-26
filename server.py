"""Neptune Apex MCP Server.

Exposes Neptune Apex aquarium controller functionality via MCP tools.
"""

import json
import os

import requests
from mcp.server.fastmcp import FastMCP

from apex_client import ApexClient
from fusion_client import FusionClient

# ── Configuration ──────────────────────────────────────────────────
APEX_HOST = os.environ["APEX_HOST"]
APEX_USER = os.environ["APEX_USER"]
APEX_PASS = os.environ["APEX_PASS"]
FUSION_USER = os.environ.get("FUSION_USER", APEX_USER)
FUSION_PASS = os.environ.get("FUSION_PASS", APEX_PASS)
FUSION_APEX_ID = os.environ.get("FUSION_APEX_ID", "")
HA_URL = os.environ.get("HA_URL", "")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

PARAM_HA_CONFIG = {
    "Alkalinity": ("sensor.reef_manual_alkalinity", "Reef Alkalinity (Manual)", "dKH", "mdi:flask"),
    "Calcium": ("sensor.reef_manual_calcium", "Reef Calcium (Manual)", "ppm", "mdi:flask"),
    "Magnesium": ("sensor.reef_manual_magnesium", "Reef Magnesium (Manual)", "ppm", "mdi:flask"),
    "Nitrate": ("sensor.reef_manual_nitrate", "Reef Nitrate (Manual)", "ppm", "mdi:test-tube"),
    "Phosphate": ("sensor.reef_manual_phosphate", "Reef Phosphate (Manual)", "ppm", "mdi:test-tube"),
    "Salinity": ("sensor.reef_manual_salinity", "Reef Salinity (Manual)", "ppt", "mdi:waves"),
    "pH": ("sensor.reef_manual_ph", "Reef pH (Manual)", "pH", "mdi:ph"),
    "Ammonia": ("sensor.reef_manual_ammonia", "Reef Ammonia (Manual)", "ppm", "mdi:alert-circle"),
    "Nitrite": ("sensor.reef_manual_nitrite", "Reef Nitrite (Manual)", "ppm", "mdi:alert-circle"),
}

client = ApexClient(APEX_HOST, APEX_USER, APEX_PASS)
_fusion: FusionClient | None = None


def _get_fusion() -> FusionClient:
    """Lazy-init the Fusion client (launches headless browser on first use)."""
    global _fusion
    if _fusion is None:
        if not FUSION_APEX_ID:
            raise RuntimeError(
                "FUSION_APEX_ID not set. Find your Apex ID in the Fusion URL: "
                "https://apexfusion.com/apex/<APEX_ID>"
            )
        _fusion = FusionClient(FUSION_USER, FUSION_PASS, FUSION_APEX_ID)
    return _fusion

mcp = FastMCP(
    "Neptune Apex",
    instructions="Control and monitor a Neptune Apex aquarium controller",
)

# ── Helpers ────────────────────────────────────────────────────────

PROBE_TYPE_LABELS = {
    "Temp": "Temperature",
    "pH": "pH",
    "ORP": "ORP (mV)",
    "Cond": "Salinity (ppt)",
    "Amps": "Current (A)",
    "pwr": "Power (W)",
    "volts": "Voltage (V)",
    "alk": "Alkalinity (dKH)",
    "ca": "Calcium (ppm)",
    "mg": "Magnesium (ppm)",
    "digital": "Digital Switch",
    "in": "Analog Input",
    "gph": "Flow (GPH)",
}

OUTPUT_STATE_LABELS = {
    "AON": "Auto ON (program says ON)",
    "AOF": "Auto OFF (program says OFF)",
    "ON": "Manually ON",
    "OFF": "Manually OFF",
    "TBL": "Following timed table",
    "PF1": "Profile 1 active",
    "PF2": "Profile 2 active",
}


def _format_probe(inp: dict) -> dict:
    """Format a probe reading for display."""
    ptype = inp.get("type", "unknown")
    return {
        "name": inp["name"],
        "value": inp.get("value"),
        "type": ptype,
        "type_label": PROBE_TYPE_LABELS.get(ptype, ptype),
    }


def _format_output(out: dict) -> dict:
    """Format an output for display."""
    status = out.get("status", [])
    state = status[0] if status else "unknown"
    result = {
        "name": out["name"],
        "type": out.get("type", "unknown"),
        "device_id": out.get("did", ""),
        "state": state,
        "state_label": OUTPUT_STATE_LABELS.get(state, state),
    }
    if len(status) > 1 and status[1]:
        result["intensity"] = status[1]
    if out.get("type") in ("dos", "dqd") and len(status) > 4:
        result["total_volume_ml"] = int(status[4]) / 1000 if status[4] else None
        result["capacity_ml"] = int(status[3]) / 1000 if len(status) > 3 and status[3] else None
    return result


# ── MCP Tools ──────────────────────────────────────────────────────

@mcp.tool()
def get_system_info() -> str:
    """Get Neptune Apex system information (hostname, model, firmware, serial)."""
    info = client.get_system_info()
    return json.dumps(info, indent=2)


@mcp.tool()
def get_all_probes() -> str:
    """Get all probe/sensor readings from the Apex.

    Returns temperature, pH, ORP, salinity, alkalinity, calcium, magnesium,
    power consumption, amperage, voltage, and digital switch states.
    """
    inputs = client.get_inputs()
    probes = [_format_probe(inp) for inp in inputs]
    return json.dumps(probes, indent=2)


@mcp.tool()
def get_probe(name: str) -> str:
    """Get a specific probe/sensor reading by name.

    Args:
        name: Probe name (e.g. Sump_t, Tank_T, Salt, ORP, Alk_KH, Cax4, Mgx4)
    """
    inp = client.get_input_by_name(name)
    if inp is None:
        return json.dumps({"error": f"Probe '{name}' not found"})
    return json.dumps(_format_probe(inp), indent=2)


@mcp.tool()
def get_water_parameters() -> str:
    """Get key water quality parameters: temperature, pH, salinity, ORP, alkalinity, calcium, magnesium.

    This is a convenience tool that filters to just the important water quality readings.
    """
    inputs = client.get_inputs()
    water_types = {"Temp", "pH", "ORP", "Cond", "alk", "ca", "mg"}
    params = [_format_probe(inp) for inp in inputs if inp.get("type") in water_types]
    return json.dumps(params, indent=2)


@mcp.tool()
def get_power_consumption() -> str:
    """Get power consumption data for all outlets (watts and amps)."""
    inputs = client.get_inputs()
    power = [_format_probe(inp) for inp in inputs if inp.get("type") in ("pwr", "Amps")]
    return json.dumps(power, indent=2)


@mcp.tool()
def get_all_outlets() -> str:
    """Get the state of all outlets/outputs on the Apex.

    Returns each outlet's name, type, current state (AON/AOF/ON/OFF/TBL), and device ID.
    """
    outputs = client.get_outputs()
    formatted = [_format_output(out) for out in outputs]
    return json.dumps(formatted, indent=2)


@mcp.tool()
def get_outlet(name: str) -> str:
    """Get a specific outlet's current state.

    Args:
        name: Outlet name (e.g. Heaters, Skimmer, ATO, Wavemakers, UV_light)
    """
    out = client.get_output_by_name(name)
    if out is None:
        return json.dumps({"error": f"Outlet '{name}' not found"})
    return json.dumps(_format_output(out), indent=2)


@mcp.tool()
def get_outlet_program(name: str) -> str:
    """Get an outlet's Apex program code.

    Args:
        name: Outlet name (e.g. Heaters, Skimmer, ATO)
    """
    oc = client.get_output_config(name)
    if oc is None:
        return json.dumps({"error": f"Outlet config for '{name}' not found"})
    return json.dumps({
        "name": oc["name"],
        "type": oc.get("type"),
        "ctype": oc.get("ctype"),
        "program": oc.get("prog", ""),
        "logging": oc.get("log", False),
        "in_use": oc.get("inuse", False),
    }, indent=2)


@mcp.tool()
def set_outlet_state(name: str, state: str) -> str:
    """Set an outlet to ON, OFF, or AUTO.

    ON = force on (override program), OFF = force off, AUTO = return to program control.

    Args:
        name: Outlet name (e.g. Heaters, Skimmer, Wavemakers)
        state: ON, OFF, or AUTO
    """
    try:
        result = client.set_output_state(name, state)
        return json.dumps({"success": True, "outlet": name, "state": state, "response": result})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to set outlet: {e}"})


@mcp.tool()
def set_outlet_program(name: str, program: str) -> str:
    """Set an outlet's Apex program.

    This overwrites the outlet's entire program. Use Apex programming syntax.
    Each line should be a separate command (e.g. "Fallback OFF\\nSet ON\\nIf Sump_t > 82.0 Then OFF").

    Args:
        name: Outlet name
        program: Full Apex program text with lines separated by newlines
    """
    try:
        result = client.set_output_program(name, program)
        return json.dumps({"success": True, "outlet": name, "response": result})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to set program: {e}"})


@mcp.tool()
def get_feed_status() -> str:
    """Get the current feed cycle status (which feed cycle is active, if any)."""
    return json.dumps(client.get_feed_status(), indent=2)


@mcp.tool()
def trigger_feed(cycle: str = "A") -> str:
    """Trigger a feed cycle on the Apex.

    Feed cycles temporarily modify outlet behavior (e.g. turn off skimmer, wavemakers).
    FeedA/B/C/D each have different durations configured per-outlet in their programs.

    Args:
        cycle: Feed cycle letter — A, B, C, or D (default: A)
    """
    try:
        result = client.trigger_feed(cycle)
        return json.dumps(result)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to trigger feed: {e}"})


@mcp.tool()
def cancel_feed() -> str:
    """Cancel the currently active feed cycle."""
    try:
        result = client.cancel_feed()
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to cancel feed: {e}"})


@mcp.tool()
def get_power_history() -> str:
    """Get the last power failure and restore timestamps."""
    from datetime import datetime, timezone

    power = client.get_power_info()
    result = {}
    if "failed" in power:
        result["last_failure"] = datetime.fromtimestamp(power["failed"], tz=timezone.utc).isoformat()
    if "restored" in power:
        result["last_restored"] = datetime.fromtimestamp(power["restored"], tz=timezone.utc).isoformat()
    return json.dumps(result, indent=2)


@mcp.tool()
def get_digital_inputs() -> str:
    """Get all digital switch/sensor states (float switches, leak detectors, buttons).

    Digital inputs read as 0 (OPEN/normal) or non-zero (CLOSED/triggered).
    """
    inputs = client.get_inputs()
    digitals = []
    for inp in inputs:
        if inp.get("type") == "digital":
            val = inp.get("value", 0)
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0
            digitals.append({
                "name": inp["name"],
                "value": val,
                "state": "CLOSED" if val != 0 else "OPEN",
            })
    return json.dumps(digitals, indent=2)


@mcp.tool()
def get_dosing_status() -> str:
    """Get status of all dosing pump outputs (DOS/DQD), including total volume dosed."""
    outputs = client.get_outputs()
    dosers = [_format_output(out) for out in outputs if out.get("type") in ("dos", "dqd")]
    return json.dumps(dosers, indent=2)


@mcp.tool()
def get_full_config() -> str:
    """Get the complete Apex configuration dump (all outputs, inputs, modules, profiles).

    Warning: This returns a large JSON payload.
    """
    config = client.get_config()
    return json.dumps(config, indent=2)


# ── Fusion Cloud Tools (manual measurements) ──────────────────────

@mcp.tool()
def get_manual_measurements(days: int = 365) -> str:
    """Get manually-logged water test measurements from Neptune Fusion cloud.

    These are tests you logged yourself (not from Trident or probes) — e.g. NO3, PO4,
    manual Alk/Ca/Mg, Salinity, pH, Ammonia, Nitrite.

    Note: First call launches a headless browser for Fusion auth (~10 seconds).

    Args:
        days: Number of days of history (default: 365)
    """
    try:
        fusion = _get_fusion()
        entries = fusion.get_measurements(days)
        return json.dumps(entries, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch Fusion measurements: {e}"})


@mcp.tool()
def get_manual_measurements_summary(days: int = 365) -> str:
    """Get a summary of manually-logged measurements grouped by parameter.

    Shows count, min, max, latest value, and date range for each parameter.

    Args:
        days: Number of days of history (default: 365)
    """
    try:
        fusion = _get_fusion()
        summary = fusion.get_measurements_summary(days)
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch Fusion summary: {e}"})


@mcp.tool()
def get_latest_manual_measurements() -> str:
    """Get the most recent manually-logged value for each water test parameter.

    Returns the latest NO3, PO4, Alk, Ca, Mg, Salinity, pH, Ammonia, Nitrite, etc.
    """
    try:
        fusion = _get_fusion()
        latest = fusion.get_latest_measurements()
        return json.dumps(latest, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch latest measurements: {e}"})


# ── HA Sync Tool ──────────────────────────────────────────────────

@mcp.tool()
def sync_measurements_to_ha() -> str:
    """Push the latest manually-logged Fusion measurements to Home Assistant as sensors.

    Creates/updates sensor entities (sensor.reef_manual_*) so they appear on HA dashboards.
    Call this after logging new water test results in Neptune Fusion.

    Requires HA_URL and HA_TOKEN environment variables.
    """
    if not HA_URL or not HA_TOKEN:
        return json.dumps({"error": "HA_URL and HA_TOKEN environment variables are required for HA sync."})

    try:
        fusion = _get_fusion()
        latest = fusion.get_latest_measurements()
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch Fusion measurements: {e}"})

    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    results = {}
    for param_name, data in latest.items():
        cfg = PARAM_HA_CONFIG.get(param_name)
        if cfg is None:
            continue
        entity_id, friendly_name, unit, icon = cfg
        payload = {
            "state": data["value"],
            "attributes": {
                "friendly_name": friendly_name,
                "unit_of_measurement": unit,
                "icon": icon,
                "device_class": "measurement",
                "state_class": "measurement",
                "last_tested": data["date"],
                "source": "Neptune Fusion (manual)",
            },
        }
        r = requests.post(f"{HA_URL}/api/states/{entity_id}", headers=headers, json=payload, timeout=10)
        results[param_name] = {"entity_id": entity_id, "value": data["value"], "ok": r.status_code in (200, 201)}

    return json.dumps({"synced": len(results), "details": results}, indent=2)


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
