# Dials and the Touch Strip

The Stream Deck + XL's touch strip is a 1200×100 LCD split into six 200×100 segments, one per encoder (dial). Each segment renders either a layout (title + image + value components composed per Elgato's rules) or defers to a full-strip background that shows through all six segments as one continuous ribbon.

Streamdeck-mcp gives you two levers for each dial:
1. **Action UUID variant** (the `encoder_layout` field on `streamdeck_write_page`) — static choice made at authoring time.
2. **Per-dial imagery** (the `icon_path` and `strip_background_path` fields) — the pixels that render in whichever layout slots the chosen UUID exposes.

## Built-in layouts

| Layout | Components | `setFeedback` keys (live-channel, Phase 2) | Phase 1 rendering |
|---|---|---|---|
| **(default)** — no `encoder_layout` set | Elgato's default composition (icon overlay + title) with full-strip background show-through | N/A (default composition) | ✅ Renders correctly. Best pick for themed cohesive decks. |
| **`$X1`** | title + centered icon | `title`, `icon` | ✅ Renders correctly. Clean look for toggle-style dials. |
| **`$A0`** | title + full-width canvas + small canvas overlay | `title`, `full-canvas`, `canvas` | ✅ Renders correctly. Good for splash art, album covers, per-dial images. |
| **`$A1`** | title + icon + numeric value | `title`, `icon`, `value` | ⚠️ Value slot empty in Phase 1 (no setFeedback). |
| **`$B1`** | title + icon + value + progress bar | `title`, `icon`, `value`, `indicator` | ⚠️ Value and bar empty in Phase 1. |
| **`$B2`** | title + icon + value + gradient bar | `title`, `icon`, `value`, `indicator` | ⚠️ Value and bar empty in Phase 1. |
| **`$C1`** | title + two icons + two bars | `title`, `icon1`, `icon2`, `indicator1`, `indicator2` | ⚠️ Bars empty in Phase 1. |

**Phase 1 corollary**: `setFeedback` is a live-channel call made by plugin JS. The streamdeck-mcp bundled plugin is currently a pure declarative shell (no JS logic) so it never calls `setFeedback`. The value and indicator slots on `$A1/$B1/$B2/$C1` render empty because nothing populates them. Use those layouts only if the user explicitly accepts the empty slots.

Source: <https://docs.elgato.com/streamdeck/sdk/guides/dials> and <https://docs.elgato.com/streamdeck/sdk/references/touch-strip-layout>.

## Decision tree: which UUID variant?

**On Plus XL, which encoder layout do I pick?**

- Want an immersive themed deck with a single wide background that unifies all six dials? → **Default `.dial`** (omit `encoder_layout`). Generate a 1200×100 PNG via `streamdeck_create_icon(shape="touchstrip", ...)` and set it on one encoder's `strip_background_path`; the show-through shares it across all segments. Pair with per-dial transparent-bg icon overlays (`transparent_bg=True`) on each encoder's `icon_path`.
- Want per-dial imagery with no show-through? → **`$X1`** (simple icon + title) or **`$A0`** (full-width image + title).
- Want a visible volume/brightness bar that ticks as the user rotates? → That's a **live-channel feature**. Phase 2. Use `$X1` for now with a volume icon + title, or `$A0` with a custom image; graduate when Phase 2 ships setFeedback wiring.

## Writing per-dial imagery

For an encoder, `streamdeck_write_page` accepts:

```json
{
  "controller": "encoder",
  "key": 0,
  "title": "Volume",
  "icon_path": "/path/to/72x72-transparent-icon.png",
  "strip_background_path": "/path/to/200x100-or-1200x100-bg.png",
  "encoder_layout": "$X1"
}
```

- `icon_path`: 72×72 dial face. Use `transparent_bg=True` when generating the icon so it composes cleanly over the strip background.
- `strip_background_path`: 200×100 for one segment, OR 1200×100 for the full strip (the default `.dial` UUID shares it across segments via show-through). Use `shape="touchstrip"` on `streamdeck_create_icon` for the 200×100 aspect.
- `encoder_layout`: omit for the default; set to one of the six codes for a variant.

