# Stream Deck SDK URL index — fallback for when Context7 is unavailable

Use this file when no `*context7*` tool is available in the session (e.g. the MCP was removed). Pick the closest page to the user's question, `WebFetch` it, and work from that. If Context7 *is* available, prefer it — these URLs are the same pages Context7 indexes, just one round-trip further away.

All URLs below were pulled from `https://docs.elgato.com/sitemap.xml`. The site marks every page `changefreq=weekly`, so content may drift from what this skill was built against.

## Introduction (4 pages) — start here for plugin basics

- `https://docs.elgato.com/streamdeck/sdk/introduction/getting-started` — SDK overview, terminology, the "what is a plugin" primer.
- `https://docs.elgato.com/streamdeck/sdk/introduction/plugin-environment` — directory layout of a `.sdPlugin`, files the Stream Deck app expects, manifest skeleton.
- `https://docs.elgato.com/streamdeck/sdk/introduction/your-first-changes` — walkthrough of editing an example plugin.
- `https://docs.elgato.com/streamdeck/sdk/introduction/distribution` — publishing to the Elgato Marketplace.

## Guides (13 pages) — concepts and recipes

- `https://docs.elgato.com/streamdeck/sdk/guides/actions` — action lifecycle, event handlers, UUID format, `SingletonAction` pattern.
- `https://docs.elgato.com/streamdeck/sdk/guides/app-monitoring` — `ApplicationsToMonitor` field, `applicationDidLaunch/DidTerminate` events.
- `https://docs.elgato.com/streamdeck/sdk/guides/deep-linking` — `streamdeck://plugins/message/...` URL grammar, active vs passive, OAuth2 redirect proxy.
- `https://docs.elgato.com/streamdeck/sdk/guides/devices` — device enumeration, device types (IDs 0–11), `deviceDidConnect/Disconnect` events.
- `https://docs.elgato.com/streamdeck/sdk/guides/dials` — dial / encoder behavior on Stream Deck +, rotate/press/touch semantics.
- `https://docs.elgato.com/streamdeck/sdk/guides/i18n` — localization file format, supported locales.
- `https://docs.elgato.com/streamdeck/sdk/guides/keys` — keypad action states, `setImage`, `setTitle`, multi-action context.
- `https://docs.elgato.com/streamdeck/sdk/guides/logging` — logger API, log levels, where logs are written on disk.
- `https://docs.elgato.com/streamdeck/sdk/guides/profiles` — installing and switching profiles from a plugin.
- `https://docs.elgato.com/streamdeck/sdk/guides/resources` — bundling static assets, i18n, and icons with a plugin.
- `https://docs.elgato.com/streamdeck/sdk/guides/settings` — per-action settings, global settings, `didReceiveSettings`, `setSettings`.
- `https://docs.elgato.com/streamdeck/sdk/guides/system` — system-level events (`systemDidWakeUp`, `didReceiveDeepLink`).
- `https://docs.elgato.com/streamdeck/sdk/guides/ui` — property inspector with `sdpi-components` web-component library.

## References (6 pages) — authoritative schema and API

- `https://docs.elgato.com/streamdeck/sdk/references/manifest` — full `manifest.json` schema (TypeScript type declaration + field-by-field reference). Schema URL: `https://schemas.elgato.com/streamdeck/plugins/manifest.json`.
- `https://docs.elgato.com/streamdeck/sdk/references/touch-strip-layout` — the six built-in layouts (`$X1`, `$A0`, `$A1`, `$B1`, `$B2`, `$C1`) plus the custom-layout JSON schema.
- `https://docs.elgato.com/streamdeck/sdk/references/websocket/plugin` — plugin-side WebSocket API: every inbound event (24) and outbound command (22) with TypeScript payloads.
- `https://docs.elgato.com/streamdeck/sdk/references/websocket/ui` — property-inspector WebSocket API (the UI side of the same protocol).
- `https://docs.elgato.com/streamdeck/sdk/references/websocket/changelog` — per-version changes to the WebSocket API.
- `https://docs.elgato.com/streamdeck/sdk/references/changelog` — SDK-wide changelog (v6.4 through v7.1 as of this writing).

## Releases & style guide (2 pages)

- `https://docs.elgato.com/streamdeck/sdk/releases/upgrading/v2` — migration guide from v1 to v2 SDK (breaking changes, codemod notes).
- `https://docs.elgato.com/streamdeck/sdk/style-guide/linting` — recommended ESLint / TypeScript config for plugin code.

## CLI (11 pages) — for plugin developers

Used when authoring / packaging a `.sdPlugin`, not for profile authoring.

- `https://docs.elgato.com/streamdeck/cli/intro` — installation and overview.
- `https://docs.elgato.com/streamdeck/cli/commands/config` — CLI configuration.
- `https://docs.elgato.com/streamdeck/cli/commands/create` — scaffold a new plugin.
- `https://docs.elgato.com/streamdeck/cli/commands/dev` — run a plugin in development mode.
- `https://docs.elgato.com/streamdeck/cli/commands/link` — install a dev plugin into the desktop app.
- `https://docs.elgato.com/streamdeck/cli/commands/unlink` — remove a dev plugin.
- `https://docs.elgato.com/streamdeck/cli/commands/list` — list installed plugins.
- `https://docs.elgato.com/streamdeck/cli/commands/pack` — package a plugin for distribution.
- `https://docs.elgato.com/streamdeck/cli/commands/validate` — validate a plugin's manifest + structure.
- `https://docs.elgato.com/streamdeck/cli/commands/restart` — restart the Stream Deck app.
- `https://docs.elgato.com/streamdeck/cli/commands/stop` — stop the Stream Deck app.
