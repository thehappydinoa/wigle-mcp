"""MCP server exposing WiGLE.net wardriving lookups as tools."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from pydantic import Field

from wigle_mcp.client import WigleClient, WigleAuthError

mcp = FastMCP("wigle-mcp")

MAX_LOCATIONS = 5


async def _call(coro: Any) -> dict[str, Any]:
    try:
        return await coro
    except WigleAuthError as exc:
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        return {"error": f"WiGLE API error {exc.response.status_code}: {exc.response.text[:500]}"}
    except httpx.HTTPError as exc:
        return {"error": f"Request to WiGLE failed: {exc}"}


def _trim_network(net: dict[str, Any]) -> dict[str, Any]:
    """Drop noisy fields and cap location history for a network record."""
    trimmed = dict(net)
    locations = trimmed.get("locationData")
    if isinstance(locations, list) and len(locations) > MAX_LOCATIONS:
        trimmed["locationData"] = locations[:MAX_LOCATIONS]
        trimmed["locationDataTruncated"] = True
        trimmed["locationDataTotal"] = len(locations)
    return trimmed


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def network_search(
    ssid: Annotated[str | None, Field(description="Exact SSID to match")] = None,
    ssid_like: Annotated[
        str | None, Field(description="SQL LIKE pattern for SSID, e.g. 'Pretty Fly%'")
    ] = None,
    bssid: Annotated[
        str | None, Field(description="MAC address / BSSID to match, e.g. 'AA:BB:CC:DD:EE:FF'")
    ] = None,
    lat_min: Annotated[float | None, Field(description="Minimum latitude of bounding box")] = None,
    lat_max: Annotated[float | None, Field(description="Maximum latitude of bounding box")] = None,
    long_min: Annotated[float | None, Field(description="Minimum longitude of bounding box")] = None,
    long_max: Annotated[float | None, Field(description="Maximum longitude of bounding box")] = None,
    country: Annotated[str | None, Field(description="Two-letter country code, e.g. 'US'")] = None,
    region: Annotated[str | None, Field(description="State/region name")] = None,
    city: Annotated[str | None, Field(description="City name")] = None,
    only_open: Annotated[
        bool | None, Field(description="If true, only return networks with no encryption")
    ] = None,
    encryption: Annotated[
        str | None, Field(description="Encryption filter, e.g. 'wpa', 'wpa2', 'wep', 'none'")
    ] = None,
    results_per_page: Annotated[
        int, Field(description="Max results to return (1-100)", ge=1, le=100)
    ] = 25,
    search_after: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous response's 'search_after' field"),
    ] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed WiFi networks by SSID, BSSID, location, or encryption."""
    return await _call(
        _network_search(
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
    )


async def _network_search(**params: Any) -> dict[str, Any]:
    client = WigleClient()
    data = await client.network_search(**params)
    results = data.get("results", [])
    return {
        "success": data.get("success"),
        "totalResults": data.get("totalResults"),
        "resultCount": len(results),
        "searchAfter": data.get("search_after"),
        "results": [_trim_network(r) for r in results],
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def network_detail(
    bssid: Annotated[str, Field(description="MAC address / BSSID to look up, e.g. 'AA:BB:CC:DD:EE:FF'")],
) -> dict[str, Any]:
    """Look up everything WiGLE knows about a single network by its BSSID, including
    SSID history, encryption, and recorded sighting locations."""
    return await _call(_network_detail(bssid))


async def _network_detail(bssid: str) -> dict[str, Any]:
    client = WigleClient()
    data = await client.network_detail(bssid)
    results = data.get("results", [])
    if not results:
        return {"success": data.get("success"), "found": False, "results": []}
    return {
        "success": data.get("success"),
        "found": True,
        "results": [_trim_network(r) for r in results],
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def user_stats() -> dict[str, Any]:
    """Get WiGLE account statistics for the configured API user: rank,
    monthly rank, and counts of discovered WiFi/cell networks."""
    return await _call(_stats_user())


async def _stats_user() -> dict[str, Any]:
    client = WigleClient()
    return await client.stats_user()


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def site_stats() -> dict[str, Any]:
    """Get WiGLE-wide statistics: total WiFi/cell/Bluetooth networks and
    locations recorded, total users, and recent daily/monthly upload totals."""
    return await _call(_stats_general())


async def _stats_general() -> dict[str, Any]:
    client = WigleClient()
    return await client.stats_general()


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def bluetooth_search(
    name: Annotated[str | None, Field(description="Exact device name to match")] = None,
    name_like: Annotated[
        str | None, Field(description="SQL LIKE pattern for device name, e.g. 'Galaxy%'")
    ] = None,
    bssid: Annotated[
        str | None, Field(description="MAC address to match, e.g. 'AA:BB:CC:DD:EE:FF'")
    ] = None,
    lat_min: Annotated[float | None, Field(description="Minimum latitude of bounding box")] = None,
    lat_max: Annotated[float | None, Field(description="Maximum latitude of bounding box")] = None,
    long_min: Annotated[float | None, Field(description="Minimum longitude of bounding box")] = None,
    long_max: Annotated[float | None, Field(description="Maximum longitude of bounding box")] = None,
    results_per_page: Annotated[
        int, Field(description="Max results to return (1-100)", ge=1, le=100)
    ] = 25,
    search_after: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous response's 'search_after' field"),
    ] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed Bluetooth/BLE devices by name, MAC, or location."""
    return await _call(
        _bluetooth_search(
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
    )


async def _bluetooth_search(**params: Any) -> dict[str, Any]:
    client = WigleClient()
    data = await client.bluetooth_search(**params)
    results = data.get("results", [])
    return {
        "success": data.get("success"),
        "totalResults": data.get("totalResults"),
        "resultCount": len(results),
        "searchAfter": data.get("search_after"),
        "results": [_trim_network(r) for r in results],
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def bluetooth_detail(
    bssid: Annotated[str, Field(description="MAC address to look up, e.g. 'AA:BB:CC:DD:EE:FF'")],
) -> dict[str, Any]:
    """Look up everything WiGLE knows about a single Bluetooth/BLE device by its MAC address,
    including name history and recorded sighting locations."""
    return await _call(_bluetooth_detail(bssid))


async def _bluetooth_detail(bssid: str) -> dict[str, Any]:
    client = WigleClient()
    data = await client.bluetooth_detail(bssid)
    results = data.get("results", [])
    if not results:
        return {"success": data.get("success"), "found": False, "results": []}
    return {
        "success": data.get("success"),
        "found": True,
        "results": [_trim_network(r) for r in results],
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
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
    results_per_page: Annotated[
        int, Field(description="Max results to return (1-100)", ge=1, le=100)
    ] = 25,
    search_after: Annotated[
        str | None,
        Field(description="Pagination cursor from a previous response's 'search_after' field"),
    ] = None,
) -> dict[str, Any]:
    """Search WiGLE's database of observed cell towers by ID, operator, network type, or location."""
    return await _call(
        _cell_search(
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
    )


async def _cell_search(**params: Any) -> dict[str, Any]:
    client = WigleClient()
    data = await client.cell_search(**params)
    results = data.get("results", [])
    return {
        "success": data.get("success"),
        "totalResults": data.get("totalResults"),
        "resultCount": len(results),
        "searchAfter": data.get("search_after"),
        "results": [_trim_network(r) for r in results],
    }


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
async def cell_detail(
    netid: Annotated[
        str, Field(description="Cell tower identifier to look up, e.g. '310-410-12345-6789'")
    ],
) -> dict[str, Any]:
    """Look up everything WiGLE knows about a single cell tower by its ID, including
    operator/network type and recorded sighting locations."""
    return await _call(_cell_detail(netid))


async def _cell_detail(netid: str) -> dict[str, Any]:
    client = WigleClient()
    data = await client.cell_detail(netid)
    results = data.get("results", [])
    if not results:
        return {"success": data.get("success"), "found": False, "results": []}
    return {
        "success": data.get("success"),
        "found": True,
        "results": [_trim_network(r) for r in results],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
