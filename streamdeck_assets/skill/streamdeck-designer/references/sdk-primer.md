# Stream Deck SDK primer — hot-path facts

This is the thin slice of the Elgato Stream Deck SDK that agents use on nearly every authoring turn. Everything else lives at `docs.elgato.com/streamdeck/sdk/` (see `sdk-urls.md` for the full index) or Context7 under library `/websites/elgato_streamdeck_sdk`. Use this file first, then look deeper.

The facts here are verbatim from the SDK docs. Do not paraphrase them when emitting to the user — copy the grammar exactly.

## Deep linking

Deep links let a button (or any caller) send a message to a running Stream Deck plugin. The Elgato desktop app intercepts the URL scheme.

### URL grammar

```
streamdeck://plugins/message/<PLUGIN_UUID>[path][?query][#fragment]
```

- `streamdeck://plugins/message/` — fixed scheme prefix.
- `<PLUGIN_UUID>` — required. The target plugin's UUID (e.g. `com.elgato.wavelink`, `com.elgato.hello-world`).
- `[path]` — optional. An action path inside the plugin (e.g. `/hello`, `/auth`).
- `[?query]` — optional. Query-string params for the plugin. Reserved key: `streamdeck=hidden` makes the link *passive* (see below).
- `[#fragment]` — optional. Fragment identifier (e.g. `#waving`).

Full example: `streamdeck://plugins/message/com.elgato.hello-world/hello?name=Elgato#waving`

### Active vs passive

| | Active | Passive |
|---|---|---|
| Default behavior | Brings the Stream Deck window to the foreground | Stays in the background |
| Configuration | Default | Add `?streamdeck=hidden` |
| Minimum Stream Deck version | 6.5 | 7.0 |
| Typical use | OAuth flows, any interaction needing focus | Background IPC, port exchange, setup |

### Limits and constraints

- Deep-link messages must stay under **2,000 characters**. For larger payloads use a WebSocket connection.
- Deep-links are **local-only** — you cannot trigger them from remote sources.
- Some OAuth providers don't accept custom URL schemes. In that case use the redirect proxy: `https://oauth2-redirect.elgato.com/streamdeck/plugins/message/<PLUGIN_UUID>` — the proxy forwards the callback as a `streamdeck://...` deep link.

### Wiring into a deck button (Phase 1)

Because this skill authors static profiles (not plugins), a deep-link button is a shell action that invokes `open` on macOS or `start` on Windows:

```bash
#!/bin/bash
open 'streamdeck://plugins/message/com.elgato.wavelink/settings'
```

Pass that through `streamdeck_create_action(name="wavelink-settings", command="...")` the same way as any other shell action. The user's Stream Deck app receives the URL and routes it to the named plugin.

**Go deeper** — Context7 query: `"deep linking"` on `/websites/elgato_streamdeck_sdk`. Canonical URL: `https://docs.elgato.com/streamdeck/sdk/guides/deep-linking`.

## manifest.json cheat sheet

`manifest.json` describes a Stream Deck plugin to the Elgato desktop app. Phase 1 of this skill does **not** author plugins — it authors user profiles (a separate artifact). But agents often get manifest questions, and several manifest concepts leak into the profile format (DeviceType IDs, controller types, encoder layout tokens). Read this before speculating.

### Top-level sections (verified from the Manifest TypeScript type)

| Key | Purpose |
|---|---|
| `UUID` | Unique plugin ID (e.g. `com.elgato.hello-world`). Also used in deep-link URLs. |
| `Name`, `Version`, `Author`, `Description`, `Icon` | Plugin metadata. |
| `Actions[]` | The actions the plugin exposes (Keypad/Encoder). Each has its own UUID, States, Controllers, PropertyInspectorPath. |
| `CodePath` (+ `CodePathMac`, `CodePathWin`) | Entry-point script the desktop app launches. |
| `SDKVersion` | `2` or `3`. |
| `Software.MinimumVersion` | Minimum Stream Deck app version: one of `"6.4"`…`"7.1"`. |
| `OS[]` | Platform list with `Platform` (`"mac"` \| `"windows"`) and `MinimumVersion`. |
| `Nodejs` | `{ Version: "20" \| "24", Debug?, GenerateProfilerOutput? }` — required when the plugin is Node-based. |
| `Profiles[]` | Pre-defined profiles the plugin installs (each with `Name`, `DeviceType` 0–11, `AutoInstall`, `Readonly`, `DontAutoSwitchWhenInstalled`). |
| `ApplicationsToMonitor` | `{ mac?: string[], windows?: string[] }` — see pitfall below. |
| `Category`, `CategoryIcon` | Group the plugin in the store UI. |
| `PropertyInspectorPath` | Plugin-level property inspector file (fallback if action doesn't define one). |
| `URL`, `SupportURL` | Marketing / help URLs. |
| `DefaultWindowSize` | Default property-inspector window dimensions. |

Schema URL for JSON-Schema validation / IntelliSense: `https://schemas.elgato.com/streamdeck/plugins/manifest.json`. Put it in `$schema` at the top of `manifest.json`.

### Pitfalls — don't fabricate these

- **The JSON key is `ApplicationsToMonitor`, not `ApplicationMonitoring`.** The docs page is *titled* "Application Monitoring," which tricks both users and agents. The actual manifest field is `ApplicationsToMonitor` with `mac` and `windows` arrays of bundle IDs / executable names. It's a **plugin-side** feature (the plugin's code decides what to do when a monitored app is active/inactive) and has no effect on a static profile authored by streamdeck-mcp.
- **Encoder layout tokens**: `$X1`, `$A0`, `$A1`, `$B1`, `$B2`, `$C1` are the six built-in touchstrip layouts. The `Encoder.layout` field also accepts a custom `${string}.json` path. See `dials-and-touchstrip.md` for which ones render in Phase 1.
- **`Controllers`** on an action is a tuple `["Encoder" | "Keypad", ("Encoder" | "Keypad")?]` — the second slot is optional, and an action can be dual-role (keypad + encoder) by listing both.
- **`Software.MinimumVersion` is a literal union**, not a free-form string. Only the enumerated versions `"6.4"` through `"7.1"` are valid.

