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

## Designing Decks with the `streamdeck-designer` Skill

streamdeck-mcp ships with an **Agent Skill** that teaches Claude how to design, theme, and author complete Stream Deck layouts using the MCP tools below. With the skill loaded, Claude can one-shot an authored deck from a high-level prompt — "give me a hello-kitty-themed Twitch deck with Hue light controls", "build a dev deck for this repo in Nordic colors" — including palette planning, integration discovery, consistent icon generation, and shell-script wiring.

### Install the skill (Claude Code / Claude.ai)

```bash
# After installing streamdeck-mcp (e.g. via uvx or pip install -e .)
streamdeck-mcp-install-skill
# or, without the console script:
uv run python -m install_skill
```

The skill is copied to `~/.claude/skills/streamdeck-designer/`. Restart Claude Code (or start a new session) and it auto-loads when your request matches a themed/custom deck design intent.

To upgrade after a `streamdeck-mcp` version bump, rerun with `--force`:

```bash
streamdeck-mcp-install-skill --force
```

### Other MCP clients

Clients that don't load Claude Code skills (Claude Desktop, Cursor, ChatGPT-with-MCP, …) get a condensed mirror via the MCP prompt **`design_streamdeck_deck`**. Invoke it before asking for a deck — most clients expose it as a slash command or prompt picker. Pass the user's intent via the `intent` argument if your client supports it.

### What the skill covers

- Hardware inventory — the skill always calls `streamdeck_read_profiles` first, then consults bundled references to match authoring style to the user's model (Original, MK.2, XL, Plus XL, Neo, Mini).
- Palette + typography planning — 8 theme archetypes (kawaii, retrowave, brutalist, nordic, terminal, nature, minimal, corporate) with ready palettes + per-strategy icon-color guidance.
- Dials + touchstrip — decision tree for Plus XL encoder layouts (`$X1` / `$A0` / …) with Phase 1 constraints called out (value/indicator slots render empty until the live channel lands).
- Integration recipes — per-service patterns for Hue, OBS, Spotify, Home Assistant, Twitch, shell, browser. Authoring-time discovery via companion MCPs; credentials stored in `~/StreamDeckScripts/.env`, never baked into scripts.
- Starter recipes — streamer/hello-kitty (Plus XL), dev/Nordic (XL), music/retrowave (Original) as adaptation shapes.

The skill lives at `streamdeck_assets/skill/streamdeck-designer/` in the repo; the `SKILL.md` body is ≤500 lines and `references/` are loaded on demand.

## Default Tools

| Tool | What it does |
|------|---------------|
| `streamdeck_read_profiles` | Lists desktop profiles and page directories from the active ProfilesV3 or ProfilesV2 store |
| `streamdeck_read_page` | Reads a page manifest and returns simplified button details plus the raw manifest |
| `streamdeck_write_page` | Creates a new page or rewrites an existing page manifest |
| `streamdeck_create_icon` | Generates a PNG icon from a Material Design Icons name (e.g. `mdi:cpu-64-bit`) or from text (but not both). `shape="button"` (72x72, default) for keypad keys and encoder dial faces; `shape="touchstrip"` (200x100) for Stream Deck + / + XL dial segment backgrounds. ~7400 MDI icons are bundled offline; unknown names return close-match suggestions |
| `streamdeck_create_action` | Creates an executable shell script in `~/StreamDeckScripts/` and returns an Open action block |
| `streamdeck_restart_app` | Restarts the macOS Stream Deck desktop app after profile changes |
| `streamdeck_install_mcp_plugin` | Installs the bundled streamdeck-mcp Stream Deck plugin into the user's Elgato Plugins directory. `streamdeck_write_page` auto-installs it when an encoder button needs it, so direct use is rarely necessary |

## How the Profile Writer Works

- `ProfilesV3` is preferred when it exists because page UUIDs map cleanly to directories.
- `ProfilesV2` is still supported, but existing pages should be targeted by `directory_id` or `page_index` because Elgato stores opaque page directory names there.
- `streamdeck_write_page` can accept raw native action objects, or use convenience fields like `path`, `action_type`, `plugin_uuid`, and `action_uuid`.
- Generated icons are stored in `~/.streamdeck-mcp/generated-icons/`.
- Generated shell scripts are stored in `~/StreamDeckScripts/`.
- The bundled streamdeck-mcp Stream Deck plugin is installed into the Stream Deck Plugins directory (e.g., `~/Library/Application Support/com.elgato.StreamDeck/Plugins/` on macOS, `%APPDATA%\Elgato\StreamDeck\Plugins\` on Windows) once installed. It's a minimal shell whose only job is to declare encoder support so per-instance `Encoder.Icon` / `Encoder.background` writes survive an Elgato app restart. `streamdeck_write_page` installs it automatically the first time an encoder button needs it.

## Editing Workflow (Important)

The Elgato desktop app keeps every profile in memory and rewrites the on-disk manifests from that snapshot when it quits, so any edit made while the app is running is wiped the next time it closes. The profile writer enforces a quit → write → relaunch cycle:

1. Ensure the Elgato app is not running, or pass `auto_quit_app: true` to `streamdeck_write_page` to have it quit the app for you (AppleScript first, `killall` fallback).
2. Make as many `streamdeck_write_page` calls as you need — the app stays quit across them.
3. Call `streamdeck_restart_app` when you are done. The device re-reads the manifests on launch and your changes appear.

`streamdeck_write_page` raises a `StreamDeckAppRunningError` when the app is running and `auto_quit_app` is not set, so you cannot accidentally write changes that will be silently discarded.

If your Elgato app is installed somewhere other than `/Applications/Elgato Stream Deck.app`, set `STREAMDECK_APP_PATH` to the bundle path.

## Usage Notes

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
