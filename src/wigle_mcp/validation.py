"""Input validation for WiGLE MCP tools."""

from __future__ import annotations

from fastmcp.exceptions import ToolError


def require_search_filter(tool_name: str, **filters: object) -> None:
    """Require at least one meaningful search filter before calling the API."""
    if not any(v is not None and v != "" for v in filters.values()):
        raise ToolError(
            f"{tool_name} requires at least one search filter "
            "(e.g. ssid, bssid, bounding box, or geo fields). "
            "Unfiltered searches waste your daily WiGLE query quota."
        )


def validate_bounding_box(
    lat_min: float | None,
    lat_max: float | None,
    long_min: float | None,
    long_max: float | None,
) -> None:
    """Validate bounding-box parameters when any corner is provided."""
    corners = (lat_min, lat_max, long_min, long_max)
    if not any(c is not None for c in corners):
        return
    if not all(c is not None for c in corners):
        raise ToolError("Bounding box search requires all four parameters: lat_min, lat_max, long_min, and long_max.")
    if lat_min > lat_max:
        raise ToolError("lat_min must be less than or equal to lat_max.")
    if long_min > long_max:
        raise ToolError("long_min must be less than or equal to long_max.")
