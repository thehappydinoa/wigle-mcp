import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from wigle_mcp import client as wigle_client
from wigle_mcp.server import (
    bluetooth_detail,
    bluetooth_search,
    cell_detail,
    cell_search,
    mcp,
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


def _mock_startup_check():
    return respx.get(f"{wigle_client.WIGLE_BASE}/stats/user").mock(
        return_value=httpx.Response(200, json={"success": True})
    )


@respx.mock
async def test_network_search_summarizes_response():
    _mock_startup_check()
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
    assert net["ssid"] == "test-network"
    assert net["sightingCount"] == 10
    assert net["lastSeen"] == {"latitude": 9.0, "longitude": 9.0}
    assert "locationData" not in net


@respx.mock
async def test_network_detail_not_found():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    result = await network_detail(bssid="AA:BB:CC:DD:EE:FF")

    assert result == {"success": True, "found": False, "results": []}


@respx.mock
async def test_network_detail_found_summary():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": [_network_result()]})
    )

    result = await network_detail(bssid="AA:BB:CC:DD:EE:FF")

    assert result["found"] is True
    assert result["results"][0]["ssid"] == "test-network"
    assert "locationData" not in result["results"][0]


@respx.mock
async def test_network_detail_include_locations_trims():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": [_network_result()]})
    )

    result = await network_detail(bssid="AA:BB:CC:DD:EE:FF", include_locations=True)

    net = result["results"][0]
    assert len(net["locationData"]) == 5
    assert net["locationDataTruncated"] is True
    assert net["locationDataTotal"] == 10


@respx.mock
@pytest.mark.parametrize(
    ("tool", "path", "kwargs"),
    [
        (bluetooth_search, "bluetooth/search", {"name": "device"}),
        (cell_search, "cell/search", {"operator": "carrier"}),
    ],
)
async def test_search_tools_shape_response(tool, path, kwargs):
    respx.get(f"{wigle_client.WIGLE_BASE}/{path}").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "totalResults": 1, "results": [_network_result()]},
        )
    )

    result = await tool(**kwargs)

    assert result["success"] is True
    assert result["resultCount"] == 1
    assert result["results"][0]["sightingCount"] == 10


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


async def test_network_search_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "C:\\nonexistent-wigle-mcp-config")
    wigle_client._load_credentials.cache_clear()

    with pytest.raises(ToolError, match="WiGLE API credentials"):
        await network_search(ssid="test")


@respx.mock
async def test_network_search_http_error_raises():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(return_value=httpx.Response(500, text="server boom"))

    with pytest.raises(ToolError, match="500"):
        await network_search(ssid="test")


@respx.mock
async def test_network_search_rate_limit_raises():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(429, text="too many requests")
    )

    with pytest.raises(ToolError, match="daily query limit"):
        await network_search(ssid="test")


@respx.mock
async def test_network_search_auth_failure_raises():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(return_value=httpx.Response(401, text="unauthorized"))

    with pytest.raises(ToolError, match="authentication failed"):
        await network_search(ssid="test")


@respx.mock
async def test_network_search_forbidden_raises():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(return_value=httpx.Response(403, text="forbidden"))

    with pytest.raises(ToolError, match="access denied"):
        await network_search(ssid="test")


async def test_network_search_requires_filter():
    with pytest.raises(ToolError, match="requires at least one search filter"):
        await network_search()


async def test_network_search_validates_bounding_box():
    with pytest.raises(ToolError, match="lat_min must be less than or equal to lat_max"):
        await network_search(lat_min=10.0, lat_max=5.0, long_min=1.0, long_max=2.0)

    with pytest.raises(ToolError, match="requires all four parameters"):
        await network_search(lat_min=10.0)


@respx.mock
async def test_network_search_maps_parameters():
    route = respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    await network_search(ssid_like="Fly%", only_open=True, results_per_page=10)

    request = route.calls.last.request
    assert request.url.params["ssidlike"] == "Fly%"
    assert request.url.params["freenet"] == "true"
    assert request.url.params["resultsPerPage"] == "10"


@respx.mock
async def test_network_search_via_mcp_client():
    _mock_startup_check()
    route = respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "totalResults": 0, "results": []},
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("network_search", {"ssid": "test-network"})

    assert not result.is_error
    assert route.called


@respx.mock
async def test_startup_probe_fails_without_credentials(monkeypatch):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "C:\\nonexistent-wigle-mcp-config")
    wigle_client._load_credentials.cache_clear()

    with pytest.raises(RuntimeError, match="WiGLE API credentials"):
        async with Client(mcp):
            pass
