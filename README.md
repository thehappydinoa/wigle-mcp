# wigle-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes
[WiGLE.net](https://wigle.net) wardriving lookups as tools for LLMs.

All tools are read-only. Responses are trimmed to compact summaries so agents
stay within context limits and WiGLE query quota.

## Tools

- **network_search** — search observed WiFi networks by SSID, BSSID, bounding
  box, country/region/city, or encryption.
- **network_detail** — look up a single BSSID; pass `include_locations=true`
  for capped sighting history.
- **bluetooth_search** / **bluetooth_detail** — same pattern for Bluetooth/BLE
  devices.
- **cell_search** / **cell_detail** — same pattern for cell towers.
- **user_stats** — WiGLE account stats (rank, discovered network counts).
- **site_stats** — WiGLE-wide totals (networks, locations, users).

## Query etiquette

WiGLE enforces **per-account daily query limits** (reset midnight US/Pacific;
new accounts start low). The server validates requests and ships MCP server
instructions to guide agents, but humans should know the rules too:

- **Always filter searches.** Every `*_search` call needs at least one filter
  (SSID, BSSID, geo fields, bounding box, encryption, etc.). Unfiltered
  searches are rejected before they hit the API.
- **Paginate with `search_after`.** Responses include a `searchAfter` cursor.
  Pass it as `search_after` on the next page — it alone satisfies the filter
  requirement, so you do not need to repeat the original filters.
- **Prefer search over detail.** One bounded search beats many per-BSSID detail
  calls. Keep `results_per_page` low unless you need more.
- **Locations are opt-in.** `*_detail` returns a summary by default. Pass
  `include_locations=true` only when sighting history is needed (capped at 5
  points).

On startup the server verifies credentials by calling `stats/user`. Missing or
invalid keys fail immediately instead of on the first tool call.

Errors are returned as MCP tool errors (not success payloads with an `error`
field). HTTP 429 responses include guidance about daily limits.

## Response shape

Search results are compact summaries, not raw WiGLE records:

```json
{
  "netid": "00:00:34:7A:67:1E",
  "ssid": "pretty fly for a wifi",
  "encryption": "wpa2",
  "trilat": 33.057,
  "trilong": -96.720,
  "country": "US",
  "region": "TX",
  "city": "Plano",
  "sightingCount": 12,
  "lastSeen": {"latitude": 33.057, "longitude": -96.720}
}
```

Detail responses use the same summary fields. With `include_locations=true`,
`sightingCount` is accompanied by up to five `locationData` entries (with
`locationDataTruncated` when more exist).

## Example workflow

```
1. network_search(city="San Francisco", region="CA", country="US", results_per_page=5)
   → searchAfter: "3522985", results: [...]

2. network_search(search_after="3522985", results_per_page=5)
   → next page of the same query

3. network_detail(bssid="00:00:00:00:81:4E")
   → summary for one network

4. network_detail(bssid="00:00:00:00:81:4E", include_locations=true)
   → summary plus capped sighting locations
```

## Setup

1. Get a free API key (Name + Token) at <https://wigle.net/account>, under
   "Your API Key".
2. Provide credentials via environment variables:

   ```bash
   export WIGLE_API_NAME=...
   export WIGLE_API_TOKEN=...
   ```

   or in `~/.config/wigle-mcp/config.json`:

   ```json
   {"api_name": "...", "api_token": "..."}
   ```

   MCP host configs can omit `env` when using the config file.

## Running

```bash
uv run wigle-mcp
```

If `uv run` fails because `wigle-mcp.exe` is locked (common on Windows when
another MCP client is connected), use the module entry point instead:

```bash
uv run python -m wigle_mcp.server
```

## Configuration

On **Windows**, add `--no-sync` to `uv run` args in every host config so
`uv` does not try to reinstall the project while another client already has
`wigle-mcp.exe` open.

### Claude Code

```bash
claude mcp add wigle -- uv --directory /path/to/wigle-mcp run --no-sync wigle-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "wigle": {
      "command": "uv",
      "args": ["--directory", "/path/to/wigle-mcp", "run", "--no-sync", "wigle-mcp"],
      "env": {
        "WIGLE_API_NAME": "your-api-name",
        "WIGLE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "wigle": {
      "command": "uv",
      "args": ["--directory", "/path/to/wigle-mcp", "run", "--no-sync", "wigle-mcp"],
      "env": {
        "WIGLE_API_NAME": "your-api-name",
        "WIGLE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

License: MIT
