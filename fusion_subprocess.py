"""Subprocess wrapper for FusionClient.

Standalone script for testing or calling Fusion outside the MCP server.

Usage:
    python fusion_subprocess.py <command> [args]

Commands:
    measurements [days]     — get_measurements(days)
    summary [days]          — get_measurements_summary(days)
    latest                  — get_latest_measurements()
    alog [date]             — get_alarm_log(date)

Output: JSON on stdout. Errors exit non-zero with JSON {"error": "..."}.
"""

import json
import os
import sys
from datetime import datetime, timezone

from fusion_client import FusionClient

FUSION_USER = os.environ.get("FUSION_USER", "")
FUSION_PASS = os.environ.get("FUSION_PASS", "")
FUSION_APEX_ID = os.environ.get("FUSION_APEX_ID", "")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fusion_subprocess.py <command> [args]"}))
        sys.exit(1)

    if not FUSION_USER or not FUSION_PASS or not FUSION_APEX_ID:
        print(json.dumps({"error": "FUSION_USER, FUSION_PASS, and FUSION_APEX_ID env vars required"}))
        sys.exit(1)

    command = sys.argv[1]
    client = FusionClient(FUSION_USER, FUSION_PASS, FUSION_APEX_ID)

    try:
        if command == "measurements":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
            result = client.get_measurements(days)
        elif command == "summary":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
            result = client.get_measurements_summary(days)
        elif command == "latest":
            result = client.get_latest_measurements()
        elif command == "alog":
            date = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone.utc).strftime("%Y-%m-%dT04:00:00.000Z")
            result = client.get_alarm_log(date)
        else:
            print(json.dumps({"error": f"Unknown command: {command}"}))
            sys.exit(1)

        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
