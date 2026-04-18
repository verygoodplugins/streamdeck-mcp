# Integrations

How to wire Stream Deck buttons to real services in Phase 1 (static authoring, no ongoing Claude connection). The common shape:

1. Figure out how to invoke the service from a shell command (curl, CLI, native scripting).
2. Bake that invocation into a script via `streamdeck_create_action`.
3. Store credentials in `~/StreamDeckScripts/.env`; source it in each generated script.

Below: per-service patterns. Each one names the companion MCP to prefer for authoring-time discovery (if the user has it installed), the shell-script shape to generate, and what goes in `.env`.

## The `.env` pattern (universal)

All integrations follow this pattern for secrets:

**`~/StreamDeckScripts/.env`** (created once, user-maintained):

```bash
# Philips Hue
HUE_BRIDGE_IP=192.168.1.5
HUE_API_KEY=XYZ-your-long-token-here

# OBS (obs-websocket v5)
OBS_HOST=127.0.0.1
OBS_PORT=4455
OBS_PASSWORD=your-websocket-password

# Home Assistant
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your-long-lived-access-token

# Spotify (via spotipy)
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Twitch
TWITCH_OAUTH=oauth:your-token
TWITCH_CHANNEL=yourchannel
```

**Every generated script sources it**:

```bash
#!/bin/bash
set -a
source "$HOME/StreamDeckScripts/.env"
set +a
# ... command using $VAR_NAME variables
```

Tell the user where `.env` lives, which vars they need to fill in, and that the file is never logged or transmitted. If they're on 1Password CLI or the macOS Keychain, flag that as an alternative and offer to show them the pattern — but `.env` is the default.

---

## Philips Hue

**If a Hue MCP is available in this session**: use it to enumerate bridges, rooms, scenes, and light groups. The goal is that buttons reference the user's *actual* scene names — not placeholders.

**If not**: ask the user for their Hue Bridge IP (on their local network) and their API key. Generate the key via the [Hue CLIP API discovery flow](https://developers.meethue.com/develop/get-started-2/) if they don't have one (they press a physical button on the bridge, then curl `/api`).

### Shell script shape

**Activate a scene**:

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
curl -s "http://$HUE_BRIDGE_IP/api/$HUE_API_KEY/groups/0/action" \
  -X PUT \
  -H "Content-Type: application/json" \
  -d '{"scene": "SCENE_ID_HERE"}' > /dev/null
```

Scene IDs come from `GET /api/$HUE_API_KEY/scenes` — enumerate them at authoring time via the Hue MCP (or have the user curl once and paste you the list).

**Toggle a room's lights on/off**:

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
curl -s "http://$HUE_BRIDGE_IP/api/$HUE_API_KEY/groups/1/action" \
  -X PUT -d '{"on": true}' > /dev/null   # or false
```

**Set brightness (0–254)**:

```bash
curl -s "http://$HUE_BRIDGE_IP/api/$HUE_API_KEY/groups/1/action" \
  -X PUT -d '{"bri": 200}' > /dev/null
```

On Plus XL you'd want the dial to adjust this value — but dial rotation events land in Phase 2. For now, make discrete brightness presets (25%, 50%, 100%) as separate buttons.

### Icons to reach for

`mdi:lightbulb`, `mdi:lightbulb-on`, `mdi:lightbulb-off`, `mdi:ceiling-light`, `mdi:lamp`, `mdi:palette` (for scenes), `mdi:brightness-6` (brightness).

---

## OBS (obs-websocket v5)

**If an OBS MCP is available**: use it to discover scenes, sources, audio inputs, and studio/program mode state.

**If not**: user needs obs-websocket v5 enabled in OBS (Tools → WebSocket Server Settings; set password). Then use `obs-cli` (Rust, `cargo install obs-cli`) or `obs-websocket-py` for shell scripting. `obs-cli` is simpler.

### Shell script shape (using `obs-cli`)

Install `obs-cli` once, configure via `~/.config/obs-cli/config.yaml` with your websocket host/port/password.

**Switch to a scene**:

```bash
#!/bin/bash
obs-cli scene current "Starting Soon"
```

**Toggle mute on an audio source**:

```bash
obs-cli audio toggle "Mic/Aux"
```

**Start / stop stream**:

```bash
obs-cli stream start
obs-cli stream stop
```

**Start / stop recording**:

```bash
obs-cli record start
obs-cli record stop
```

If the user won't install `obs-cli`, use `curl` to the websocket upgrade endpoint — but this requires auth handshake code and is a poor fit for a one-line shell script. Recommend `obs-cli`.

### Icons to reach for

`mdi:video-wireless`, `mdi:broadcast`, `mdi:record-circle`, `mdi:monitor-screenshot`, `mdi:video-switch`, `mdi:microphone`, `mdi:microphone-off`, `mdi:camera`, `mdi:camera-off`.

---

## Home Assistant

**If a Home Assistant MCP is available**: use it to discover entities, scenes, scripts, automations. This is the ideal case — HA has hundreds of entities even in a small house, and picking the right ones by hand is tedious.

**If not**: user provides the URL + a long-lived access token (Profile → Security → Long-Lived Access Tokens).

### Shell script shape

Home Assistant uses REST with bearer auth:

**Call a service** (e.g. activate a scene, run a script):

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
curl -s -X POST "$HA_URL/api/services/scene/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "scene.evening_chill"}' > /dev/null
```

**Toggle an entity**:

```bash
curl -s -X POST "$HA_URL/api/services/light/toggle" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' > /dev/null
```

**Run a script or automation**:

```bash
curl -s -X POST "$HA_URL/api/services/script/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -d '{"entity_id": "script.morning_routine"}' > /dev/null
```

### Icons

`mdi:home`, `mdi:home-automation`, `mdi:lightbulb`, `mdi:thermostat`, `mdi:door`, `mdi:lock`, `mdi:motion-sensor`, `mdi:robot-vacuum`.

---

## Spotify

**If a Spotify MCP is available**: use it for current-track reads and playback control discovery.

**If not**: Python with `spotipy` is the simplest path. Requires a Spotify developer app (free) and a one-time OAuth flow to get a refresh token. The generated scripts use `spotipy` to issue playback commands.

One-time setup:
1. User registers a dev app at <https://developer.spotify.com/dashboard>, gets Client ID + Client Secret.
2. Puts them in `.env` as `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI=http://localhost:8888/callback`.
3. Runs an auth flow script once (you can generate it) that opens the browser, captures the redirect, saves the refresh token to `~/.cache-spotipy` or similar.

### Shell script shape

Each action is a small Python wrapper:

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
python3 -c "
import spotipy
from spotipy.oauth2 import SpotifyOAuth
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope='user-modify-playback-state'))
sp.next_track()
"
```

Verbs: `sp.next_track()`, `sp.previous_track()`, `sp.pause_playback()`, `sp.start_playback()`, `sp.start_playback(context_uri='spotify:playlist:...')`, `sp.volume(50)`.

This requires `spotipy` installed in the user's Python. Flag that during authoring.

### Icons

`mdi:play`, `mdi:pause`, `mdi:skip-next`, `mdi:skip-previous`, `mdi:spotify`, `mdi:music`, `mdi:playlist-music`, `mdi:shuffle-variant`, `mdi:repeat`.

---

## Twitch

**If a Twitch MCP is available**: use it to query channel state, viewer count, recent follows.

**If not**: for chat automation the easiest path is `twitch-cli` (official) or curl to the Helix API with an OAuth token.

### Shell script shape

**Send a chat message** (requires OAuth token with `chat:edit` scope):

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
# Use twitch-cli:
twitch chat send-message --from-user yourbot --to-channel "$TWITCH_CHANNEL" --message "Welcome to the stream!"
```

