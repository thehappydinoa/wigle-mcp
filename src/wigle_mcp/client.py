"""Thin async client for the WiGLE.net v2 API.

Credentials are read from the WIGLE_API_NAME / WIGLE_API_TOKEN env vars, or
from ~/.config/wigle-mcp/config.json (keys "api_name" / "api_token"). The
same env var names used by flockdar's WiGLEEnricher are supported so a single
WiGLE account can be shared across tools.
"""

from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from wigle_mcp import __version__

WIGLE_BASE = "https://api.wigle.net/api/v2"
USER_AGENT = f"wigle-mcp/{__version__}"

# Shared connection pool: reused across tool calls so repeated lookups avoid
# re-doing DNS/TLS handshakes.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


class WigleAuthError(RuntimeError):
    """Raised when no WiGLE API credentials are configured."""


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "wigle-mcp" / "config.json"


@lru_cache(maxsize=1)
def _load_credentials() -> tuple[str, str]:
    name = os.environ.get("WIGLE_API_NAME", "")
    token = os.environ.get("WIGLE_API_TOKEN", "")
    if name and token:
        return name, token

    path = _config_path()
    if path.is_file():
        try:
            cfg = json.loads(path.read_text())
        except (OSError, ValueError):
            cfg = {}
        name = name or cfg.get("api_name", "")
        token = token or cfg.get("api_token", "")

    if not name or not token:
        raise WigleAuthError(
            "No WiGLE API credentials found. Set WIGLE_API_NAME and "
            "WIGLE_API_TOKEN env vars, or create "
            f'{path} with {{"api_name": ..., "api_token": ...}}. '
            "Get a free API key at https://wigle.net/account"
        )
    return name, token


class WigleClient:
    """Async client wrapping the handful of WiGLE v2 endpoints we need."""

    def __init__(self) -> None:
        name, token = _load_credentials()
        cred = base64.b64encode(f"{name}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {cred}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        client = _get_http_client()
        resp = await client.get(f"{WIGLE_BASE}/{path}", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def network_search(self, **params: Any) -> dict[str, Any]:
        return await self._get("network/search", params)

    async def network_detail(self, netid: str) -> dict[str, Any]:
        return await self._get("network/detail", {"netid": netid})

    async def stats_user(self) -> dict[str, Any]:
        return await self._get("stats/user", {})

    async def stats_general(self) -> dict[str, Any]:
        return await self._get("stats/general", {})

    async def bluetooth_search(self, **params: Any) -> dict[str, Any]:
        return await self._get("bluetooth/search", params)

    async def bluetooth_detail(self, netid: str) -> dict[str, Any]:
        return await self._get("bluetooth/detail", {"netid": netid})

    async def cell_search(self, **params: Any) -> dict[str, Any]:
        return await self._get("cell/search", params)

    async def cell_detail(self, netid: str) -> dict[str, Any]:
        return await self._get("cell/detail", {"netid": netid})
