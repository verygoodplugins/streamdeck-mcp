# 🎛️ Stream Deck MCP · v0.1.0

<!-- mcp-name: io.github.verygoodplugins/streamdeck-mcp -->

> **Let AI design your Stream Deck setup** — Describe what you want in plain English. Your AI builds it.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## The Problem

Stream Deck is powerful, but configuring it is tedious. Clicking through the GUI, finding icons, setting up multi-page workflows — it takes forever.

## The Solution

Tell your AI what you want:

```
"Design a podcast studio layout with pages for recording, editing, and publishing.
Include buttons for mic mute, recording start/stop, sound effects, and scene switching."
```

Your AI designs the strategy, creates the pages, and configures every button. Done.

## ✨ What You Can Do

🎙️ **"Set up my Stream Deck for podcasting"** — AI designs a multi-page system
🏠 **"Create a home automation page"** — Buttons for lights, scenes, climate
🎮 **"Build a gaming profile with Discord, OBS, and Spotify"** — One prompt, full setup
🔄 **"Redesign my layout to be more intuitive"** — AI understands workflow, suggests improvements

Works with: Stream Deck, Stream Deck Mini, Stream Deck XL, Stream Deck MK.2, Stream Deck +

## ⚠️ Important: Quit Elgato Software First

**This MCP server requires exclusive USB access.** You must quit the Elgato Stream Deck software before using it:

```bash
# macOS — quit Elgato software
killall "Stream Deck" 2>/dev/null || true
```

The Stream Deck can only be controlled by one application at a time. While using this MCP server, the Elgato software cannot run (and vice versa).

---

## 🏃 Quick Start — 2 Minutes to Buttons

### 1️⃣ Prerequisites

```bash
# macOS
brew install hidapi

# Linux (Debian/Ubuntu)
sudo apt install libhidapi-libusb0

# Linux udev rule (required for non-root access)
sudo tee /etc/udev/rules.d/10-streamdeck.rules << EOF
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", MODE="0666"
EOF
sudo udevadm control --reload-rules
```

### 2️⃣ Install

```bash
git clone https://github.com/verygoodplugins/streamdeck-mcp.git
cd streamdeck-mcp
uv venv && uv pip install -e .
```

### 3️⃣ Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "streamdeck": {
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

### 4️⃣ Use It

In Claude:
```
Connect to my Stream Deck
```

Then:
```
Set button 0 to "Lights" with a blue background
Set button 1 to "Music" with action "open -a Spotify"
Create a page called "gaming" and switch to it
```

That's it! 🎉

## 🛠️ Available Tools

| Tool | What it does |
|------|-------------|
| `streamdeck_connect` | Connect to first available deck |
| `streamdeck_info` | Get deck model, key count, current page |
| `streamdeck_set_button` | Set text, image, colors, and action |
| `streamdeck_clear_button` | Clear a single button |
| `streamdeck_set_brightness` | 0-100% brightness |
| `streamdeck_create_page` | Create a new button profile |
| `streamdeck_switch_page` | Switch active page |
| `streamdeck_list_pages` | List all pages |
| `streamdeck_delete_page` | Delete a page (except "main") |
| `streamdeck_disconnect` | Clean disconnect |

### Natural Language Examples

Just tell Claude what you want:

- "Connect to my Stream Deck and show me the layout"
- "Set button 0 to say 'Lights' with a blue background"
- "Make button 4 open Spotify when I press it"
- "Create a 'gaming' page with Discord, Steam, and OBS buttons"
- "Switch to the gaming page"
- "Set brightness to 50%"

## 📐 Button Layout

Buttons are numbered left-to-right, top-to-bottom:

**Stream Deck (15 keys, 5×3):**
```
[0]  [1]  [2]  [3]  [4]
[5]  [6]  [7]  [8]  [9]
[10] [11] [12] [13] [14]
```

**Stream Deck Mini (6 keys, 3×2):**
```
[0]  [1]  [2]
[3]  [4]  [5]
```

**Stream Deck XL (32 keys, 8×4):**
```
[0]  [1]  [2]  [3]  [4]  [5]  [6]  [7]
[8]  [9]  [10] [11] [12] [13] [14] [15]
[16] [17] [18] [19] [20] [21] [22] [23]
[24] [25] [26] [27] [28] [29] [30] [31]
```

## 🏠 Home Assistant Integration

Wire buttons to your HA entities. Example prompt:

```
Set up my Stream Deck for home control:
- Button 0: "Office Lights" that toggles light.office_ceiling
- Button 1: "All Off" that runs a scene
- Button 4: Page switch to "media" page
```

The action field accepts any shell command — use `curl` to hit HA webhooks or the HA CLI.

## 🎨 Custom Icons

Drop PNG/JPG files anywhere and reference them:

```
Set button 5 with image ~/icons/spotify.png
```

Images auto-scale to button size (72×72 or 96×96 depending on deck model).

## 📁 State Storage

Configs persist at `~/.streamdeck-mcp/`:
- `pages.json` — Button appearances per page
- `buttons.json` — Button actions per page

## ⚠️ Troubleshooting

**"No Stream Deck found"**
- Check USB connection
- On Linux: Did you add the udev rule and reload?
- On macOS: Grant terminal USB access in System Preferences → Security & Privacy

**"streamdeck library not installed"**
```bash
uv pip install streamdeck pillow
```

**Buttons don't respond to presses**
- Physical button callbacks require the MCP server to stay running
- The server runs while Claude Desktop is open

**"Deck disconnected" errors**
- The server handles USB disconnections gracefully
- Just say "Connect to my Stream Deck" again to reconnect

## 🧪 Development

```bash
# Setup
uv venv && uv pip install -e ".[dev]"

# Run server
uv run server.py

# Run tests (no hardware required)
uv run pytest tests/ -v

# Lint
uv run ruff check .
```

## 🔮 Roadmap

- [ ] Home Assistant entity browser integration
- [ ] Icon generation from emoji
- [ ] Button press webhooks
- [ ] Multi-deck support

## License

MIT — Because hardware control should be free.

---

*Built by [Jack Arturo](https://verygoodplugins.com/?utm_source=github) at Very Good Plugins* 🧡

[![X (Twitter)](https://img.shields.io/badge/follow-@jjack__arturo-black?logo=x)](https://x.com/jjack_arturo)
