# wigle-mcp

A local MCP server exposing [WiGLE.net](https://wigle.net) wardriving lookups
as tools for Claude.

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

## Add to Claude Code

```bash
claude mcp add wigle -- uv --directory D:/wigle-mcp run wigle-mcp
```
