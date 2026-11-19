# AGENTS.md

This file provides guidance to coding agents (Claude Code, Cursor, Codex, and others) when working with code in this repository.

## Overview

MCP server for authoring real Elgato Stream Deck profiles. The default server (`profile_server.py`) writes directly to the Elgato Stream Deck desktop app's profile manifests (`ProfilesV3`, with `ProfilesV2` fallback) instead of taking exclusive USB control. A legacy USB-direct server (`server.py`, built on `python-elgato-streamdeck`) is preserved for Linux/headless setups or when the MCP server should own the hardware itself.

This is a Python project managed with `uv` (see `pyproject.toml`); there is no `package.json`.

## Entry Points

`pyproject.toml` defines three console scripts:

- `streamdeck-mcp` → `profile_server:run` — **default** profile-writer server (`profile_server.py:782`).
- `streamdeck-mcp-usb` → `server:run` — legacy USB-direct server (`server.py:1332`).
- `streamdeck-mcp-install-skill` → `install_skill:main` — copies the bundled `streamdeck-designer` Agent Skill into `~/.claude/skills/`.

Both servers use MCP's `Server` class over stdio (`stdio_server`).

## Development Commands

```bash
# Setup
uv venv && uv pip install -e ".[dev]"

# Run the default profile-writer server
uvx streamdeck-mcp
# or from source:
uv run profile_server.py

# Run the legacy USB server
uvx --from streamdeck-mcp streamdeck-mcp-usb
# or from source:
uv run server.py

# Lint
uv run ruff check .
uv run ruff check --fix .

# Format
uv run ruff format .

# Run tests (no hardware required)
uv run pytest tests/ -v
```

Tests live in `tests/` (`test_profile_manager.py`, `test_server.py`); `pytest` is configured with `asyncio_mode = "auto"` and `testpaths = ["tests"]` in `pyproject.toml`.

## Client Config

