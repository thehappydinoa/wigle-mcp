import pytest

from wigle_mcp import client as wigle_client


@pytest.fixture(autouse=True)
def _reset_client_state(monkeypatch):
    """Ensure each test sees fresh credentials and a fresh HTTP client."""
    monkeypatch.setenv("WIGLE_API_NAME", "test-name")
    monkeypatch.setenv("WIGLE_API_TOKEN", "test-token")
    wigle_client._load_credentials.cache_clear()
    wigle_client._http_client = None
    yield
    wigle_client._load_credentials.cache_clear()
    wigle_client._http_client = None
