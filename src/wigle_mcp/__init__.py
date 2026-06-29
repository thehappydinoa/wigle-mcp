"""WiGLE MCP server package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("wigle-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"
