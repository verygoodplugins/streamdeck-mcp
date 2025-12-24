# 🎛️ Stream Deck MCP · v0.1.0

> **Control your Elgato Stream Deck via MCP** — Set buttons, manage pages, wire actions. No YAML hell, no GUI clicking.

## ✨ What This Does

🎯 **Direct hardware control** — Bypasses Elgato software entirely via USB  
🔥 **Multi-page support** — Create profiles like "Office", "Gaming", "Streaming"  
🧠 **Persistent state** — Button configs survive restarts  
⚡ **Action hooks** — Wire buttons to shell commands or page switches  

Works with: Stream Deck (all sizes), Stream Deck Mini, Stream Deck XL, Stream Deck MK.2

## 🏃 Quick Start — 5 Minutes to Buttons

### Prerequisites

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

### 1️⃣ Install

```bash
cd ~/Projects/OpenAI/mcp-servers/streamdeck-mcp
uv venv
uv pip install -e .
```

### 2️⃣ Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "streamdeck": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/jgarturo/Projects/OpenAI/mcp-servers/streamdeck-mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

### 3️⃣ Connect and Configure

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

## 📐 Button Layout

Buttons are numbered left-to-right, top-to-bottom:

**Stream Deck (15 keys, 5x3):**
```
[0]  [1]  [2]  [3]  [4]
[5]  [6]  [7]  [8]  [9]
[10] [11] [12] [13] [14]
```

**Stream Deck XL (32 keys, 8x4):**
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

The action field accepts any shell command, so you can use `curl` to hit HA webhooks or the HA CLI.

## 🎨 Custom Icons

Drop PNG/JPG files anywhere and reference them:

```
Set button 5 with image ~/icons/spotify.png
```

Images auto-scale to button size (72x72 or 96x96 depending on deck model).

## 📁 State Storage

Configs persist at `~/.streamdeck-mcp/`:
- `pages.json` — Button appearances per page
- `buttons.json` — Button actions per page

## ⚠️ Troubleshooting

**"No Stream Deck found"**
- Check USB connection
- On Linux: Did you add the udev rule and reload?
- On macOS: Grant terminal USB access in System Preferences > Security

**"streamdeck library not installed"**
```bash
uv pip install streamdeck
```

**Buttons don't respond to presses**
- Physical button callbacks require the server to stay running
- For persistent actions, use the Elgato software + this MCP for configuration

## 🔮 Coming Soon

- [ ] Home Assistant entity browser integration
- [ ] Icon generation from emoji
- [ ] Button press webhooks
- [ ] Multi-deck support

---

MIT License
