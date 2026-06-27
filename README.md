# wigle-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes
[WiGLE.net](https://wigle.net) wardriving lookups as tools for LLMs.

## Tools

- **network_search** — search WiGLE's database of observed WiFi networks by
  SSID, BSSID, location bounding box, country/region/city, or encryption.
- **network_detail** — full detail for a single BSSID, including SSID history
  and recorded sighting locations.
- **bluetooth_search** / **bluetooth_detail** — same, for observed Bluetooth/BLE devices.
- **cell_search** / **cell_detail** — same, for observed cell towers.
- **user_stats** — your WiGLE account stats (rank, discovered network counts).
- **site_stats** — WiGLE-wide totals (networks, locations, users).

## Setup

1. Get a free API key (Name + Token) at <https://wigle.net/account>, under
   "Your API Key".
2. Provide credentials either via environment variables:

   ```bash
   WIGLE_API_NAME=...
   WIGLE_API_TOKEN=...
   ```

   or in `~/.config/wigle-mcp/config.json`:

   ```json
   {"api_name": "...", "api_token": "..."}
   ```

## Running

```bash
uv run wigle-mcp
```

## Configuration

### Claude Code

```bash
claude mcp add wigle -- uv --directory /path/to/wigle-mcp run wigle-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "wigle": {
      "command": "uv",
      "args": ["--directory", "/path/to/wigle-mcp", "run", "wigle-mcp"],
      "env": {
        "WIGLE_API_NAME": "your-api-name",
        "WIGLE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

### Cursor

Add to your `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "wigle": {
      "command": "uv",
      "args": ["--directory", "/path/to/wigle-mcp", "run", "wigle-mcp"],
      "env": {
        "WIGLE_API_NAME": "your-api-name",
        "WIGLE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```