Fields **must not combine** with `path`/`action_type`/`plugin_uuid`/`action_uuid` — those are for custom actions. The MCP validates this.

## Encoder title color is controlled by the layout, not by `title_color`

Phase 1 gotcha: on keypad buttons, `title_color` on the button spec maps to `TitleColor` in the action state and the Stream Deck app renders the title in that color. On encoders, the touchstrip layout's own `color` attribute on the `title` text item wins — `TitleColor` in the action state is ignored at render time. In practice this means encoder titles come out white (the layout default) regardless of what `title_color` you set on the button spec.

The Elgato spec (touch-strip-layout reference) states that when a Text item's `key` equals `"title"`, the property inspector grants users font customization authority, overriding layout-defined color / font / alignment. Our bundled plugin doesn't ship a property inspector, so users can't override it that way either.

Phase 1 workarounds, if white-on-default-bg isn't acceptable:
1. Bake the title text into the dial's icon PNG (`text="…"` on `streamdeck_create_icon` with a transparent background sized for the dial face). Accept that you lose Elgato's overlay-title dynamic sizing.
2. Choose backgrounds that look right behind white text.
3. Skip titles on encoders entirely (set `show_title: false` on the button spec) and rely on the icon to communicate the dial's purpose.

Phase 2 (plugin JS gains `setFeedback`) can call `setFeedback({title: {value: "...", color: "#..."}})` per-instance, closing this gap. Until then, document the limitation rather than try to paper over it.

## TriggerDescription — the free win

Each encoder action in the bundled plugin manifest declares an `Encoder.TriggerDescription` block. Stream Deck uses its values to tell the user what rotate/push/touch do when they hover or look at their dial stack. Currently the bundled plugin declares empty trigger descriptions (`"Rotate": ""`, etc.) — the Stream Deck app falls back to generic labels.

If you're authoring a deck where a dial's behavior is non-obvious, include descriptive strings in the button spec's `action.settings` or `action.Encoder` payload — the Elgato app surfaces them in the UI. (Exact path depends on how the user's version of the Stream Deck app renders them. Keep them short: "Scene brightness", "Seek track", "Mute on push".)

## Custom layouts (Phase 2+ territory)

Elgato supports custom layout JSON — a file checked into the plugin describing arbitrary text/pixmap/bar/gbar items with rects inside the 200×100 canvas. Streamdeck-mcp doesn't expose this in Phase 1 (the bundled plugin ships only the six built-in variants as static action UUIDs). If a user has a very specific per-dial visual language in mind, the Phase 1 answer is "use the default `.dial` with a custom 1200×100 background PNG" — which handles most visual wishes without custom layout JSON.

Full custom layout schema: <https://docs.elgato.com/streamdeck/sdk/references/touch-strip-layout>.

## Plus-XL-specific quirks

- **The Plus XL has 9 keypad columns, not 8.** `MODEL_LAYOUTS["20GBX9901"]` declares `(9, 4)`. This was corrected in PR #18 after empirical hardware check — writing `position: "8,0"` lands on the rightmost column, not off-grid.
- **The bundled plugin is required for per-dial imagery to survive restart.** Per-instance `Encoder.Icon` and `Encoder.background` writes get stripped by the Elgato app when quit, unless the action's plugin declares `Controllers: ["Encoder"]`. The streamdeck-mcp plugin does exactly this and nothing else. `streamdeck_write_page` auto-installs it the first time an encoder button needs it; `streamdeck_install_mcp_plugin(force=True)` upgrades after a plugin version bump.

## Sources

- <https://docs.elgato.com/streamdeck/sdk/guides/dials>
- <https://docs.elgato.com/streamdeck/sdk/references/manifest>
- <https://docs.elgato.com/streamdeck/sdk/references/touch-strip-layout>