**Run a command shortcut via IRC** (alternative path using curl + IRC gateway is more complex; prefer twitch-cli).

**Toggle chat mode** (emote-only, followers-only) uses the Helix `PATCH /helix/chat/settings` endpoint.

### Icons

`mdi:twitch`, `mdi:chat`, `mdi:message-text`, `mdi:account-group`, `mdi:heart` (followers), `mdi:currency-usd` (bits/tips), `mdi:eye` (viewers).

---

## Shell / terminal / CLI

The simplest category. Any shell command becomes an action directly:

```python
streamdeck_create_action(
  name="Open Terminal in Project",
  command='open -a "Terminal" /path/to/project',
)
```

Common shapes:

- **Open a file/folder**: `open /path/to/thing`
- **Run a build**: `cd /path/to/repo && npm run build`
- **Invoke a dev server**: `cd /repo && npm run dev`
- **Run a custom script in the repo**: `cd /repo && ./scripts/do-thing.sh`
- **Send keyboard shortcut via AppleScript** (macOS): `osascript -e 'tell application "System Events" to keystroke "s" using {command down}'`

For clipboard or `pbcopy`/`pbpaste` automation, just chain shell:

```bash
echo "$MY_STRING" | pbcopy
```

### Icons

`mdi:terminal`, `mdi:console`, `mdi:bash`, `mdi:folder-open`, `mdi:code-tags`, `mdi:play-circle`, `mdi:power`.

---

## Browser URLs

```python
streamdeck_create_action(
  name="Open GitHub PRs",
  command='open "https://github.com/verygoodplugins/streamdeck-mcp/pulls"',
)
```

Simple and reliable. For multi-URL scripts, chain with `&&` or list separately; Stream Deck fires them sequentially.

### Icons

Per-service: `mdi:github`, `mdi:gitlab`, `mdi:slack`, `mdi:linear`, `mdi:figma`, `mdi:notion`, `mdi:world` (generic web), `mdi:link`.

---

## When you hit a service with no clean shell path

Some services (Adobe apps, proprietary desktop tools, games) are hostile to shell automation. Options, in order of preference:

1. Check if they have a URL scheme (`adobe://`, `figma://`, etc.) — a one-line `open` works.
2. Check if they have a CLI (`figma-cli`, etc.).
3. Use AppleScript on macOS (`osascript -e 'tell application "..."'`).
4. Use `osascript` to send keystrokes as a last resort (fragile — breaks if the target app's UI changes).
5. Tell the user: "I can't wire [tool] via shell reliably — would you like to set up a keyboard shortcut in [tool] and have the button send that shortcut?" Then use `osascript` to send the keystroke. This is the most reliable fallback.

## Credential hygiene

- **Never** bake a credential inline into a shell script.
- **Never** log a credential (no `echo $TOKEN`, no `set -x`).
- **Never** commit `.env` to a repo (user should `echo ".env" >> ~/StreamDeckScripts/.gitignore` if they're tracking that directory).
- For production-level secrecy, suggest the macOS Keychain (`security find-generic-password`) or 1Password CLI (`op read`) as alternatives to `.env`.
