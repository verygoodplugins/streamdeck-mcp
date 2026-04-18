---
name: streamdeck-designer
description: Design, theme, and author complete Stream Deck layouts for the user's hardware using the streamdeck-mcp tools. Use whenever the user wants a custom Stream Deck setup, asks for a themed deck (e.g. "hello-kitty Twitch deck", "retrowave music controls", "a dev deck for this repo"), wants buttons or dials configured for specific apps (OBS, Hue, Spotify, Home Assistant, Twitch, etc.), or asks Claude to "set up" / "build" / "make" / "configure" a Stream Deck page — even if they don't explicitly say "streamdeck-mcp" or "profile." Also triggers when they mention Stream Deck + / + XL dials, encoders, or the touch strip, or when they describe an aesthetic they want reflected on their deck.
---

# Stream Deck Designer

You are designing a Stream Deck layout for the user. The streamdeck-mcp tools let you author it directly to disk; the Elgato desktop app picks it up on next launch and the deck lights up exactly how you composed it. Your job is to produce something cohesive, useful, and visually considered — not a randomly-placed grid of icons.

A good authored deck:
- Has a deliberate palette and typography (not whatever colors land by accident).
- Reflects how the user actually works (their real apps, their real scenes, their real shortcuts).
- Runs standalone — every button does something even when Claude is offline.
- Tells the user what each control does without them having to guess.

## Follow this authoring order

Resist the urge to start generating icons before the structure is decided. Every reordering of these steps increases the chance of wasted work.

### 1. Inventory the hardware before anything else

Call `streamdeck_read_profiles` first. This tells you which profiles exist, what model each profile is bound to, and which pages are populated. Never assume a layout — Original (5×3 keys), MK.2 (5×3), XL (8×4), Plus XL (9×4 keys + 6 encoders with a 1200×100 touch strip), Mini (3×2), and Neo (4×2) are all in active use, and the tradeoffs differ. See `references/hardware.md` for per-model guidance.

If you're replacing existing content, call `streamdeck_read_page` for the target page and inspect what's already there. Confirm with the user that overwriting is OK — a deck full of the user's prior work is precious, even if it looks generic.

### 2. Understand intent before designing

