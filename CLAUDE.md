# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MCP server providing direct USB control of Elgato Stream Deck devices. Bypasses Elgato software entirely using `python-elgato-streamdeck`.

## Development Commands

```bash
# Setup
uv venv && uv pip install -e ".[dev]"

# Run server (for Claude Desktop)
uv run server.py

# Lint
uv run ruff check .
uv run ruff check --fix .

# Format
uv run ruff format .

# Run tests (no hardware required)
uv run pytest tests/ -v

# Test without deck (fails gracefully if no hardware)
python -c "from server import state; print(state.get_deck_info())"
```

## Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "streamdeck": {
      "command": "uv",
      "args": ["--directory", "/path/to/streamdeck-mcp", "run", "server.py"]
    }
  }
}
```

## Architecture

Single-file server (`server.py`) using MCP's `Server` class with stdio transport.

```
server.py
├── StreamDeckState      # Connection, pages, buttons, callbacks
│   ├── connect()        # Find and open first USB deck
│   ├── set_button_*()   # Image/action configuration
│   ├── *_page()         # Page CRUD and switching
│   └── _key_callback()  # Physical button press handler
├── @server.list_tools() # Tool definitions
└── @server.call_tool()  # Tool handlers
```

**State persistence**: `~/.streamdeck-mcp/pages.json` (appearance) and `buttons.json` (actions).

## Key Concepts

- **Button indexing**: 0-based, left-to-right, top-to-bottom. 5x3 deck = keys 0-14.

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

- **Pages**: Named profiles. "main" is default and undeletable.
- **Actions**: `page:name` for page switching, or shell commands (requires running server).
- **Image generation**: Pillow creates button images from text/colors. Falls back gracefully if fonts unavailable.

## USB Permissions

- **macOS**: `brew install hidapi` (usually works)
- **Linux**: Needs udev rule — see README
- **Windows**: May need Zadig driver

## Troubleshooting

1. **"No Stream Deck found"** — Check USB, permissions, hidapi installed
2. **Button images blank** — Pillow not installed or font not found
3. **State not persisting** — Check write permissions on `~/.streamdeck-mcp/`
