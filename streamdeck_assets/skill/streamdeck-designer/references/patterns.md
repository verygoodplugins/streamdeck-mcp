# Deck Patterns

Starter specs for common deck archetypes. These aren't copy-paste templates — they're starting shapes you adapt to the user's real integrations, hardware, and preferences. Every user's deck looks different even if they started from the same pattern.

## 1. Streamer deck (Plus XL, hello-kitty theme)

See `assets/recipes/streamer-hello-kitty.json` for the fully-baked JSON equivalent of this pattern.

**Hardware**: Plus XL (9×4 keys + 6 dials + touchstrip).
**Theme**: Kawaii (pink/white), Strategy A.
**Integrations**: OBS, Hue, Twitch.

**Encoders (top priority — these are the continuous controls)**:
- Dial 0: Master volume (icon: `mdi:volume-high`). Rotate for volume, push for mute. *Note: in Phase 1 the volume value won't update live; the dial is a launch point, not a live display.*
- Dial 1: Mic volume (`mdi:microphone`).
- Dial 2: Scene brightness via Hue (`mdi:lightbulb-on`).
- Dial 3: Chat scroll (`mdi:chat`). Push to clear recent.
- Dial 4: Alerts volume (`mdi:heart`).
- Dial 5: Master brightness (`mdi:brightness-6`).

**Touchstrip**: single 1200×100 pink-gradient background spanning all six segments. Each dial icon is `transparent_bg=True`, 72×72, composing cleanly.

**Keypad row 0 (scene switches)**:
- Keys 0–4: scenes (Starting Soon, Just Chatting, Gameplay, BRB, End). Each uses `obs-cli scene current <name>`.
- Key 5: Go Live (record + stream toggle, combines `obs-cli stream start` and `obs-cli record start`).
- Keys 6–8: chat shortcuts (welcome, lurk command, schedule).

**Keypad row 1 (mic/camera/sources)**:
- Keys 9–10: mic / camera toggles (`obs-cli audio toggle "Mic/Aux"`, `obs-cli audio toggle "Camera"`).
- Keys 11–13: scene sources (game capture, browser source, alerts overlay).
- Keys 14–17: Hue scenes (Chill, Focus, Stream, Break).

**Keypad row 2 (effects / alerts)**:
- Keys 18–23: sound effects (via `afplay /path/to/sound.wav` on macOS or equivalent).
- Keys 24–26: alerts / overlays toggles.

**Keypad row 3 (utilities / navigation)**:
- Keys 27–29: browser URLs (Twitch dashboard, OBS Studio, Discord).
- Keys 30–31: volume presets or meta actions (all sources muted, emergency back to Starting Soon).
- Keys 32–35: nav keys (page next/prev, or profile switch).

This is a starting shape. Adapt: drop rows the user doesn't need; add sound effects as they name them; re-color based on their exact reference.

## 2. Per-repo dev deck (XL, Nordic theme)

See `assets/recipes/dev-nordic.json` for the JSON equivalent.

**Hardware**: XL (8×4).
**Theme**: Nordic, Strategy A.
**Integrations**: GitHub, shell, browser, terminal.

Before authoring, examine the user's repo. Key signals:
- `package.json` scripts → buttons for `dev`, `build`, `test`, `lint`, `deploy`.
- `Makefile` targets → buttons for each.
- `pyproject.toml` entry points → buttons for common dev commands.
- `.github/workflows/` → CI status links.
- Presence of Docker / docker-compose → start/stop containers.

**Column 0 (build/run)**:
- Key 0: `npm run dev` (or equivalent). Icon: `mdi:play-circle`.
- Key 8: `npm run build`. Icon: `mdi:package-variant`.
- Key 16: `npm test`. Icon: `mdi:test-tube`.
- Key 24: `npm run lint`. Icon: `mdi:check-circle`.

**Column 1 (git / GitHub)**:
- Key 1: Open GitHub PRs page. Icon: `mdi:github`.
- Key 9: Open current branch on GitHub. Icon: `mdi:source-branch`.
- Key 17: Open Actions / CI. Icon: `mdi:robot`.
- Key 25: Open Issues. Icon: `mdi:bug`.

**Column 2 (env)**:
- Key 2: Docker up. Icon: `mdi:docker`.
- Key 10: Docker down.
- Key 18: Clear logs.
- Key 26: Clear cache.

