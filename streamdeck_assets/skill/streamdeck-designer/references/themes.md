# Theme Archetypes

Starter palettes + strategy for common aesthetics. These aren't prescriptive — adapt to the user's exact reference if they give you one. If they just said the theme name, these defaults get you 80% there.

Each archetype lists: the palette (3–5 hex codes), the icon-color strategy (A/B/C as defined in `icons.md`), typography note, and one example MDI glyph + color combo for a "play" button to anchor the style.

## Kawaii / Hello Kitty

Pastel pink-dominant, soft. Reads as cute without being clinical.

```
Palette:       #ff8faa (primary pink), #ffe0f0 (pale pink), #ffffff (white), #1a1a1a (near-black for contrast)
Accent:        #ffd700 (gold for emphasis/highlights)
Strategy:      A (theme-on-neutral) — pink/gold icons on near-white canvases; use Strategy B for 1–2 "hero" buttons in reverse
Typography:    Default title; `title_color="#1a1a1a"` on pale backgrounds, `#ffffff` on pink
Example:       icon="mdi:heart", icon_color="#ff8faa", bg_color="#ffe0f0"  — play button equivalent
```

Good for streamers targeting kawaii/anime communities, casual creators, personal-brand decks. Avoid for technical/corporate contexts unless the user *wants* the contrast.

## Retrowave / Synthwave

Saturated pink + cyan + deep purple, with neon glow. Dark canvases essential — retrowave dies on white.

```
Palette:       #ff006e (neon pink), #00f5ff (cyan), #7209b7 (deep purple), #1a1a2e (midnight bg), #ffb703 (sun-yellow accent)
Strategy:      B (neutral-on-theme) — cyan/pink icons on midnight backgrounds; occasional sun-yellow for single "hero" glyphs
Typography:    `title_color="#00f5ff"` or `#ffb703` on midnight
Example:       icon="mdi:play", icon_color="#00f5ff", bg_color="#1a1a2e"
```

Matches music-deck and streamer contexts. The full touchstrip is a canvas for a wide retrowave skyline image (generate it externally, not via MDI).

## Brutalist

High-contrast, minimal color, type-forward. All function, no ornament.

```
Palette:       #ffffff (white), #000000 (black), #ff0000 (single red accent)
Strategy:      A (theme-on-neutral) — black icons on white, occasional red for destructive or critical actions
Typography:    `title_color="#000000"`, larger-than-default `font_size` if possible
Example:       icon="mdi:play", icon_color="#000000", bg_color="#ffffff"
```

Good for developer decks, operational dashboards, anyone who wants the opposite of playful.

## Nordic

Cool, muted, gentle. The quiet palette that doesn't fatigue at arm's length.

```
Palette:       #2e3440 (polar night), #88c0d0 (frost blue), #a3be8c (aurora green), #d8dee9 (snow white), #bf616a (aurora red for warnings)
Strategy:      A (theme-on-neutral) — frost blue / aurora green icons on polar-night backgrounds
Typography:    `title_color="#d8dee9"` on dark
Example:       icon="mdi:play", icon_color="#88c0d0", bg_color="#2e3440"
```

Excellent default for dev/coding decks. Easy on the eyes, plays well with IDE themes the user is probably already in.

## Terminal

CRT green on black, monospace aesthetic. Dev-heavy.

```
Palette:       #00ff41 (terminal green), #0a0a0a (near-black), #00ff9c (secondary green), #ff6b35 (error orange)
Strategy:      B — green glyphs on near-black. No other strategies work here.
Typography:    `title_color="#00ff41"` on black. Ideally monospace but default font still reads.
Example:       icon="mdi:terminal", icon_color="#00ff41", bg_color="#0a0a0a"
```

Ship-of-theseus dev decks, hacker aesthetics, anyone running a `cmatrix` screensaver.

## Nature / Forest

Earth tones, organic. Calming.

```
Palette:       #2d6a4f (forest green), #d8f3dc (pale sage), #95d5b2 (mid green), #1b4332 (deep green), #ffb703 (sun yellow accent)
Strategy:      A — forest-green / deep-green icons on pale sage, occasional yellow for emphasis
Typography:    `title_color="#1b4332"` on pale, `#d8f3dc` on dark
Example:       icon="mdi:leaf", icon_color="#2d6a4f", bg_color="#d8f3dc"
```

Home-control decks, outdoor / hobby contexts, anyone who specifically asked for "calming."

## Minimal / Monochrome

No color. Grayscale gradations. Discipline.

```
Palette:       #ffffff (white), #e5e5e5 (light gray), #a3a3a3 (mid gray), #404040 (dark gray), #0a0a0a (near-black)
Strategy:      A — single-tone glyphs; vary via bg grays, not glyph color
Typography:    Subtle; `title_color="#0a0a0a"` on light, `#ffffff` on dark
Example:       icon="mdi:play", icon_color="#0a0a0a", bg_color="#e5e5e5"
```

Good when the user says "nothing fancy", "just functional", or doesn't want to think about theme. Falls back well.

## Corporate / Professional

Brand-blue-dominant, business-clean.

```
Palette:       #0077b6 (corporate blue), #023e8a (deep blue), #caf0f8 (pale blue), #ffffff (white), #ef233c (accent red for alerts)
Strategy:      A — blue icons on white canvases; reverse for hero buttons
Typography:    `title_color="#023e8a"`
Example:       icon="mdi:briefcase", icon_color="#0077b6", bg_color="#ffffff"
```

Dashboards for work contexts, client-facing decks, demo setups.

## Asking when unclear

If the user named a theme you don't recognize (e.g. "cottagecore", "cyberpunk 2077", a specific anime aesthetic), don't silently map to the closest archetype. Ask: "What's the feel — earthy pastels or harsh neons? Got a reference image?" Theme naming is personal, and the wrong approximation is annoying.

## Typography limits

`streamdeck_write_page`'s button schema exposes `font_size`, `title_color`, `title_alignment`, `show_title`. That's it — no font family selection in Phase 1 (Elgato's default sans-serif is used). Color and placement are your main levers. If a theme depends on a specific font (e.g. retrowave's chrome typography), that typography lives in the *icon PNGs*, not in titles.
