# Stream Deck MCP

<!-- mcp-name: io.github.verygoodplugins/streamdeck-mcp -->

AI-first MCP server for Elgato Stream Deck profile management. The default server writes directly to the Stream Deck desktop app's native profile files, and the original USB-direct server is still available as a legacy fallback.

## Installation

### Default: Desktop Profile Writer

The default packaged entrypoint is the profile writer. It edits `ProfilesV3` when present, then falls back to `ProfilesV2`.

```bash
uvx streamdeck-mcp
```

### Local Repo Configuration

```json
{
  "mcpServers": {
    "streamdeck": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/streamdeck-mcp",
        "run",
        "profile_server.py"
      ]
    }
  }
}
```

### Legacy USB Server

If you still want direct hardware control that bypasses the Elgato app entirely, keep using the legacy server:

```json
{
  "mcpServers": {
    "streamdeck-usb": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/streamdeck-mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

Or use the packaged legacy entrypoint:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-usb
```

## Default Tools

| Tool | What it does |
|------|---------------|
| `streamdeck_read_profiles` | Lists desktop profiles and page directories from the active ProfilesV3 or ProfilesV2 store |
| `streamdeck_read_page` | Reads a page manifest and returns simplified button details plus the raw manifest |
| `streamdeck_write_page` | Creates a new page or rewrites an existing page manifest |
| `streamdeck_create_icon` | Generates a 72x72 PNG icon with text and colors |
| `streamdeck_create_action` | Creates an executable shell script in `~/StreamDeckScripts/` and returns an Open action block |
| `streamdeck_restart_app` | Restarts the macOS Stream Deck desktop app after profile changes |

## How the Profile Writer Works

- `ProfilesV3` is preferred when it exists because page UUIDs map cleanly to directories.
- `ProfilesV2` is still supported, but existing pages should be targeted by `directory_id` or `page_index` because Elgato stores opaque page directory names there.
- `streamdeck_write_page` can accept raw native action objects, or use convenience fields like `path`, `action_type`, `plugin_uuid`, and `action_uuid`.
- Generated icons are stored in `~/.streamdeck-mcp/generated-icons/`.
- Generated shell scripts are stored in `~/StreamDeckScripts/`.

## Usage Notes

- After writing profiles, the Elgato desktop app may need a restart to pick up the new manifests.
- `streamdeck_create_action` is the safest way to build shell-command buttons because it writes a standalone script and returns the native Open action block for it.
- The profile writer does not require exclusive USB access.

## Legacy USB Tools

The original USB-direct server is preserved for backwards compatibility. It still provides:

- `streamdeck_connect`
- `streamdeck_info`
- `streamdeck_set_button`
- `streamdeck_set_buttons`
- `streamdeck_clear_button`
- `streamdeck_get_button`
- `streamdeck_clear_all`
- `streamdeck_set_brightness`
- `streamdeck_create_page`
- `streamdeck_switch_page`
- `streamdeck_list_pages`
- `streamdeck_delete_page`
- `streamdeck_disconnect`

Use that mode only when you want the MCP server to own the hardware directly and the Elgato desktop app is not running.

## Development

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest tests/ -v
uv run ruff check .
```

To audit this repo against the shared Very Good Plugins MCP standards:

```bash
../mcp-ecosystem/scripts/audit-server.sh .
```

## Support

For issues, questions, or suggestions:

- [Open an issue on GitHub](https://github.com/verygoodplugins/streamdeck-mcp/issues)
- [Contact Very Good Plugins](https://verygoodplugins.com/contact/?utm_source=github)

---

Built with 🧡 by [Very Good Plugins](https://verygoodplugins.com/?utm_source=github)
