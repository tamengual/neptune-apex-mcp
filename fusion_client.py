"""Neptune Fusion cloud API client.

Uses Playwright headless browser for authentication (Neptune blocks
programmatic login) then fetches data via in-page JavaScript fetch().
"""

import json
import time

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class FusionClient:
    """Client for the Neptune Fusion cloud API (apexfusion.com)."""

    FUSION_URL = "https://apexfusion.com"
    TYPE_MAP = {0: "Custom", 1: "Alkalinity", 2: "Calcium", 3: "Iodine",
                4: "Magnesium", 5: "Nitrate", 6: "Phosphate"}

    def __init__(self, username: str, password: str, apex_id: str):
        self.username = username
        self.password = password
        self.apex_id = apex_id
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._logged_in = False

    def _ensure_browser(self) -> None:
        """Launch browser and log in if needed."""
        if self._page is not None and self._logged_in:
            return

        if self._playwright is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)

        if self._context is None:
            self._context = self._browser.new_context()

        if self._page is None:
            self._page = self._context.new_page()

        self._login()

    def _login(self) -> None:
        """Log into Fusion via the browser."""
        self._page.goto(f"{self.FUSION_URL}/login")
        self._page.wait_for_selector("#index-login-username", timeout=15000)
        self._page.fill("#index-login-username", self.username)
        self._page.fill("#index-login-password", self.password)
        self._page.click('button[type="submit"]')
        self._page.wait_for_timeout(3000)
        self._logged_in = True

    def _fetch_json(self, path: str) -> list | dict:
        """Fetch a Fusion API endpoint from within the authenticated page context."""
        self._ensure_browser()
        url = f"/api/apex/{self.apex_id}{path}"
        result = self._page.evaluate(
            """(url) => fetch(url, {
                credentials: 'include',
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }).then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.text();
            })""",
            url,
        )
        if not result or result.startswith("<!"):
            self._logged_in = False
            self._ensure_browser()
            result = self._page.evaluate(
                """(url) => fetch(url, {
                    credentials: 'include',
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                }).then(r => {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.text();
                })""",
                url,
            )
        return json.loads(result)

    def close(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._logged_in = False

    # ── API methods ────────────────────────────────────────────────

    def get_measurements(self, days: int = 365) -> list[dict]:
        """Get manual measurement log entries.

        Args:
            days: Number of days of history to fetch (default: 365)

        Returns:
            List of measurement entries with date, type, name, value.
        """
        raw = self._fetch_json(f"/mlog?days={days}")
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
