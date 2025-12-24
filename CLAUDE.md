# Stream Deck MCP — Agent Instructions

## Overview
This MCP server provides direct USB control of Elgato Stream Deck devices. It bypasses the official Elgato software entirely using the `python-elgato-streamdeck` library.

## Architecture

```
server.py          # Main MCP server (FastMCP pattern)
├── StreamDeckState    # State manager (connection, pages, buttons)
├── list_tools()       # Tool definitions
└── call_tool()        # Tool handlers
```

## Key Concepts

**Button indexing**: 0-based, left-to-right, top-to-bottom. A 5x3 deck has keys 0-14.

**Pages**: Named button profiles. "main" is default and cannot be deleted. Users can create arbitrary pages ("gaming", "streaming", "office") and switch between them.

**State persistence**: All button configs and actions saved to `~/.streamdeck-mcp/` as JSON. Survives restarts.

**Actions**: Currently supports:
- `page:name` — Switch to another page
- Shell commands (executed on button press, requires server running)

## Development

```bash
# Setup
uv venv && uv pip install -e .

# Run standalone
uv run server.py

# Test without deck (will fail gracefully)
python -c "from server import state; print(state.get_deck_info())"
```

## Dependencies

- `mcp[cli]` — MCP server framework
- `streamdeck` — USB hardware control
- `pillow` — Image generation for button faces

## USB Permissions

macOS: Usually works out of the box
Linux: Requires udev rule (see README)
Windows: May need Zadig driver

## Common Issues

1. **"No Stream Deck found"** — Check USB, permissions
2. **Button images don't show** — Pillow not installed or font not found
3. **State not persisting** — Check write permissions on ~/.streamdeck-mcp/
