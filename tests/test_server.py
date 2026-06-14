import httpx
import pytest
import respx

from wigle_mcp import client as wigle_client
from wigle_mcp.server import (
    bluetooth_detail,
    bluetooth_search,
    cell_detail,
    cell_search,
    network_detail,
    network_search,
    site_stats,
    user_stats,
)


def _network_result(**overrides):
    base = {
        "netid": "AA:BB:CC:DD:EE:FF",
        "ssid": "test-network",
        "encryption": "wpa2",
        "locationData": [{"latitude": float(i), "longitude": float(i)} for i in range(10)],
    }
    base.update(overrides)
    return base


@respx.mock
async def test_network_search_trims_locations_and_shapes_response():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "totalResults": 1,
                "search_after": "cursor123",
                "results": [_network_result()],
            },
        )
    )

    result = await network_search(ssid="test-network")

    assert result["success"] is True
    assert result["totalResults"] == 1
    assert result["resultCount"] == 1
    assert result["searchAfter"] == "cursor123"
    net = result["results"][0]
    assert len(net["locationData"]) == 5
    assert net["locationDataTruncated"] is True
    assert net["locationDataTotal"] == 10


@respx.mock
async def test_network_detail_not_found():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    result = await network_detail(bssid="AA:BB:CC:DD:EE:FF")

    assert result == {"success": True, "found": False, "results": []}


@respx.mock
async def test_network_detail_found():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": [_network_result()]})
    )

    result = await network_detail(bssid="AA:BB:CC:DD:EE:FF")

    assert result["found"] is True
    assert result["results"][0]["ssid"] == "test-network"


@respx.mock
@pytest.mark.parametrize(
    ("tool", "path"),
    [
        (bluetooth_search, "bluetooth/search"),
        (cell_search, "cell/search"),
    ],
)
async def test_search_tools_shape_response(tool, path):
    respx.get(f"{wigle_client.WIGLE_BASE}/{path}").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "totalResults": 1, "results": [_network_result()]},
        )
    )

    result = await tool()

    assert result["success"] is True
    assert result["resultCount"] == 1
    assert result["results"][0]["locationDataTruncated"] is True


@respx.mock
@pytest.mark.parametrize(
    ("tool", "path"),
    [
        (bluetooth_detail, "bluetooth/detail"),
        (cell_detail, "cell/detail"),
    ],
)
async def test_detail_tools_not_found(tool, path):
    respx.get(f"{wigle_client.WIGLE_BASE}/{path}").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    result = await tool("some-id")

    assert result == {"success": True, "found": False, "results": []}


@respx.mock
async def test_user_stats_passthrough():
    respx.get(f"{wigle_client.WIGLE_BASE}/stats/user").mock(
        return_value=httpx.Response(200, json={"success": True, "statistics": {"rank": 1}})
    )

    result = await user_stats()

    assert result == {"success": True, "statistics": {"rank": 1}}


@respx.mock
async def test_site_stats_passthrough():
    respx.get(f"{wigle_client.WIGLE_BASE}/stats/general").mock(
        return_value=httpx.Response(200, json={"success": True, "statistics": {"totalWiFi": 1}})
    )

    result = await site_stats()

    assert result == {"success": True, "statistics": {"totalWiFi": 1}}


async def test_network_search_without_credentials_returns_error(monkeypatch):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "C:\\nonexistent-wigle-mcp-config")
    wigle_client._load_credentials.cache_clear()

    result = await network_search()

    assert "error" in result
    assert "WiGLE API credentials" in result["error"]


@respx.mock
async def test_network_search_http_error_returns_error_dict():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(500, text="server boom")
    )

    result = await network_search()

    assert "error" in result
    assert "500" in result["error"]
