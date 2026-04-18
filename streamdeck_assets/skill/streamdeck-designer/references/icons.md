# Icons

`streamdeck_create_icon` renders icons from the bundled Material Design Icons font (~7400 glyphs, offline, no network). Pass an MDI name and colors; get back a filesystem path to a PNG you hand to `streamdeck_write_page`.

## Calling the tool

```python
streamdeck_create_icon(
  icon="mdi:microphone",     # or just "microphone" — the "mdi:" prefix is optional
  icon_color="#ff4444",      # the glyph
  bg_color="#ffe0f0",        # the canvas behind (ignored when transparent_bg=True)
  icon_scale=0.8,            # fraction of canvas the glyph bbox fills
  shape="button",            # "button" → 72×72, "touchstrip" → 200×100
  transparent_bg=False,      # True → RGBA canvas, no bg_color fill
  filename="mic-off"         # optional; auto-generated if omitted
)
```

Returns `{"path": "..."}` — pass `result["path"]` as the button's `icon_path`.

## The `icon` vs `text` rule

`icon` and `text` are **mutually exclusive**. The Stream Deck app overlays a button's `title` (set on `streamdeck_write_page`) on top of its image. If you bake text into the PNG *and* set a title, the text doubles up on-screen. For labeled icon buttons:

- Pass only `icon` (or only `text`) to `streamdeck_create_icon`.
- Put the label in the button's `title` field on `streamdeck_write_page`.

## Scaling

- **Keypad keys with a bottom title**: `icon_scale=0.75-0.85`. Leaves breathing room for the title overlay.
- **Keypad keys without a title**: `icon_scale=0.9-1.0`. Edge-to-edge.
- **Encoder dial icons**: `icon_scale=1.0`, `transparent_bg=True`. Matches Elgato's own native icon sizing; composes cleanly over the touchstrip background.
- **Touchstrip backgrounds**: `shape="touchstrip"`, `icon_scale=0.5-0.8`. Larger canvas (200×100) so you often want less fill.

