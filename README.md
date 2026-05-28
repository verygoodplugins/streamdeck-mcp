<!-- mcp-name: io.github.verygoodplugins/streamdeck-mcp -->

<p align="center">
  <img width="120" src="streamdeck_plugin/io.github.verygoodplugins.streamdeck-mcp.sdPlugin/Images/plugin@2x.png" alt="Stream Deck MCP logo">
</p>

<h1 align="center">Stream Deck MCP</h1>

<p align="center">
  Stream Deck MCP lets agents build and reconfigure real Elgato Stream Deck profiles.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a>
  ·
  <a href="#demo">Demo</a>
  ·
  <a href="#features">Features</a>
  ·
  <a href="#tools">Tools</a>
  ·
  <a href="#development">Development</a>
</p>

Tell your AI what Stream Deck you want. Get back a polished profile with buttons, icons, colors, dials, touch-strip art, and the shell scripts behind it. Stream Deck MCP writes the same profile format the Elgato desktop app already uses, so agents can author real local decks without making you build a Stream Deck plugin first.

It works with Claude Desktop, Claude Code, Cursor, Codex, and any MCP client that can launch a stdio server.

## Quick Start

Claude Code:

```bash
claude mcp add streamdeck -- uvx streamdeck-mcp
```

Claude Desktop, Cursor, Codex, and other MCP clients can use the same command:

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

Then ask your agent for a deck:

> Make me a Slack control board for my Stream Deck + XL.

For Claude Code, install the bundled designer skill for better layout, palette, hardware, and plugin-action guidance:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-install-skill
```

## Demo

<video src="https://github.com/user-attachments/assets/970c8973-f8ff-4a5d-ad48-cde3f3b1fc65"></video>

<p align="center">
  <sub>Product trailer generated with Remotion, showing hardware inventory, plugin discovery, configured action reuse, and a final Stream Deck + XL reveal.</sub>
</p>

## Features

- **Profile-native authoring** - reads and writes Elgato `ProfilesV3` files directly, with `ProfilesV2` fallback for older installs.
- **Hardware inventory** - discovers profile pages, device model names, key geometry, dials, and touch-strip support before writing.
- **Installed plugin discovery** - scans readable Stream Deck plugin manifests with `streamdeck_read_plugins` so agents can find plugin and action UUIDs.
- **Configured plugin action reuse** - reads existing buttons with `streamdeck_read_page` and preserves plugin-specific settings by copying `button.raw`; it does not infer private property-inspector settings.
- **Offline icon generation** - renders button and touch-strip PNGs from about 7,400 bundled Material Design Icons, or from short text labels.
- **Script-backed automations** - creates executable shell scripts in `~/StreamDeckScripts/` and wires them to Stream Deck Open actions.
- **Dial and touch-strip support** - installs a minimal bundled Stream Deck plugin when needed so encoder imagery survives app restarts.
- **Safe write cycle** - guards against the Elgato app overwriting manifest edits by enforcing a quit, write, relaunch workflow.

## Agentic Workflows

The point is not generic buttons. When your agent also has Slack, Home Assistant, OBS, GitHub, Hue, Spotify, or other MCP servers loaded, it can query those systems first and build around what is actually in your environment.

Try prompts like:

- **"Make me a control board for Slack."** Query channels, status, and unread state; create channel jumps, status toggles, read-all controls, and dials.
- **"A hello-kitty-themed Home Assistant dashboard for the living room."** Discover living-room entities, then lay out scenes, lights, and media controls in a matching visual style.
- **"OBS control panel based on my actual scenes and audio inputs."** Read scenes, sources, and devices; write scene switches, source toggles, and per-input dial controls.
- **"A dev deck for this repo in Nordic colors."** Read project scripts and GitHub context; create local command buttons, PR links, and CI shortcuts.
- **"A Friday demo deck."** Compose across Zoom, Slack, Hue, and screen recording by generating local scripts and wiring them to one page.

Iteration is cheap: change the prompt, rerun the authoring flow, and get a new profile.

## Install

The packaged entrypoint is `streamdeck-mcp`, run through [`uvx`](https://docs.astral.sh/uv/).

### Cursor

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-light.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=streamdeck&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJzdHJlYW1kZWNrLW1jcCJdfQ==)

Or paste into `~/.cursor/mcp.json`:

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

### Claude Desktop

Paste into `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows, then restart Claude Desktop:

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

### Claude Code

```bash
claude mcp add streamdeck -- uvx streamdeck-mcp
```

### OpenAI Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.streamdeck]
command = "uvx"
args = ["streamdeck-mcp"]
```

### Other MCP Clients

Anything that speaks MCP over stdio works the same way: point it at `uvx streamdeck-mcp`.

### Linux and Headless Setups

The default profile writer targets the Elgato Stream Deck desktop app, which is available on macOS and Windows. On Linux, headless machines, or setups where you want the MCP server to own the hardware directly, use the legacy USB server:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-usb
```

