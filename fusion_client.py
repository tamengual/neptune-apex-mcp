"""Neptune Fusion cloud API client.

Uses requests with CSRF token authentication.
"""

import re
import time

import requests


class FusionClient:
    """Client for the Neptune Fusion cloud API (apexfusion.com)."""

    FUSION_URL = "https://apexfusion.com"
    TYPE_MAP = {0: "Custom", 1: "Alkalinity", 2: "Calcium", 3: "Iodine",
                4: "Magnesium", 5: "Nitrate", 6: "Phosphate"}

    def __init__(self, username: str, password: str, apex_id: str):
        self.username = username
        self.password = password
        self.apex_id = apex_id
        self.session = requests.Session()
        self._logged_in = False

    def _login(self) -> None:
        """Authenticate via CSRF token + POST to /login."""
        r = self.session.get(f"{self.FUSION_URL}/login", timeout=15)
        r.raise_for_status()
        match = re.search(r'csrf-token"\s+content="([^"]+)"', r.text)
        if not match:
            raise RuntimeError("Could not find CSRF token on Fusion login page")
        csrf = match.group(1)

        r = self.session.post(
            f"{self.FUSION_URL}/login",
            json={"username": self.username, "password": self.password},
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if "username" not in data:
            raise RuntimeError(f"Fusion login failed: {data}")
        self._logged_in = True

    def _ensure_auth(self) -> None:
        if not self._logged_in:
            self._login()

    def _get(self, path: str) -> list | dict:
        """Authenticated GET to a Fusion API endpoint."""
        self._ensure_auth()
        url = f"{self.FUSION_URL}/api/apex/{self.apex_id}{path}"
        sep = "&" if "?" in path else "?"
        url += f"{sep}_={int(time.time())}"
        r = self.session.get(
            url,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15,
        )
        if r.status_code == 401:
            self._logged_in = False
            self._ensure_auth()
            r = self.session.get(
                url,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=15,
            )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        """Clean up session."""
        self.session.close()
        self._logged_in = False

    # ── API methods ────────────────────────────────────────────────

    def get_measurements(self, days: int = 365) -> list[dict]:
        """Get manual measurement log entries."""
        raw = self._get(f"/mlog?days={days}")
        results = []
        for entry in raw:
            mtype = entry.get("type", 0)
            results.append({
                "date": entry["date"],
                "parameter": entry.get("name") if mtype == 0 else self.TYPE_MAP.get(mtype, f"type_{mtype}"),
                "value": entry.get("value"),
                "type_code": mtype,
                "note": entry.get("text", ""),
            })
        return results

    def get_measurements_summary(self, days: int = 365) -> dict:
        """Get a summary of manual measurements grouped by parameter."""
        entries = self.get_measurements(days)
        summary = {}
        for entry in entries:
            param = entry["parameter"]
            if param not in summary:
                summary[param] = {
                    "count": 0,
                    "values": [],
                    "first_date": entry["date"],
                    "last_date": entry["date"],
                }
            summary[param]["count"] += 1
            summary[param]["values"].append(entry["value"])
            summary[param]["last_date"] = entry["date"]

        for param, data in summary.items():
            vals = data["values"]
            data["min"] = min(vals)
            data["max"] = max(vals)
            data["latest"] = vals[-1]
            del data["values"]

        return summary

    def get_latest_measurements(self) -> dict:
        """Get the most recent value for each manually-logged parameter."""
        entries = self.get_measurements(days=90)
        latest = {}
        for entry in entries:
            param = entry["parameter"]
            latest[param] = {
                "value": entry["value"],
                "date": entry["date"],
            }
        return latest

    def get_alarm_log(self, date: str, page: int = 1, per_page: int = 50) -> dict:
        """Get alarm log entries for a specific date.

        Args:
            date: ISO date string (e.g. "2026-07-05T04:00:00.000Z")
            page: Page number (default: 1)
            per_page: Results per page (default: 50)

        Returns:
            Dict with "total_entries" and "entries" list.
        """
        raw = self._get(f"/alog?date={date}&page={page}&per_page={per_page}")
        return {
            "total_entries": raw[0]["total_entries"],
            "entries": raw[1],
        }
