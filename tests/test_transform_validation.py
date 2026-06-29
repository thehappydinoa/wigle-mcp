import pytest
from fastmcp.exceptions import ToolError

from wigle_mcp.transform import summarize_result
from wigle_mcp.validation import require_search_filter, validate_bounding_box


def test_summarize_wifi_search_omits_locations():
    record = {
        "netid": "AA:BB:CC:DD:EE:FF",
        "ssid": "test",
        "encryption": "wpa2",
        "noiseField": "drop-me",
        "locationData": [{"latitude": 1.0, "longitude": 2.0}],
    }

    summary = summarize_result(record, kind="wifi")

    assert summary["ssid"] == "test"
    assert summary["sightingCount"] == 1
    assert summary["lastSeen"] == {"latitude": 1.0, "longitude": 2.0}
    assert "noiseField" not in summary
    assert "locationData" not in summary


def test_summarize_detail_includes_capped_locations():
    record = {
        "netid": "AA:BB:CC:DD:EE:FF",
        "locationData": [{"latitude": float(i), "longitude": float(i)} for i in range(8)],
    }

    summary = summarize_result(record, kind="wifi", include_locations=True)

    assert len(summary["locationData"]) == 5
    assert summary["locationDataTruncated"] is True
    assert summary["locationDataTotal"] == 8


def test_require_search_filter_rejects_empty():
    with pytest.raises(ToolError, match="requires at least one search filter"):
        require_search_filter("network_search")


def test_require_search_filter_accepts_only_open():
    require_search_filter("network_search", only_open=True)


def test_validate_bounding_box_requires_all_corners():
    with pytest.raises(ToolError, match="requires all four parameters"):
        validate_bounding_box(1.0, None, None, None)


def test_validate_bounding_box_rejects_inverted_lat():
    with pytest.raises(ToolError, match="lat_min must be less than or equal to lat_max"):
        validate_bounding_box(10.0, 5.0, 1.0, 2.0)
