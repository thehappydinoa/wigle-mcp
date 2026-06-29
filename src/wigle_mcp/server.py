"""MCP server exposing WiGLE.net wardriving lookups as tools."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.lifespan import lifespan
from pydantic import Field

from wigle_mcp import __version__
from wigle_mcp.client import WigleAuthError, WigleClient
from wigle_mcp.transform import DeviceKind, summarize_result
from wigle_mcp.validation import require_search_filter, validate_bounding_box

SERVER_INSTRUCTIONS = """\
WiGLE exposes wardriving data with strict per-account daily query limits \
(reset midnight US/Pacific; new accounts start with very low limits).

Query etiquette:
- Prefer one bounded *_search over many *_detail calls.
- Always pass at least one search filter; unfiltered searches waste quota.
- To fetch more results, STRONGLY prefer passing search_after from the prior \
response's searchAfter field. search_after alone is valid for pagination and \
avoids repeating filters or re-running the same query from scratch.
- Keep results_per_page low unless the user explicitly needs more.
- *_detail omits sighting locations by default; pass include_locations=true only when needed.
"""

SEARCH_AFTER_FIELD = (
    "Pagination cursor from a previous response's searchAfter field. "
    "STRONGLY PREFERRED for additional pages: pass this alone to continue the "
    "same query without repeating filters."
)

READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
}

RATE_LIMIT_MESSAGE = (
    "WiGLE daily query limit reached. Limits reset at midnight US/Pacific. "
    "Prefer *_search over many *_detail calls, reuse search_after for pagination, "
    "and keep results_per_page low."
)


def _http_status_to_tool_error(exc: httpx.HTTPStatusError) -> ToolError:
    code = exc.response.status_code
    if code == 429:
        return ToolError(RATE_LIMIT_MESSAGE)
    if code == 401:
        return ToolError("WiGLE authentication failed. Check WIGLE_API_NAME and WIGLE_API_TOKEN.")
    if code == 403:
        return ToolError(f"WiGLE access denied (403): {exc.response.text[:200]}")
    return ToolError(f"WiGLE API error {code}: {exc.response.text[:500]}")


async def _invoke(coro: Awaitable[Any]) -> Any:
    try:
        return await coro
    except WigleAuthError as exc:
        raise ToolError(str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _http_status_to_tool_error(exc) from exc
    except httpx.HTTPError as exc:
        raise ToolError(f"Request to WiGLE failed: {exc}") from exc


async def _verify_credentials() -> None:
    client = WigleClient()
    await client.stats_user()


@lifespan
async def _startup_lifespan(server: FastMCP[Any]):
    await _invoke(_verify_credentials())
    yield {}


mcp = FastMCP(
    "wigle-mcp",
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
    lifespan=_startup_lifespan,
)


async def _search(
    kind: DeviceKind,
    client_method: str,
    **params: Any,
) -> dict[str, Any]:
    async def _do() -> dict[str, Any]:
        client = WigleClient()
        data = await getattr(client, client_method)(**params)
        results = data.get("results", [])
        return {
            "success": data.get("success"),
            "totalResults": data.get("totalResults"),
            "resultCount": len(results),
            "searchAfter": data.get("search_after"),
            "results": [summarize_result(r, kind=kind) for r in results],
        }

    return await _invoke(_do())


async def _detail(
    kind: DeviceKind,
    client_method: str,
    netid: str,
    *,
    include_locations: bool,
) -> dict[str, Any]:
    async def _do() -> dict[str, Any]:
        client = WigleClient()
        data = await getattr(client, client_method)(netid)
        results = data.get("results", [])
        if not results:
            return {"success": data.get("success"), "found": False, "results": []}
        return {
            "success": data.get("success"),
            "found": True,
            "results": [summarize_result(r, kind=kind, include_locations=include_locations) for r in results],
        }

    return await _invoke(_do())


@mcp.tool(annotations=READ_ONLY)
async def network_search(
    ssid: Annotated[str | None, Field(description="Exact SSID to match")] = None,
    ssid_like: Annotated[str | None, Field(description="SQL LIKE pattern for SSID, e.g. 'Pretty Fly%'")] = None,
    bssid: Annotated[str | None, Field(description="MAC address / BSSID to match, e.g. 'AA:BB:CC:DD:EE:FF'")] = None,
    lat_min: Annotated[float | None, Field(description="Minimum latitude of bounding box")] = None,
    lat_max: Annotated[float | None, Field(description="Maximum latitude of bounding box")] = None,
    long_min: Annotated[float | None, Field(description="Minimum longitude of bounding box")] = None,
    long_max: Annotated[float | None, Field(description="Maximum longitude of bounding box")] = None,
    country: Annotated[str | None, Field(description="Two-letter country code, e.g. 'US'")] = None,
    region: Annotated[str | None, Field(description="State/region name")] = None,
    city: Annotated[str | None, Field(description="City name")] = None,
    only_open: Annotated[bool | None, Field(description="If true, only return networks with no encryption")] = None,
    encryption: Annotated[str | None, Field(description="Encryption filter, e.g. 'wpa', 'wpa2', 'wep', 'none'")] = None,
    results_per_page: Annotated[int, Field(description="Max results to return (1-100)", ge=1, le=100)] = 25,
    search_after: Annotated[str | None, Field(description=SEARCH_AFTER_FIELD)] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed WiFi networks by SSID, BSSID, location, or encryption.

    For additional pages, pass search_after from the prior response's searchAfter field.
    """
    validate_bounding_box(lat_min, lat_max, long_min, long_max)
    require_search_filter(
        "network_search",
        ssid=ssid,
        ssid_like=ssid_like,
        bssid=bssid,
        lat_min=lat_min,
        country=country,
        region=region,
        city=city,
        only_open=only_open,
        encryption=encryption,
        search_after=search_after,
    )
    return await _search(
        "wifi",
        "network_search",
        ssid=ssid,
        ssidlike=ssid_like,
        netid=bssid,
        latrange1=lat_min,
        latrange2=lat_max,
        longrange1=long_min,
        longrange2=long_max,
        country=country,
        region=region,
        city=city,
        freenet="true" if only_open else None,
        encryption=encryption,
        resultsPerPage=results_per_page,
        searchAfter=search_after,
    )