Ask, don't guess:
- What's the activity? (streaming, coding, music, home control, presenting, gaming)
- What aesthetic? (a theme name like "retrowave" or "hello kitty"; or a color palette; or a reference image)
- Which integrations? (OBS, Hue, Home Assistant, Spotify, Twitch — specific products, not categories)
- Which profile and page? (they may have a dedicated profile per activity; don't auto-pick)

Fill gaps with sensible defaults, but if the user gave you a theme name, don't silently reinterpret it. If they said "hello kitty" and you're about to render blue icons, stop and check.

### 3. Plan the palette and typography before rendering any icon

Pick **3–5 colors** before you generate a single icon. Decide the icon-color strategy up front — the three viable ones:

- **Theme-on-neutral**: colored icons on a dark or white bg. High contrast, works on any hardware. The safe default.
- **Neutral-on-theme**: white or black icons on themed backgrounds. Bolder; good for strong brand aesthetics.
- **Dual-tone**: alternating pairs. Good for visual rhythm across a large grid but harder to theme consistently.

Pick one strategy and keep it across the whole page. Mixing strategies is what makes a deck look like someone grabbed random emoji.

Show the user the palette (name the colors + one sentence on the strategy) before you start generating icons. Correcting direction after 30 icons exist is expensive.

See `references/themes.md` for archetypes (kawaii, retrowave, brutalist, nordic, terminal, nature, minimal, corporate) with ready palettes and per-archetype icon-color strategies.

### 4. Plan the layout against the hardware

Write out the grid before you author anything. For each slot describe: what lives here, what happens on press, which icon (by MDI name), what title.

On **Plus XL** (the hardware with encoders): encoders are the user's always-visible continuous-control surface — reach for them first for the *most-used continuous values* (volume, brightness, current scene, song scrub). Use keypad slots for discrete actions (toggle, launch, switch). The touch strip is shared across all four rendering slots (200×100 each) — see `references/dials-and-touchstrip.md` for which layout fits which use.

For **XL and Plus XL** (the large grids): group related actions. A row of scene switches stays together. A column of mic controls stays together. The top row gets the most-pressed actions. A cluster of matching colors reads as "these belong together" without words.

For **Original / MK.2 / Neo / Mini**: fewer slots, so every slot matters more. Often the right answer is 2–3 essential actions + navigation to secondary pages, not jamming everything onto one page.

### 5. Discover integrations at authoring time, don't guess endpoints

When the user names an integration, check what you have access to **right now** in this session:

- If a matching MCP is available (Hue MCP, Home Assistant MCP, Spotify MCP, OBS MCP), **use it** to enumerate the user's real devices, scenes, rooms, playlists. The goal is that when the user presses "Chill Scene" on the deck, their actual living-room Hue scene named "Chill" activates — not a placeholder.
- If no matching MCP is available, **ask the user** for the endpoints, credentials, bridge IPs, auth tokens you need. Tell them plainly what you're going to do with each (e.g. "I'll store your Hue API key in ~/StreamDeckScripts/.env — nothing outside your machine").

Bake the discovered invocations into **shell scripts** via `streamdeck_create_action`. Those scripts run standalone — they don't need Claude or the MCP server to be present at press time. That's the whole point of the static authoring model.

**Never inline credentials into the action scripts.** Put secrets in `~/StreamDeckScripts/.env`; source it in each generated script:

```bash
#!/bin/bash
set -a; source "$HOME/StreamDeckScripts/.env"; set +a
curl -s "http://$HUE_BRIDGE_IP/api/$HUE_API_KEY/groups/1/action" \
  -X PUT -d '{"scene": "chill-scene-id"}'
```

See `references/integrations.md` for per-service patterns (Hue, OBS, Spotify, Home Assistant, Twitch, shell/terminal, browser URLs).

### 6. Generate icons with consistent parameters

For every button that needs an icon, call `streamdeck_create_icon` with:
- Your planned palette's `icon_color` and `bg_color`.
- For keypad keys that will also show a title at the bottom: `icon_scale` around `0.75`–`0.85` (leaves visual room for the title overlay).
- For encoder dial faces and any icon that fills its canvas edge-to-edge: `icon_scale=1.0` (matches Elgato's own native icon sizing).
- For icons that will composite over a touchstrip background: `shape="touchstrip"` for the 200×100 segment background, and `transparent_bg=True` on dial icons that overlay it.

**`icon` and `text` are mutually exclusive.** The Stream Deck app draws the button's `title` *over* its image, so if you bake text into the PNG and also set a title, the text doubles up. For labeled icon buttons: pass only `icon` to `streamdeck_create_icon`, then set `title` in the `streamdeck_write_page` button spec.

If an MDI name misses, `streamdeck_create_icon` returns close-match suggestions. Take them — the exact right glyph for a concept is often named something slightly different (e.g. `mdi:cog` vs `mdi:gear`). `references/icons.md` has 30+ categorized exemplars.

### 7. Wire actions with shell scripts

For commands, use `streamdeck_create_action(name, command)`. It:
- Writes an executable script to `~/StreamDeckScripts/<slug>.sh`.
- Returns a native `com.elgato.streamdeck.system.open` action block you pass into `streamdeck_write_page`.

For page navigation between pages in the same profile, use `action_type: "next_page"` or `action_type: "previous_page"` on the button. For opening a URL, `command="open 'https://...'"` works on macOS; Windows uses `start`.

For switching to a **different profile** on press, that's not exposed as a convenience field — build the action object explicitly with `plugin_uuid: "com.elgato.streamdeck.profile"` and the profile-switch action UUID. Most decks don't need this; if you need it, check the Elgato SDK reference.

No other action types exist standalone in Phase 1. In particular: there is no "call back to Claude" action yet — pressing a key fires a shell script or switches a page, nothing else. See Phase 2 in the repo roadmap if the user asks about live/dynamic behavior.

### 8. Pick encoder layouts with the Phase 1 constraint in mind

The bundled plugin ships seven dial variants: a default (`.dial`) that shows the full-strip background through, plus six layout variants (`.dial.x1`/`.a0`/`.a1`/`.b1`/`.b2`/`.c1`) each bound to one of Elgato's built-in touch-strip layouts.

In Phase 1 **only the default `.dial`, `$X1`, and `$A0` render fully.** The value-carrying layouts (`$A1`, `$B1`, `$B2`, `$C1`) have empty `value` / `indicator` slots because that data comes from a live `setFeedback` call in plugin JS, which Phase 1's plugin shell does not make. If the user asks for a "volume bar that ticks up", tell them plainly: that's live-channel behavior and lands in Phase 2 — in the meantime, use `$X1` with a volume icon and a numeric title, or `$A0` with a custom image.

Prefer the default `.dial` (no `encoder_layout` field) for immersive themed decks: author one big 1200×100 touch-strip background image and per-dial icon overlays; the user sees a continuous themed ribbon with their dial icons composed on top. This is the most visually cohesive look on Plus XL.

Set `TriggerDescription` on each encoder so the Stream Deck app's tooltip tells the user what rotate/push/touch do. This is pure manifest — works in Phase 1.

See `references/dials-and-touchstrip.md` for the full decision tree.

### 9. Write in one pass

Batch every button and dial into a single `streamdeck_write_page` call:

```python
streamdeck_write_page(
  profile_id="<from step 1>",
  directory_id="<from step 1>",
  buttons=[
    {"controller": "keypad", "key": 0, "title": "Go Live", "icon_path": "...", "action": {...}},
    {"controller": "keypad", "key": 1, ...},
    {"controller": "encoder", "key": 0, "title": "Volume", "icon_path": "...", "strip_background_path": "..."},
    ...
  ],
  clear_existing=True,
  auto_quit_app=True,  # if the Elgato app is running, quit it before writing
)
```

The writer refuses to run while the Elgato desktop app is up (its in-memory cache would overwrite your manifest the next time it quits). Pass `auto_quit_app=True` to quit it gracefully. After the write, call `streamdeck_restart_app` so the device reloads with your new layout.

If the page uses encoder buttons, the writer auto-installs the bundled streamdeck-mcp Stream Deck plugin the first time — no separate step needed. You can call `streamdeck_install_mcp_plugin` explicitly if you want to force-reinstall after a plugin version bump.

### 10. Verify before claiming done

After the write:
1. Call `streamdeck_read_page` and diff against your intended spec. Every button you meant to write should be present; no stray buttons from a previous layout.
2. Tell the user what to verify on-device — "the deck should show the new layout now; try pressing button 3 to confirm the mic toggle works." Physical verification is on them; don't declare success on their behalf.
3. If a button depends on credentials in `.env`, check whether that file exists and has placeholders filled in. If not, tell the user which env vars they need to set before the action will work.

## Guardrails

**Don't**:
- Bake secrets into generated scripts. Always use the `.env` + `source` pattern.
- Mix `icon` and `text` on the same `streamdeck_create_icon` call — they double up with the title overlay.
- Use the `$A1/$B1/$B2/$C1` encoder layouts in Phase 1 unless the user has explicitly accepted the empty-value-slot gap.
- Generate 30 icons with different color hexes because you forgot the planned palette.
- Overwrite pages without reading them first.
- Ask the user to quit their Elgato app manually — pass `auto_quit_app=True` and let the tool handle it.

**Do**:
- Show the palette before rendering icons.
- Set `TriggerDescription` on every encoder.
- Prefer a consistent icon-color strategy across the whole page.
- Use companion MCPs to discover the user's actual scenes/devices — don't guess endpoints.
- Name actions in `streamdeck_create_action` descriptively (the name becomes the shell script filename — `scene-chill.sh` beats `action1.sh`).

## When the user wants more than static authoring

If they describe behavior like "the dial value updates live as I rotate it," "the button should flash when CI goes red," "I want Claude to render progress as the build runs," or "the button should show what Claude is thinking about" — that's **Phase 2** (live channel, setFeedback wiring, MCP-callback actions). Say so plainly: "That's a live/dynamic behavior; the current MCP handles static authoring. Phase 2 adds the live channel — it's on the roadmap."

Don't try to fake it with heuristics (e.g. a shell script that polls every 5 seconds and rewrites the manifest). Manifest rewrites require the Elgato app to be down, so polling at runtime doesn't work. Better to tell the user the honest shape of the system.

## Reference files

Loaded on demand, not by default. Consult them when:

- `references/hardware.md` — before step 1, if you're unfamiliar with the user's model's tradeoffs.
- `references/dials-and-touchstrip.md` — whenever the user has a Plus XL or mentions dials/encoders/touchstrip.
- `references/icons.md` — when picking MDI glyphs; carries 30+ categorized exemplars and scaling guidance.
- `references/themes.md` — when the user names a theme and you want a starting palette + strategy rather than inventing from scratch.
- `references/integrations.md` — per-service recipes (Hue, OBS, Spotify, Home Assistant, Twitch, browser, shell).
- `references/patterns.md` — starter page specs for common deck archetypes (streamer, per-repo dev, music, home-control).
- `references/troubleshooting.md` — when a write succeeds but the deck doesn't reflect it, icons render wrong, or an encoder icon vanishes after restart.
