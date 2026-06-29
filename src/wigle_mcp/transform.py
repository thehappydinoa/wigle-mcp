"""Shape WiGLE API records into compact summaries for LLM consumption."""

from __future__ import annotations

from typing import Any, Literal

MAX_LOCATIONS = 5

DeviceKind = Literal["wifi", "bluetooth", "cell"]

_SUMMARY_KEYS: dict[DeviceKind, tuple[str, ...]] = {
    "wifi": (
        "netid",
        "ssid",
        "encryption",
        "channel",
        "frequency",
        "trilat",
        "trilong",
        "firsttime",
        "lasttime",
        "country",
        "region",
        "city",
        "type",
    ),
    "bluetooth": (
        "netid",
        "name",
        "type",
        "trilat",
        "trilong",
        "firsttime",
        "lasttime",
        "country",
        "region",
        "city",
    ),
    "cell": (
        "netid",
        "operator",
        "networkType",
        "trilat",
        "trilong",
        "firsttime",
        "lasttime",
        "country",
        "region",
        "city",
    ),
}


def summarize_result(
    record: dict[str, Any],
    *,
    kind: DeviceKind,
    include_locations: bool = False,
) -> dict[str, Any]:
    """Return a compact summary of a WiGLE result record."""
    summary: dict[str, Any] = {}
    for key in _SUMMARY_KEYS[kind]:
        if key in record and record[key] is not None:
            summary[key] = record[key]

    locations = record.get("locationData")
    if isinstance(locations, list):
        summary["sightingCount"] = len(locations)
        if include_locations:
            if len(locations) > MAX_LOCATIONS:
                summary["locationData"] = locations[:MAX_LOCATIONS]
                summary["locationDataTruncated"] = True
                summary["locationDataTotal"] = len(locations)
            else:
                summary["locationData"] = locations
        elif locations:
            latest = locations[-1]
            if isinstance(latest, dict):
                lat = latest.get("latitude")
                lon = latest.get("longitude")
                if lat is not None and lon is not None:
                    summary["lastSeen"] = {"latitude": lat, "longitude": lon}

    return summary