@mcp.tool(annotations=READ_ONLY)
async def network_detail(
    bssid: Annotated[str, Field(description="MAC address / BSSID to look up, e.g. 'AA:BB:CC:DD:EE:FF'")],
    include_locations: Annotated[
        bool, Field(description="Include capped sighting location history in the response")
    ] = False,
) -> dict[str, Any]:
    """Look up a single WiFi network by BSSID, including SSID history and encryption."""
    return await _detail("wifi", "network_detail", bssid, include_locations=include_locations)


@mcp.tool(annotations=READ_ONLY)
async def user_stats() -> dict[str, Any]:
    """Get WiGLE account statistics for the configured API user: rank,
    monthly rank, and counts of discovered WiFi/cell networks."""
    return await _invoke(WigleClient().stats_user())


@mcp.tool(annotations=READ_ONLY)
async def site_stats() -> dict[str, Any]:
    """Get WiGLE-wide statistics: total WiFi/cell/Bluetooth networks and
    locations recorded, total users, and recent daily/monthly upload totals."""
    return await _invoke(WigleClient().stats_general())


@mcp.tool(annotations=READ_ONLY)
async def bluetooth_search(
    name: Annotated[str | None, Field(description="Exact device name to match")] = None,
    name_like: Annotated[str | None, Field(description="SQL LIKE pattern for device name, e.g. 'Galaxy%'")] = None,
    bssid: Annotated[str | None, Field(description="MAC address to match, e.g. 'AA:BB:CC:DD:EE:FF'")] = None,
    lat_min: Annotated[float | None, Field(description="Minimum latitude of bounding box")] = None,
    lat_max: Annotated[float | None, Field(description="Maximum latitude of bounding box")] = None,
    long_min: Annotated[float | None, Field(description="Minimum longitude of bounding box")] = None,
    long_max: Annotated[float | None, Field(description="Maximum longitude of bounding box")] = None,
    results_per_page: Annotated[int, Field(description="Max results to return (1-100)", ge=1, le=100)] = 25,
    search_after: Annotated[str | None, Field(description=SEARCH_AFTER_FIELD)] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed Bluetooth/BLE devices by name, MAC, or location.

    For additional pages, pass search_after from the prior response's searchAfter field.
    """
    validate_bounding_box(lat_min, lat_max, long_min, long_max)
    require_search_filter(
        "bluetooth_search",
        name=name,
        name_like=name_like,
        bssid=bssid,
        lat_min=lat_min,
        search_after=search_after,
    )
    return await _search(
        "bluetooth",
        "bluetooth_search",
        name=name,
        namelike=name_like,
        netid=bssid,
        latrange1=lat_min,
        latrange2=lat_max,
        longrange1=long_min,
        longrange2=long_max,
        resultsPerPage=results_per_page,
        searchAfter=search_after,
    )


@mcp.tool(annotations=READ_ONLY)
async def bluetooth_detail(
    bssid: Annotated[str, Field(description="MAC address to look up, e.g. 'AA:BB:CC:DD:EE:FF'")],
    include_locations: Annotated[
        bool, Field(description="Include capped sighting location history in the response")
    ] = False,
) -> dict[str, Any]:
    """Look up a single Bluetooth/BLE device by MAC address, including name history."""
    return await _detail("bluetooth", "bluetooth_detail", bssid, include_locations=include_locations)


@mcp.tool(annotations=READ_ONLY)
async def cell_search(
    netid: Annotated[
        str | None,
        Field(description="Cell tower identifier to match, e.g. '310-410-12345-6789'"),
    ] = None,
    operator: Annotated[str | None, Field(description="Carrier/operator name to match")] = None,
    network_type: Annotated[
        str | None, Field(description="Network type filter, e.g. 'GSM', 'UMTS', 'LTE', 'CDMA'")
    ] = None,
    lat_min: Annotated[float | None, Field(description="Minimum latitude of bounding box")] = None,
    lat_max: Annotated[float | None, Field(description="Maximum latitude of bounding box")] = None,
    long_min: Annotated[float | None, Field(description="Minimum longitude of bounding box")] = None,
    long_max: Annotated[float | None, Field(description="Maximum longitude of bounding box")] = None,
    results_per_page: Annotated[int, Field(description="Max results to return (1-100)", ge=1, le=100)] = 25,
    search_after: Annotated[str | None, Field(description=SEARCH_AFTER_FIELD)] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed cell towers by ID, operator, network type, or location.

    For additional pages, pass search_after from the prior response's searchAfter field.
    """
    validate_bounding_box(lat_min, lat_max, long_min, long_max)
    require_search_filter(
        "cell_search",
        netid=netid,
        operator=operator,
        network_type=network_type,
        lat_min=lat_min,
        search_after=search_after,
    )
    return await _search(
        "cell",
        "cell_search",
        netid=netid,
        operator=operator,
        networkType=network_type,
        latrange1=lat_min,
        latrange2=lat_max,
        longrange1=long_min,
        longrange2=long_max,
        resultsPerPage=results_per_page,
        searchAfter=search_after,
    )


@mcp.tool(annotations=READ_ONLY)
async def cell_detail(
    netid: Annotated[str, Field(description="Cell tower identifier to look up, e.g. '310-410-12345-6789'")],
    include_locations: Annotated[
        bool, Field(description="Include capped sighting location history in the response")
    ] = False,
) -> dict[str, Any]:
    """Look up a single cell tower by ID, including operator/network type."""
    return await _detail("cell", "cell_detail", netid, include_locations=include_locations)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
