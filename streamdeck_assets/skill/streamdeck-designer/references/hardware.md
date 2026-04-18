# Stream Deck Hardware Reference

Consult before starting a layout if you don't already know the user's model's tradeoffs. All dimensions come from `MODEL_LAYOUTS` in `profile_manager.py` — if those change, this file is stale. Verify with `streamdeck_read_profiles`, which reports both the raw product ID (`Model`) and a human-readable `ModelName` per profile — always prefer `ModelName` when writing about the user's device (it eliminates any chance of mis-translating the Elgato product code).

## Models at a glance

Elgato's current lineup includes **four distinct SKUs with "+" or "XL" in the name**. Don't conflate them; the key counts and dial counts differ.

| Model name | Product ID | Keypad | Encoders | Touchstrip | Best for |
|---|---|---|---|---|---|
| Stream Deck Original | `20GBA9901` | 5 × 3 = 15 keys | — | — | Focused action set; tight 3-button-per-context groupings |
| Stream Deck MK.2 | `20GAA9901` | 5 × 3 = 15 keys | — | — | Same as Original; updated firmware |
| Stream Deck Mini | `20GAI9501` | 3 × 2 = 6 keys | — | — | Travel; single-purpose dashboards; power user shortcuts |
| Stream Deck XL | `20GAT9902` | 8 × 4 = 32 keys | — | — | Large action surfaces; clustered workflows; streamer decks |
| Stream Deck XL rev2 | `20GBA9902` | 8 × 4 = 32 keys | — | — | Same hardware as XL, updated firmware |
| **Stream Deck +** (original Plus, 2022) | *ID unknown — see note* | 4 × 2 = 8 keys | **4 × 1** | 800 × 100 | Budget control surface with dials; older/smaller sibling of + XL |
| **Stream Deck + XL** (the big Plus, 2025) | `20GBX9901` | **9 × 4 = 36 keys** | **6 × 1** | **1200 × 100** | Pro streaming / control surfaces with 6 continuous knobs |
| Stream Deck Neo | `20GBD9901` | 4 × 2 = 8 keys | — | Embedded clock/weather strip (not separately addressable today) | Entry-level; always-on ambient bar |
| UI Stream Deck / AI Stream Deck (emulators) | `"UI Stream Deck"`, `"AI Stream Deck"` | 4 × 2 = 8 keys | — | — | Elgato app's virtual companion deck (the app renamed the emulator from "UI" to "AI" in recent builds) |

**The "+ XL" and the original "+" are two different devices, not variants of one.** If `streamdeck_read_profiles` returns `ModelName: "Stream Deck + XL"`, the user has the 36-key / 6-dial version. If it says `Stream Deck +` (the original Plus), it's the 8-key / 4-dial version — half the keys, two-thirds the dials, a narrower touchstrip. Never pattern-match "+ XL" to "Plus (non-XL)."

**Status of the original + in this MCP**: the Elgato-app product ID for the original Stream Deck + has not yet been observed in any profile manifest this project has seen, so it's absent from `MODEL_LAYOUTS`. If `streamdeck_read_profiles` returns a `ModelName` of `Unknown Stream Deck model (<id>)` and the user says they have an original Plus, capture that product ID and add it to `MODEL_LAYOUTS` in a follow-up PR. Until then, profiles on that device will fall back to the 5×3 layout and you'll need to author against the 8-key/4-dial shape explicitly (use `position: "col,row"` with bounds 0–3 / 0–1 for keypad, 0–3 / 0 for encoders).

## Per-model authoring guidance

### Stream Deck Original / MK.2 (5×3)
Every key matters. Resist the urge to fill all 15. A good setup is often 8–10 deliberately chosen actions + a "more" button that navigates to a secondary page for overflow. Row 1 (keys 0–4) gets the most-pressed actions. Middle row is fine for "always context" indicators. Bottom row is comfortable for nav + destructive actions (reset, clear).

### Stream Deck XL (8×4)
Space to organize. Use 4-key-wide clusters — column-groupings around a theme (a column for mic, a column for camera, a column for scenes, a column for effects). The two bottom corners (keys 24 and 31) are the most comfortable physically — reserve them for frequent-plus-meaningful actions.

### Stream Deck + (original Plus, 4×2 + 4 encoders + 800×100 touchstrip)
Not yet supported — the Elgato-app product ID is unknown to this MCP (no observed profile). If a user has one, author as if it were a 4×2 keypad + 4 encoders + 4-segment touchstrip (each segment 200×100). The design idioms from + XL apply at smaller scale: encoders for continuous values, keypad for discrete actions. Flag to the user that full layout validation against their device isn't possible until the product ID is added to `MODEL_LAYOUTS`.

### Stream Deck + XL (9×4 + 6 encoders + 1200×100 touchstrip)
The encoders are the magic. Reach for them for **continuous values** (master volume, scene brightness, song position, room temperature, CPU throttle percentage). The keypad stays for discrete actions. The touch strip is six 200×100 segments, one per encoder, that show contextual info for the dial above.

Layout idioms that work:
- **Encoder-row first**: design the 6 encoders before touching keys. They're the user's most-ergonomic control surface — getting them right anchors the whole deck.
- **Full-strip background**: use `shape="touchstrip"` to render a single 1200×100 image that spans all six segments (e.g. a wide retrowave skyline). Pair with per-dial transparent icon overlays. See `dials-and-touchstrip.md` for the default vs layout-variant tradeoff.
- **Keypad as launcher, encoders as adjuster**: presses switch context; rotates refine within context.

### Stream Deck Mini (3×2)
Six slots. One dedicated dashboard, not a launcher. Examples: a travel deck (airplane mode, VPN, hotspot, flashlight, timer, compass); a focus deck (Pomodoro start, mute all, focus mode on, music play, lights dim, done).

### Stream Deck Neo (4×2)
Eight keys + a built-in info bar with clock/weather (rendered by the Elgato app, not currently addressable via streamdeck-mcp). Design as if the info bar is always there — don't duplicate clock/weather in your layout. Key layout is cramped enough that you want 4 pressable actions + 4 navigation keys, not 8 flat actions.

## Button indexing

All `key` values are 0-based and row-major (left to right, then top to bottom). For a 5×3 Original:

```
 0  1  2  3  4
 5  6  7  8  9
10 11 12 13 14
```

For an 8×4 XL, the same pattern continues: key 7 is top-right, key 24 is bottom-left, key 31 is bottom-right.

Encoders index 0–5 left-to-right. Touch-strip segments align to their encoders.

If you prefer named positions, pass `"position": "col,row"` instead of `key`. Same semantics, different API.

## Reading the current state

Always begin with `streamdeck_read_profiles`. For each profile you get a name, a `directory_id` (ProfilesV3) or numeric page offsets (ProfilesV2), model info, and per-page metadata.

If you plan to overwrite, run `streamdeck_read_page` on the target to see what's there. If it's empty or already placeholder, write freely. If it's populated with user content, confirm with the user before overwriting.

## Screen vs page terminology

Elgato's "profile" maps to a *context* (e.g. "Streaming", "Coding"). A profile contains **pages** — what the device shows on screen at any moment. Pages inside a profile navigate with the built-in "page.next"/"page.previous" actions. Profiles switch via the profile-switch action (or automatically via "applications to monitor" rules, which streamdeck-mcp doesn't currently write). For most layout tasks, stay inside one profile and one page; add pages only when the user has more than fits.

## Source

Model data comes from `profile_manager.py`'s `MODEL_LAYOUTS` dict and the Elgato SDK's device-type reference at <https://docs.elgato.com/streamdeck/sdk/references/device-types>.
