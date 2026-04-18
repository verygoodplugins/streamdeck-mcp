# Stream Deck Profile Writer

Use this skill when you need to configure Elgato Stream Deck desktop profiles without taking USB control of the hardware.

## Default Workflow

1. Call `streamdeck_read_profiles` to discover the active profiles root and page `directory_id` values.
2. Call `streamdeck_read_page` before editing an existing page so you can inspect the current native action objects.
3. Use `streamdeck_create_icon` for button art. Pass `icon` with a Material Design Icons name like `mdi:cpu-64-bit`, `mdi:volume-high`, or `mdi:github` (~7400 glyphs bundled) plus `icon_color` and `bg_color` for a glyph; or pass `text` alone for a text-only icon. `icon` and `text` are mutually exclusive — set the button's `title` on `streamdeck_write_page` for labels, since Elgato overlays titles on images.
4. Use `streamdeck_create_action` when you want a shell-command button. It creates an executable script in `~/StreamDeckScripts/` and returns a ready-to-insert Open action block.
5. Call `streamdeck_write_page` with `directory_id` for the safest updates on existing pages.
6. Call `streamdeck_restart_app` on macOS if the Stream Deck desktop app does not pick up changes immediately.

## Practical Notes

- The default profile writer targets `ProfilesV3` when present, then falls back to `ProfilesV2`.
- `ProfilesV3` uses page UUIDs as directory names, so page identity is stable.
- `ProfilesV2` uses opaque page directory names, so treat `directory_id` as the source of truth for updates.
- `streamdeck_write_page` replaces the page by default because `clear_existing` defaults to `true`.
- Button inputs can use `key` for linear indexing or `position` for native `col,row` coordinates.

## Button Shape

Each `buttons[]` item can use:

```json
{
  "key": 0,
  "title": "Deploy",
  "icon_path": "/path/to/icon.png",
  "path": "/path/to/script.sh"
}
```

Or a raw native action object:

```json
{
  "position": "4,2",
  "title": "Next",
  "action": {
    "ActionID": "uuid-v4",
    "LinkedTitle": true,
    "Name": "Next Page",
    "Plugin": {
      "Name": "Pages",
      "UUID": "com.elgato.streamdeck.page",
      "Version": "1.0"
    },
    "Settings": {},
    "State": 0,
    "States": [{}],
    "UUID": "com.elgato.streamdeck.page.next"
  }
}
```

## When to Use the Legacy USB Server Instead

Use `server.py` only when you explicitly want direct USB hardware control, on-device rendering, brightness control, or runtime button callbacks that do not depend on the Elgato desktop app.

## Authoritative Elgato SDK References

These are the source of truth for manifest schemas, image dimensions, and touchstrip behavior. Consult BEFORE empirical probing:

- Getting started: https://docs.elgato.com/streamdeck/sdk/introduction/getting-started
- Manifest reference: https://docs.elgato.com/streamdeck/sdk/references/manifest
- Dials & Touch Strip guide: https://docs.elgato.com/streamdeck/sdk/guides/dials-and-touch-strip
- Touch Strip Layout reference: https://docs.elgato.com/streamdeck/sdk/references/touch-strip-layout

### Image dimensions (authoritative)

| Surface | Size | @2x |
|---------|------|-----|
| Keypad state image | 72×72 | 144×144 |
| Encoder dial Icon | 72×72 | 144×144 |
| Encoder touchstrip background (per segment) | 200×100 | 400×200 |
| Full-strip background (`Controllers[Encoder].Background`) | 1200×100 | — |
| Plugin icon | 256×256 | 512×512 |
| Action list icon | 20×20 | 40×40 |

### Built-in touchstrip layouts

Pass `encoder_layout: "$A1"` (etc.) on an encoder button in `streamdeck_write_page` to opt into a layout. Omit `encoder_layout` for the default (Elgato default composition with full-strip background show-through). Picking a variant forgoes show-through — the declared layout replaces the default composition.

| Layout | Semantics |
|--------|-----------|
| *(omit)* | Default: icon over `Encoder.background`, full-strip `Controllers[Encoder].Background` shows through |
| `$X1` | Title top, icon centered |
| `$A0` | Title top, full-width image canvas center |
| `$A1` | Title top, icon left, text value right |
| `$B1` | Title top, icon left, text + progress bar right |
| `$B2` | Title top, icon left, text + gradient progress bar |
| `$C1` | Title top, dual icon-left/progress-right rows |

Each variant is a separate action UUID in the bundled plugin (`io.github.verygoodplugins.streamdeck-mcp.dial.<x1|a0|a1|b1|b2|c1>`) with `Encoder.layout` statically declared — the only Elgato-documented, durable way to set a layout.

Custom layouts (JSON shipped with the plugin) are not yet supported; deferred until a concrete layout requires it.

### Touchstrip custom art goes in the profile manifest, not `setFeedback`

For static per-instance backgrounds/icons, write directly to the page manifest:

- `Controllers[Encoder].Actions[<pos>].Encoder.Icon` → per-segment 72×72 icon path
- `Controllers[Encoder].Actions[<pos>].Encoder.background` → per-segment 200×100 background path
- `Controllers[Encoder].Background` → full 1200×100 strip background path

These fields only survive a profile write when the action's plugin declares `Controllers: ["Encoder"]`. The bundled streamdeck-mcp plugin (`io.github.verygoodplugins.streamdeck-mcp.dial`) declares encoder support (no explicit `Encoder.layout` — the Stream Deck app's default encoder layout is used), so manifest writes of `Encoder.Icon`/`background` stick across quit/relaunch.
