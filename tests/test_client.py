import base64
import json

import httpx
import pytest
import respx

from wigle_mcp import client as wigle_client
from wigle_mcp.client import WigleAuthError, WigleClient, _config_path, _load_credentials


def test_load_credentials_from_env(monkeypatch):
    monkeypatch.setenv("WIGLE_API_NAME", "alice")
    monkeypatch.setenv("WIGLE_API_TOKEN", "secret")
    _load_credentials.cache_clear()

    assert _load_credentials() == ("alice", "secret")


def test_load_credentials_from_config_file(monkeypatch, tmp_path):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg_dir = tmp_path / "wigle-mcp"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(json.dumps({"api_name": "bob", "api_token": "tok"}))
    _load_credentials.cache_clear()

    assert _load_credentials() == ("bob", "tok")


def test_load_credentials_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _load_credentials.cache_clear()

    with pytest.raises(WigleAuthError):
        _load_credentials()


def test_config_path_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert _config_path() == tmp_path / "wigle-mcp" / "config.json"


@respx.mock
async def test_get_sends_basic_auth_header():
    route = respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    client = WigleClient()
    await client.network_detail("AA:BB:CC:DD:EE:FF")

    assert route.called
    request = route.calls.last.request
    expected = base64.b64encode(b"test-name:test-token").decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert request.url.params["netid"] == "AA:BB:CC:DD:EE:FF"


@respx.mock
async def test_network_search_drops_none_params():
    route = respx.get(f"{wigle_client.WIGLE_BASE}/network/search").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    client = WigleClient()
    await client.network_search(ssid="foo", netid=None, resultsPerPage=10)

    request = route.calls.last.request
    assert "ssid" in request.url.params
    assert "netid" not in request.url.params
    assert request.url.params["resultsPerPage"] == "10"


@respx.mock
@pytest.mark.parametrize(
    ("method", "args", "path"),
    [
        ("network_search", {}, "network/search"),
        ("bluetooth_search", {}, "bluetooth/search"),
        ("cell_search", {}, "cell/search"),
        ("stats_user", {}, "stats/user"),
        ("stats_general", {}, "stats/general"),
    ],
)
async def test_search_and_stats_endpoints(method, args, path):
    route = respx.get(f"{wigle_client.WIGLE_BASE}/{path}").mock(
        return_value=httpx.Response(200, json={"success": True})
    )

    client = WigleClient()
    result = await getattr(client, method)(**args)

    assert route.called
    assert result == {"success": True}


@respx.mock
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("network_detail", "network/detail"),
        ("bluetooth_detail", "bluetooth/detail"),
        ("cell_detail", "cell/detail"),
    ],
)
async def test_detail_endpoints(method, path):
    route = respx.get(f"{wigle_client.WIGLE_BASE}/{path}").mock(
        return_value=httpx.Response(200, json={"success": True, "results": []})
    )

    client = WigleClient()
    result = await getattr(client, method)("some-id")

    assert route.called
    assert route.calls.last.request.url.params["netid"] == "some-id"
    assert result == {"success": True, "results": []}


@respx.mock
async def test_get_raises_on_http_error():
    respx.get(f"{wigle_client.WIGLE_BASE}/network/detail").mock(
        return_value=httpx.Response(500, text="boom")
    )

    client = WigleClient()
    with pytest.raises(httpx.HTTPStatusError):
        await client.network_detail("AA:BB:CC:DD:EE:FF")