**Columns 3–6**: per-service or per-module shortcuts (specific to the repo).

**Column 7 (terminal/editor)**:
- Key 7: Open in VSCode (`code /path/to/repo`).
- Key 15: Open Terminal at repo (`open -a Terminal /path/to/repo`).
- Key 23: Open `.env` or config file.
- Key 31: Switch to dev profile (meta nav).

Dev decks benefit from per-repo pages — give each repo its own page, navigate with `page.next`/`page.previous`.

## 3. Music-player deck (Original 5×3, retrowave theme)

See `assets/recipes/music-retrowave.json` for the JSON equivalent.

**Hardware**: Original (5×3, 15 keys). No encoders.
**Theme**: Retrowave, Strategy B (neon on midnight).
**Integrations**: Spotify (via spotipy) or Apple Music (via `osascript`).

**Row 0 (playback)**:
- Key 0: Previous track. Icon: `mdi:skip-previous`, color `#00f5ff` on `#1a1a2e`.
- Key 1: Play / Pause. Icon: `mdi:play-pause`.
- Key 2: Next track. Icon: `mdi:skip-next`.
- Key 3: Shuffle toggle. Icon: `mdi:shuffle-variant`.
- Key 4: Repeat toggle. Icon: `mdi:repeat`.

**Row 1 (volume / mood presets)**:
- Key 5: Volume down 10%. Icon: `mdi:volume-low`.
- Key 6: Volume up 10%. Icon: `mdi:volume-high`.
- Key 7: Chill playlist. Icon: `mdi:music-note-eighth`.
- Key 8: Focus playlist. Icon: `mdi:headphones`.
- Key 9: Party playlist. Icon: `mdi:party-popper`.

**Row 2 (discovery / meta)**:
- Key 10: Show current track in Spotify (`open -a Spotify`).
- Key 11: Save track to library. Icon: `mdi:heart`.
- Key 12: Queue this track. Icon: `mdi:playlist-plus`.
- Key 13: Open Spotify radio from current artist.
- Key 14: Mute system audio.

Volume presets work well because Phase 1 can't render a live volume bar — discrete bumps are more legible as buttons than as a "virtual dial."

## 4. Home-control deck (XL, Nature theme)

**Hardware**: XL (8×4) or Plus XL.
**Theme**: Nature / Forest, Strategy A.
**Integrations**: Home Assistant (preferred via HA MCP) or Hue direct.

**Organize by room, one row per room**:
- Row 0: Living room — lights on/off, scene selector (chill/movie/bright), TV toggle.
- Row 1: Kitchen — lights, appliances, radio.
- Row 2: Bedroom — lights, fan, alarm.
- Row 3: House-wide — "all off", "goodnight scene", "arrive home", security toggles.

**Plus XL adds**: encoders for continuous values — master brightness, thermostat setpoint, fan speed, music volume, blind position.

## 5. Claude-companion deck (Plus XL, Terminal theme) — static parts only

This pattern looks ahead to Phase 2 but ships Phase 1 compatible.

**Hardware**: Plus XL.
**Theme**: Terminal (CRT green), Strategy B.
**Integrations**: shell (Claude Desktop, Claude Code launch, terminal open).

**Encoders**: reserved for Phase 2 (agent hyperparameters). In Phase 1, label them "Reserved" with placeholder icons, or use them for generic system volume/brightness.

**Keys**: launch Claude Code in specific projects, open terminal, quick commands, clipboard actions. The real "Claude companion" features (ambient status, press-to-answer, thinking indicator) wait for Phase 2.

## Composing patterns together

Real users don't fit one pattern perfectly. A streamer who codes wants a streamer deck *and* a dev deck — on two profiles, navigable via the profile-switch action. A musician/dev wants music controls mixed into their dev deck.

The skill's job is to mix these thoughtfully:
- Don't squash two full patterns onto one page — it becomes busy.
- Do pick the most-used 60% of each and put them on separate pages.
- Do use a **consistent theme across all pages** even if the pages differ functionally. The theme is what makes the whole device feel like it's the user's, not a demo.

## Asking the user what to include

When a pattern has more options than the hardware can fit, always ask. "I have room for 15 keys on your Original. Streamer decks typically want: [top 10]. What else from these: [next 10]?" The user picks; you author. Don't silently drop or add.