**Go deeper** — Context7 query: `"manifest.json schema"` or a specific field name on `/websites/elgato_streamdeck_sdk`. Canonical URL: `https://docs.elgato.com/streamdeck/sdk/references/manifest`.

## WebSocket plugin event glossary

Every plugin event below is a JSON-RPC message the Stream Deck app pushes to the plugin's WebSocket. Phase 1 decks do **not** listen for these (they fire shell commands, not handlers), but agents get asked about them constantly. Names are case-exact. Query Context7 with the event name for the full payload.

### Input events (user action)

| Event | Controller | Purpose |
|---|---|---|
| `keyDown` | Keypad | User pressed a keypad button. Payload has `coordinates`, `settings`, `isInMultiAction`, `state`. |
| `keyUp` | Keypad | User released a keypad button. |
| `dialDown` | Encoder | User pressed a dial. Distinct from `dialRotate`. |
| `dialUp` | Encoder | User released a dial. |
| `dialRotate` | Encoder | User rotated a dial. Payload includes `ticks` (number) and `pressed` (boolean: true if dial was held down *while* rotating). |
| `touchTap` | Encoder (touchstrip) | User tapped the touchscreen. Payload has `tapPos: [x, y]` and `hold: boolean`. |

**Pitfall — dial events are separate.** `dialRotate` does NOT also fire on press. Press is `dialDown` / `dialUp`. If someone tells you "DialRotate fires on press," they're wrong — correct them with the Elgato docs as evidence.

### Lifecycle events

| Event | Purpose |
|---|---|
| `willAppear` | Action instance became visible on the deck (page switch, startup). |
| `willDisappear` | Action instance left the visible area. |
| `titleParametersDidChange` | User edited the button's title in the app. |
| `didReceiveSettings` | Settings for this action instance were updated. |
| `didReceiveGlobalSettings` | Plugin-wide settings were updated. |
| `didReceiveDeepLink` | The plugin received a `streamdeck://plugins/message/...` URL (passed in the payload). |
| `propertyInspectorDidAppear` / `propertyInspectorDidDisappear` | Property inspector UI lifecycle. |
| `systemDidWakeUp` | Host OS woke from sleep. |
| `applicationDidLaunch` / `applicationDidTerminate` | Monitored app state changed (requires `ApplicationsToMonitor`). |
| `deviceDidConnect` / `deviceDidDisconnect` | Stream Deck hardware attach/detach. |

Plugin → app **commands** (setImage, setTitle, setFeedback, setState, sendToPropertyInspector, switchToProfile, openUrl, logMessage, setSettings, etc.) live in the same reference. They are out of scope for Phase 1 (which writes the manifest, not the running plugin), but agents can cite them for user education.

**Go deeper** — Context7 queries: `"<eventName> event payload"` or `"plugin WebSocket commands"` on `/websites/elgato_streamdeck_sdk`. Canonical URL: `https://docs.elgato.com/streamdeck/sdk/references/websocket/plugin`. UI/property-inspector side: `https://docs.elgato.com/streamdeck/sdk/references/websocket/ui`.

## Stream Deck CLI

The `streamdeck` CLI is for plugin developers, not profile authors. Listed here for completeness so agents can answer "what does `streamdeck pack` do?" without guessing.

| Command | Purpose |
|---|---|
| `streamdeck config` | Inspect/set CLI configuration. |
| `streamdeck create` | Scaffold a new plugin project. |
| `streamdeck dev` | Run a plugin in development mode (hot-reload, logs streamed). |
| `streamdeck link` | Install a development plugin into the local Stream Deck app. |
| `streamdeck unlink` | Remove a development plugin. |
| `streamdeck list` | List installed plugins. |
| `streamdeck pack` | Package a plugin into a `.streamDeckPlugin` bundle for distribution. |
| `streamdeck validate` | Validate a plugin's manifest and structure against the SDK schema. |
| `streamdeck restart` | Restart the Stream Deck app. |
| `streamdeck stop` | Stop the Stream Deck app. |

None of these are invoked by this skill; `streamdeck_restart_app` (an MCP tool) plays the same role as `streamdeck restart` for the authoring workflow.

**Go deeper** — canonical URL: `https://docs.elgato.com/streamdeck/cli/intro` and per-command pages under `/streamdeck/cli/commands/`. Context7 also has these under library `/websites/elgato_streamdeck_cli` (645 snippets).

## Before you emit an SDK fact

If you catch yourself thinking:
- "I think I know the deep-link URL format" → verify against this file or Context7 first.
- "This event name sounds right (`DialRotate`, `onWillAppear`, …)" → verify.
- "The manifest probably accepts X" → verify.
- "`setImage` takes a base64 string, right?" → verify.

All of these are the same rule: **do not emit SDK facts you have not just read.** Look it up, then emit.
