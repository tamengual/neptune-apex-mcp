# Neptune Apex MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for the **Neptune Systems Apex** aquarium controller. Gives AI assistants like Claude full read/write access to your Apex — probe readings, outlet control, program editing, feed cycles, and more.

Optionally integrates with **Neptune Fusion** cloud for manual water test history, and **Home Assistant** for syncing measurements as sensor entities.

## Features

### Local Apex Control (via REST API)
- Read all probe/sensor values (temperature, pH, ORP, salinity, alkalinity, calcium, magnesium, power, digital inputs)
- Read and set outlet states (ON / OFF / AUTO)
- Read and write outlet programs (full Apex programming language)
- Trigger and cancel feed cycles (A/B/C/D)
- Get system info, power history, dosing pump status
- Full configuration dump

### Neptune Fusion Cloud (optional)
- Fetch manually-logged water test measurements (NO3, PO4, Alk, Ca, Mg, Salinity, pH, Ammonia, Nitrite)
- Measurement summaries and latest values
- Uses Playwright headless browser for auth (Neptune doesn't offer a public API)

### Home Assistant Integration (optional)
- Push Fusion manual measurements to HA as sensor entities
- Standalone sync script for scheduled runs

## Requirements

- Python 3.11+
- A Neptune Apex controller on your local network
- `pip install -r requirements.txt`
- For Fusion features: `playwright install chromium`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium  # only needed for Fusion cloud features
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `APEX_HOST` | Yes | IP address of your Apex controller |
| `APEX_USER` | Yes | Apex local login username |
| `APEX_PASS` | Yes | Apex local login password |
| `FUSION_USER` | No | Neptune Fusion username (defaults to APEX_USER) |
| `FUSION_PASS` | No | Neptune Fusion password (defaults to APEX_PASS) |
| `FUSION_APEX_ID` | No | Your Apex ID from the Fusion URL (`https://apexfusion.com/apex/<ID>`) |
| `HA_URL` | No | Home Assistant URL (e.g. `http://192.168.1.100:8123`) |
| `HA_TOKEN` | No | Home Assistant long-lived access token |

### 3. Add to your MCP client

#### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "neptune-apex": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/neptune-apex-mcp/server.py"],
      "env": {
        "APEX_HOST": "192.168.1.100",
        "APEX_USER": "admin",
        "APEX_PASS": "your_password"
      }
    }
  }
}
```

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "neptune-apex": {
      "command": "python3",
      "args": ["/path/to/neptune-apex-mcp/server.py"],
      "env": {
        "APEX_HOST": "192.168.1.100",
        "APEX_USER": "admin",
        "APEX_PASS": "your_password"
      }
    }
  }
}
```

## Available Tools

### Probes & Sensors
| Tool | Description |
|------|-------------|
| `get_all_probes` | All probe readings (temp, pH, ORP, salinity, amps, watts, digital switches) |
| `get_probe` | Single probe by name |
| `get_water_parameters` | Key water quality params only (temp, pH, ORP, salinity, alk, ca, mg) |
| `get_power_consumption` | Power draw per outlet (watts and amps) |
| `get_digital_inputs` | Float switches, leak detectors, buttons |

### Outlets & Programs
| Tool | Description |
|------|-------------|
| `get_all_outlets` | All outlet states |
| `get_outlet` | Single outlet state |
| `get_outlet_program` | Read an outlet's Apex program |
| `set_outlet_state` | Set outlet to ON, OFF, or AUTO |
| `set_outlet_program` | Write a new Apex program to an outlet |

### Feed & System
| Tool | Description |
|------|-------------|
| `trigger_feed` | Start a feed cycle (A/B/C/D) |
| `cancel_feed` | Cancel active feed cycle |
| `get_feed_status` | Check if a feed cycle is active |
| `get_system_info` | Hostname, firmware, serial |
| `get_power_history` | Last power failure/restore timestamps |
| `get_dosing_status` | DOS/DQD pump volumes |
| `get_full_config` | Complete configuration dump |

### Fusion Cloud (optional)
| Tool | Description |
|------|-------------|
| `get_manual_measurements` | Manual water test history from Fusion |
| `get_manual_measurements_summary` | Summary stats per parameter |
| `get_latest_manual_measurements` | Most recent value per parameter |
| `sync_measurements_to_ha` | Push measurements to Home Assistant |

## Standalone Fusion-to-HA Sync

For scheduled syncing (e.g. every 6 hours), run the standalone script:

```bash
export FUSION_USER=your_user FUSION_PASS=your_pass FUSION_APEX_ID=your_id
export HA_URL=http://192.168.1.100:8123 HA_TOKEN=your_token
python3 sync_fusion_to_ha.py
```

This creates/updates `sensor.reef_manual_*` entities in Home Assistant.

## Compatibility

Tested with:
- Neptune Apex A3 (firmware 5.x)
- Neptune Fusion cloud (as of 2025)
- Python 3.11, 3.12, 3.13
- Claude Code, Claude Desktop

Should work with any Apex model that has the local REST API (Apex, Apex EL, Apex Jr with network module).

## License

MIT