Run through [`uvx`](https://docs.astral.sh/uv/). Claude Code:

```bash
claude mcp add streamdeck -- uvx streamdeck-mcp
```

Claude Desktop / Cursor / Codex and other stdio MCP clients:
```json
{
  "mcpServers": {
    "streamdeck": {
      "command": "uvx",
      "args": ["streamdeck-mcp"]
    }
  }
}
```

For the legacy USB server, use `"args": ["--from", "streamdeck-mcp", "streamdeck-mcp-usb"]`.

## Architecture

The default profile-writer flow:

```
profile_server.py            # MCP Server "streamdeck-profile-mcp" (stdio)
├── @server.list_tools()     # 7 tool definitions (profile_server.py:253)
├── @server.list_prompts()   # design_streamdeck_deck prompt (profile_server.py:694)
├── @server.call_tool()      # Tool handlers
└── @server.get_prompt()     # Prompt handler
        │
        ▼
profile_manager.py           # ProfileManager: read/write Elgato profile manifests
├── ProfilesV3 / ProfilesV2 resolution (profile_manager.py:228)
├── OS-specific plugins/profile dir resolution
├── icon + script generation
└── safe write cycle (quit → write → relaunch)
```

The legacy USB flow (`server.py`, MCP Server `"streamdeck-mcp"`):

```
server.py
├── StreamDeckState         # Connection, pages, buttons, callbacks
│   ├── connect(serial)     # Open a USB deck (by serial, or first enumerated)
│   ├── set_button_*()      # Image/action configuration
│   ├── *_page()            # Page CRUD and switching
│   └── _key_callback()     # Physical button press handler
├── @server.list_tools()    # 14 tool definitions (server.py:940)
└── @server.call_tool()     # Tool handlers
```

## MCP Tools

### Default profile-writer server (`profile_server.py`) — 7 tools

1. **streamdeck_read_profiles** — List desktop profiles, device metadata, and page directories from `ProfilesV3`/`ProfilesV2`.
2. **streamdeck_read_page** — Read a page manifest; returns simplified button details plus raw native action objects.
3. **streamdeck_write_page** — Create or rewrite a page manifest. Reuse copied `button.raw` values to preserve configured third-party plugin actions.
4. **streamdeck_create_icon** — Render button or touch-strip PNGs from ~7,400 bundled Material Design Icons or from short text; unknown icon names return close-match suggestions.
5. **streamdeck_create_action** — Create an executable shell script in `~/StreamDeckScripts/` and return an Open action block.
6. **streamdeck_restart_app** — Restart the macOS Stream Deck desktop app after profile changes.
7. **streamdeck_install_mcp_plugin** — Install the bundled streamdeck-mcp Stream Deck plugin for durable encoder imagery (usually auto-installed by `streamdeck_write_page`).

**Prompt:** `design_streamdeck_deck` — primes non-skill-aware MCP clients with the streamdeck-designer authoring briefing; optional `intent` argument.

### Legacy USB server (`server.py`) — 14 tools

`streamdeck_connect`, `streamdeck_list_devices`, `streamdeck_info`, `streamdeck_set_button`, `streamdeck_set_buttons`, `streamdeck_clear_button`, `streamdeck_get_button`, `streamdeck_clear_all`, `streamdeck_set_brightness`, `streamdeck_create_page`, `streamdeck_switch_page`, `streamdeck_list_pages`, `streamdeck_delete_page`, `streamdeck_disconnect`.

When multiple decks are attached, call `streamdeck_list_devices` first, then pass the desired `serial` to `streamdeck_connect`; omitting `serial` opens the first enumerated deck.

## State & Filesystem Paths

- **Profile-writer:** edits the Elgato app's profile manifests in place under its plugins/profiles directories (macOS: `~/Library/Application Support/com.elgato.StreamDeck/`; Linux: `~/.local/share/Elgato/StreamDeck/`; Windows: `%APPDATA%\Elgato\StreamDeck\`).
  - Generated icons: `~/.streamdeck-mcp/generated-icons/` (`profile_manager.py:485`).
  - Generated shell scripts: `~/StreamDeckScripts/` (`profile_manager.py:480`).
- **Legacy USB server:** persists its own state to `~/.streamdeck-mcp/pages.json` and `buttons.json` (`server.py:55`).

## Environment Variables

- **`STREAMDECK_APP_PATH`** — override the Elgato app location if it is not at `/Applications/Elgato Stream Deck.app` (read in `profile_manager.py:332`; default `profile_manager.py:111`).
- `APPDATA` (Windows-only system var) is read to locate the Stream Deck plugins directory on Windows.

## Key Concepts

- **Button indexing**: 0-based, left-to-right, top-to-bottom. A 5x3 deck = keys 0-14.

```
Stream Deck Original (15 keys):
┌────┬────┬────┬────┬────┐
│  0 │  1 │  2 │  3 │  4 │
├────┼────┼────┼────┼────┤
│  5 │  6 │  7 │  8 │  9 │
├────┼────┼────┼────┼────┤
│ 10 │ 11 │ 12 │ 13 │ 14 │
└────┴────┴────┴────┴────┘
```

- **Image generation**: Pillow renders button images. `streamdeck_create_icon` accepts an MDI icon name (e.g. `mdi:cpu-64-bit` — ~7,400 glyphs bundled in `streamdeck_assets/`) or freeform text, plus `icon_color` / `bg_color`. Use a button's `title` field on `streamdeck_write_page` for labels so they don't collide with rendered icon art.
- **Safe write cycle**: the Elgato desktop app keeps profiles in memory and can overwrite on-disk manifest edits when it quits. When the app is running and `auto_quit_app` is not set, `streamdeck_write_page` returns a `⚠️` warning text result (not a raised exception) and does not write — inspect the returned text to detect this. On macOS, pass `auto_quit_app: true` to quit before writing, then call `streamdeck_restart_app`. On Windows, quit and relaunch manually.
- **Profile versions**: `ProfilesV3` is preferred when present. `ProfilesV2` is supported, but existing pages should be targeted by `directory_id` or `page_index` because V2 uses opaque directory names.

## streamdeck-designer Skill

The repo bundles an Agent Skill (`streamdeck_assets/skill/streamdeck-designer/`) that teaches agents to plan, theme, and author full decks. Install with:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-install-skill   # adds --force to upgrade
```

It is copied to `~/.claude/skills/streamdeck-designer/`. Clients that don't load Claude Code skills can invoke the `design_streamdeck_deck` MCP prompt instead.

## USB Permissions (legacy server only)

- **macOS**: `brew install hidapi`
- **Linux**: needs a udev rule — see README
- **Windows**: may need the Zadig driver

## Troubleshooting

1. **Profile edits not appearing** — the Elgato app may have overwritten manifests on quit; use `auto_quit_app: true` then `streamdeck_restart_app`.
2. **App not found / wrong path** — set `STREAMDECK_APP_PATH`.
3. **Button images blank** — Pillow not installed or font not found.
4. **(Legacy USB) "No Stream Deck found"** — check USB, permissions, and that `hidapi` is installed.