Client config shape:

```json
{
  "mcpServers": {
    "streamdeck": {
      "command": "uvx",
      "args": ["--from", "streamdeck-mcp", "streamdeck-mcp-usb"]
    }
  }
}
```

## Tools

| Tool | What it does |
|------|---------------|
| `streamdeck_read_plugins` | Lists installed Stream Deck plugins and declared actions from readable plugin manifests. Protected or binary manifests are reported with diagnostics instead of failing the whole catalog. |
| `streamdeck_read_profiles` | Lists desktop profiles, device metadata, page directories, and active profile roots from `ProfilesV3` or `ProfilesV2`. |
| `streamdeck_read_page` | Reads a page manifest and returns simplified button details plus raw native action objects. |
| `streamdeck_write_page` | Creates or rewrites a page manifest. Use copied `button.raw` values when reusing configured third-party plugin actions. |
| `streamdeck_create_icon` | Generates button or touch-strip PNGs from Material Design Icons or text. Icons are bundled offline; unknown names return close-match suggestions. |
| `streamdeck_create_action` | Creates an executable shell script in `~/StreamDeckScripts/` and returns an Open action block. |
| `streamdeck_restart_app` | Restarts the macOS Stream Deck desktop app after profile changes. |
| `streamdeck_install_mcp_plugin` | Installs the bundled streamdeck-mcp Stream Deck plugin used for durable encoder imagery. Usually auto-installed by `streamdeck_write_page`. |

Prompt support:

| Prompt | What it does |
|--------|---------------|
| `design_streamdeck_deck` | Gives non-skill-aware MCP clients a condensed deck-design briefing before the user describes the deck they want. |

## streamdeck-designer Skill

Stream Deck MCP ships with an Agent Skill for Claude Code that teaches the agent how to plan, theme, and author full decks end to end.

Install it with:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-install-skill
```

The skill is copied to `~/.claude/skills/streamdeck-designer/`. Restart Claude Code or start a new session after installing it. Re-run with `--force` to upgrade after a package update.

The skill covers:

- Hardware inventory and model-specific layout planning.
- Theme palettes, typography strategy, and icon-color guidance.
- Dial and touch-strip authoring for Stream Deck + and + XL devices.
- Integration recipes for Hue, OBS, Spotify, Home Assistant, Twitch, shell commands, and browser workflows.
- Existing plugin action reuse through `streamdeck_read_page` and `button.raw`.

Clients that do not load Claude Code skills can invoke the `design_streamdeck_deck` MCP prompt instead.

## Development

```bash
git clone https://github.com/verygoodplugins/streamdeck-mcp.git
cd streamdeck-mcp
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/ -v
uv run ruff check .
```

To audit this repo against the shared Very Good Plugins MCP standards:

```bash
../mcp-ecosystem/scripts/audit-server.sh .
```

### Authoring Notes

- `ProfilesV3` is preferred when present. `ProfilesV2` is still supported, but existing pages should be targeted by `directory_id` or `page_index` because Elgato uses opaque directory names there.
- The Elgato desktop app keeps profiles in memory and can overwrite on-disk manifest edits when it quits. `streamdeck_write_page` raises `StreamDeckAppRunningError` when the app is running and `auto_quit_app` is not set.
- On macOS, pass `auto_quit_app: true` to quit the app before writing, then call `streamdeck_restart_app` when done. On Windows, quit and relaunch the Elgato app manually.
- Set `STREAMDECK_APP_PATH` if your Elgato app is not installed at `/Applications/Elgato Stream Deck.app`.
- Generated icons live in `~/.streamdeck-mcp/generated-icons/`. Generated shell scripts live in `~/StreamDeckScripts/`.

### Legacy USB Mode

The original USB-direct server is preserved for backwards compatibility. It exposes direct hardware tools:

`streamdeck_connect`, `streamdeck_info`, `streamdeck_set_button`, `streamdeck_set_buttons`, `streamdeck_clear_button`, `streamdeck_get_button`, `streamdeck_clear_all`, `streamdeck_set_brightness`, `streamdeck_create_page`, `streamdeck_switch_page`, `streamdeck_list_pages`, `streamdeck_delete_page`, `streamdeck_disconnect`.

Run it with:

```bash
uvx --from streamdeck-mcp streamdeck-mcp-usb
```

## Support

- [Open an issue on GitHub](https://github.com/verygoodplugins/streamdeck-mcp/issues)
- [Contact Very Good Plugins](https://verygoodplugins.com/contact/?utm_source=github)

Built by [Very Good Plugins](https://verygoodplugins.com/?utm_source=github).
