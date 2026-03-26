"""Neptune Apex REST API client."""

import time
import requests


class ApexClient:
    """Client for the Neptune Apex local REST API."""

    def __init__(self, host: str, username: str, password: str, timeout: int = 10):
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self._sid: str | None = None

    def _login(self) -> None:
        """Authenticate and obtain session cookie."""
        r = self.session.post(
            f"{self.base_url}/rest/login",
            json={"login": self.username, "password": self.password, "remember_me": False},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        self._sid = data.get("connect.sid")

    def _ensure_auth(self) -> None:
        """Login if we don't have a valid session."""
        if self._sid is None:
            self._login()

    def _get(self, path: str) -> dict:
        """Authenticated GET request with auto-retry on 401."""
        self._ensure_auth()
        url = f"{self.base_url}{path}?_={int(time.time())}"
        r = self.session.get(url, timeout=self.timeout)
        if r.status_code == 401:
            self._login()
            r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, data: dict) -> dict:
        """Authenticated PUT request."""
        self._ensure_auth()
        r = self.session.put(
            f"{self.base_url}{path}",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        if r.status_code == 401:
            self._login()
            r = self.session.put(
                f"{self.base_url}{path}",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        r.raise_for_status()
        return r.json()

    # ── Read endpoints ─────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get full system status (inputs + outputs)."""
        return self._get("/rest/status")

    def get_config(self) -> dict:
        """Get full system configuration."""
        return self._get("/rest/config")

    def get_inputs(self) -> list[dict]:
        """Get all probe/sensor readings."""
        status = self.get_status()
        return status.get("inputs", [])

    def get_outputs(self) -> list[dict]:
        """Get all outlet states."""
        status = self.get_status()
        return status.get("outputs", [])

    def get_input_by_name(self, name: str) -> dict | None:
        """Get a specific probe by name (case-insensitive)."""
        for inp in self.get_inputs():
            if inp["name"].lower() == name.lower():
                return inp
        return None

    def get_output_by_name(self, name: str) -> dict | None:
        """Get a specific output by name (case-insensitive)."""
        for out in self.get_outputs():
            if out["name"].lower() == name.lower():
                return out
        return None

    def get_output_config(self, name: str) -> dict | None:
        """Get output configuration (including program) by name."""
        config = self.get_config()
        for oc in config.get("oconf", []):
            if oc["name"].lower() == name.lower():
                return oc
        return None

    def get_system_info(self) -> dict:
        """Get system info (hostname, serial, firmware, etc)."""
        status = self.get_status()
        system = status.get("system", {})
        return {
            "hostname": system.get("hostname"),
            "serial": system.get("serial"),
            "software": system.get("software"),
            "hardware": system.get("hardware"),
            "type": system.get("type"),
            "timezone": system.get("timezone"),
        }

    def get_feed_status(self) -> dict:
        """Get current feed cycle status."""
        status = self.get_status()
        feed = status.get("feed", {})
        feed_names = {0: "None", 1: "FeedA", 2: "FeedB", 3: "FeedC", 4: "FeedD"}
        return {
            "active_cycle": feed_names.get(feed.get("name", 0), f"Feed{feed.get('name')}"),
            "active": bool(feed.get("active", 0)),
        }

    def get_power_info(self) -> dict:
        """Get power failure/restore timestamps."""
        status = self.get_status()
        return status.get("power", {})

    # ── Write endpoints ────────────────────────────────────────────

    def set_output_state(self, name: str, state: str) -> dict:
        """Set an output to ON, OFF, or AUTO.

        Args:
            name: Output name (e.g. "Heaters", "Skimmer")
            state: "ON", "OFF", or "AUTO"
        """
        state = state.upper()
        if state not in ("ON", "OFF", "AUTO"):
            raise ValueError(f"Invalid state '{state}'. Must be ON, OFF, or AUTO.")

        output = self.get_output_by_name(name)
        if output is None:
            raise ValueError(f"Output '{name}' not found.")

        payload = {
            "did": output["did"],
            "status": [state, "", "OK", ""],
            "type": output["type"],
        }
        return self._put(f"/rest/status/outputs/{output['did']}", payload)

    def set_output_program(self, name: str, program: str) -> dict:
        """Set an output's Apex program.

        Args:
            name: Output name
            program: Full Apex program text (e.g. "Fallback OFF\\nSet ON\\n...")
        """
        oc = self.get_output_config(name)
        if oc is None:
            raise ValueError(f"Output config for '{name}' not found.")

        oc["prog"] = program
        return self._put(f"/rest/config/oconf/{oc['did']}", oc)

    def trigger_feed(self, cycle: str = "A") -> dict:
        """Trigger a feed cycle (A, B, C, or D)."""
        cycle = cycle.upper()
        if cycle not in ("A", "B", "C", "D"):
            raise ValueError(f"Invalid feed cycle '{cycle}'. Must be A, B, C, or D.")

        cycle_num = {"A": 1, "B": 2, "C": 3, "D": 4}[cycle]
        self._ensure_auth()
        r = self.session.post(
            f"{self.base_url}/rest/status/feed/{cycle_num}",
            json={"active": 1, "name": cycle_num},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        if r.status_code == 401:
            self._login()
            r = self.session.post(
                f"{self.base_url}/rest/status/feed/{cycle_num}",
                json={"active": 1, "name": cycle_num},
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        r.raise_for_status()
        return {"feed_cycle": f"Feed{cycle}", "triggered": True}

    def cancel_feed(self) -> dict:
        """Cancel the currently active feed cycle."""
        self._ensure_auth()
        r = self.session.post(
            f"{self.base_url}/rest/status/feed/0",
            json={"active": 0, "name": 0},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        if r.status_code == 401:
            self._login()
            r = self.session.post(
                f"{self.base_url}/rest/status/feed/0",
                json={"active": 0, "name": 0},
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        r.raise_for_status()
        return {"feed_cycle": "None", "cancelled": True}