The `icon_scale` parameter is bounding-box accurate (fraction of canvas filled by the glyph's bbox, not the font em). Default is `1.0`.

## Color strategy as a whole page

Pick one strategy before generating icons; apply it across every icon on the page. Mixing strategies is the single biggest source of "this deck looks random":

**Strategy A — theme-on-neutral**: colored icons, dark or white canvas. Safe default. Works with any palette; high contrast; reads well at arm's length.
```python
icon_color="#ff8faa",  # theme pink
bg_color="#1a1a1a",    # near-black
```

**Strategy B — neutral-on-theme**: white or black icons, themed canvas. Bolder; brand-forward. Use when the theme colors are the vibe.
```python
icon_color="#ffffff",  # white glyph
bg_color="#ff8faa",    # theme pink canvas
```

**Strategy C — dual-tone**: alternating pairs (e.g. pink bg + white icon, black bg + pink icon). Creates rhythm across a large grid. Harder to keep coherent — use only if you're intentional about the pattern.

## Fuzzy match on miss

If `icon="mdi:cat-face"` has no exact match, the tool returns suggestions like `["mdi:cat", "mdi:face", "mdi:emoticon-cool"]`. Take the closest one that fits the concept. Don't keep guessing names — the suggestions are already ranked.

## Categorized exemplars

Quick reference to cut down name-search time. All work without `mdi:` prefix.

### Streaming / creator
`mdi:video-wireless`, `mdi:broadcast`, `mdi:record-circle`, `mdi:microphone`, `mdi:microphone-off`, `mdi:camera`, `mdi:camera-off`, `mdi:monitor-screenshot`, `mdi:account-voice`, `mdi:chat-processing`, `mdi:twitch`, `mdi:youtube`, `mdi:discord`, `mdi:message-text`, `mdi:eye` (viewers), `mdi:heart` (follows), `mdi:currency-usd` (tips), `mdi:pause-circle`, `mdi:skip-next`, `mdi:rewind`

### Dev / coding
`mdi:github`, `mdi:git`, `mdi:code-braces`, `mdi:code-tags`, `mdi:terminal`, `mdi:docker`, `mdi:bash`, `mdi:cpu-64-bit`, `mdi:memory`, `mdi:bug`, `mdi:test-tube`, `mdi:checkbox-marked-circle`, `mdi:alert-circle`, `mdi:file-code`, `mdi:folder-open`, `mdi:api`, `mdi:server`, `mdi:database`, `mdi:package-variant`, `mdi:language-python`, `mdi:language-typescript`, `mdi:nodejs`

### Music
`mdi:music`, `mdi:music-note`, `mdi:playlist-music`, `mdi:spotify`, `mdi:apple`, `mdi:play`, `mdi:pause`, `mdi:skip-forward`, `mdi:skip-backward`, `mdi:shuffle-variant`, `mdi:repeat`, `mdi:volume-high`, `mdi:volume-medium`, `mdi:volume-low`, `mdi:volume-off`, `mdi:headphones`, `mdi:microphone-variant`

### Home / IoT
`mdi:lightbulb`, `mdi:lightbulb-on`, `mdi:lightbulb-off`, `mdi:ceiling-light`, `mdi:lamp`, `mdi:thermometer`, `mdi:thermostat`, `mdi:fan`, `mdi:air-conditioner`, `mdi:garage`, `mdi:door`, `mdi:door-open`, `mdi:lock`, `mdi:lock-open`, `mdi:camera-outline`, `mdi:motion-sensor`, `mdi:home-automation`, `mdi:home`, `mdi:power`

### System / OS
`mdi:apple-keyboard-command`, `mdi:apple-keyboard-option`, `mdi:apple-keyboard-control`, `mdi:apple-keyboard-shift`, `mdi:monitor`, `mdi:laptop`, `mdi:cellphone`, `mdi:wifi`, `mdi:wifi-off`, `mdi:bluetooth`, `mdi:battery`, `mdi:volume-high`, `mdi:brightness-6`, `mdi:weather-sunny`, `mdi:weather-night`

### UI / actions
`mdi:cog`, `mdi:account`, `mdi:magnify`, `mdi:plus`, `mdi:minus`, `mdi:check`, `mdi:close`, `mdi:content-copy`, `mdi:content-paste`, `mdi:arrow-left`, `mdi:arrow-right`, `mdi:chevron-left`, `mdi:chevron-right`, `mdi:dots-horizontal`, `mdi:refresh`, `mdi:reload`, `mdi:star`, `mdi:bookmark`, `mdi:pin`, `mdi:eye`, `mdi:eye-off`

### Emotive / aesthetic
`mdi:heart`, `mdi:star`, `mdi:sparkles`, `mdi:emoticon`, `mdi:fire`, `mdi:flash`, `mdi:crown`, `mdi:diamond`, `mdi:shield`, `mdi:trophy`, `mdi:rocket`, `mdi:palette`, `mdi:paintbrush`

## When nothing fits

MDI is wide (~7400 glyphs) but not infinite. If the exact concept isn't there:

- Try synonyms — "light" vs "lightbulb" vs "lamp" vs "illuminance"; "volume" vs "speaker" vs "audio".
- Fall back to `text="XYZ"` for a short text icon (but remember: the title overlay still applies, so use text icons only when the button has no title).
- For branded services that aren't in MDI (Adobe, Figma, specific games), a text-based icon or a custom PNG is the answer — create the PNG separately and pass its path as `icon_path` directly, skipping `streamdeck_create_icon`.

## Sources

- MDI is bundled via `materialdesignicons-webfont.ttf` + `mdi-meta.json` in `streamdeck_assets/`.
- License: Apache 2.0 (MDI-LICENSE in `streamdeck_assets/`).
- Full MDI catalog: <https://pictogrammers.com/library/mdi/>.
