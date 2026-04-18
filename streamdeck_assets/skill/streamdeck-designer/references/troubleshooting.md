# Troubleshooting

Symptoms and fixes for common authoring-time failures. If the fix isn't here and the behavior is consistent, it's worth filing an issue — most of these came from real hardware sessions.

## "No Stream Deck profiles found"

`streamdeck_read_profiles` returned nothing or errors.

- **macOS**: profiles live under `~/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/` (preferred) or `ProfilesV2/`. If neither directory exists, the Elgato app hasn't been run on this machine. Ask the user to launch it once.
- **Windows**: `%APPDATA%\Elgato\StreamDeck\ProfilesV3\`. Same rule.
- **Empty directories**: the user has the app installed but no profiles created yet. Tell them to create a profile in the Elgato app, then retry.
- **Permissions**: on macOS Sonoma+, the Elgato app directory sometimes needs explicit Full Disk Access granted to the terminal Claude Code is running from. Symptoms: permission-denied errors reading the profile manifest. Fix: System Settings → Privacy & Security → Full Disk Access → add Terminal (or iTerm, etc.).

## "StreamDeckAppRunningError"

The Elgato desktop app is running, and `streamdeck_write_page` refuses to write.

**Why**: the Elgato app caches every profile in memory and rewrites the on-disk manifests from its snapshot when it quits. Any edit made while the app is running is overwritten the next time it closes.

**Fix**: pass `auto_quit_app=True` to `streamdeck_write_page`. The tool gracefully quits the app (AppleScript first, `killall` fallback), writes the manifest, and then `streamdeck_restart_app` relaunches it.

Don't ask the user to quit manually — always pass the flag.

## "Write succeeded but the deck doesn't show my changes"

`streamdeck_write_page` returned success, but on-device the page looks unchanged.

- Did you call `streamdeck_restart_app` after? The Elgato app reads manifests on launch; without a restart, the old cached layout persists.
- If you did restart and it's still wrong, read the page back with `streamdeck_read_page` and diff against your spec. If `read_page` shows your new buttons but the device doesn't, the Elgato app may be in a cache-weirdness state — quit it (`killall "Elgato Stream Deck"` or via Activity Monitor) and relaunch.
- Check that you wrote to the page the *device is currently showing*. A Plus XL might be on page 3 of a profile; writing to page 1 updates page 1, not what's on screen.

## "My encoder icon disappeared after restarting the Elgato app"

Known issue. The Elgato app strips `Encoder.Icon` and `Encoder.background` fields from the manifest unless the action's plugin declares `Controllers: ["Encoder"]`.

**Fix**: make sure the bundled streamdeck-mcp plugin is installed. `streamdeck_write_page` auto-installs it the first time an encoder button references it, but if you wrote an encoder button and the plugin install was skipped or failed, the fields get stripped on the next app quit.

- Verify: check `~/Library/Application Support/com.elgato.StreamDeck/Plugins/io.github.verygoodplugins.streamdeck-mcp.sdPlugin/` exists.
- Force-install: `streamdeck_install_mcp_plugin(force=True)`.
- After install, quit and relaunch the Elgato app. Now the stripping stops.

Background: this is PR #20's core finding. Don't spend cycles re-investigating — it's the plugin-declaration issue every time.

## "Encoder layout value/indicator slot is empty"

On-device, a dial using `$A1`/`$B1`/`$B2`/`$C1` shows title + icon but the value number or bar is blank.

**This is expected in Phase 1**, not a bug. Those slots are populated by `setFeedback` calls made by plugin JS, and the bundled plugin doesn't make those calls yet (memory: it's a no-op registration shell). Graduate to Phase 2 (live channel) for live values.

**Workaround in Phase 1**: use `$X1` or `$A0` (title + icon or title + full-canvas; no value slot to be empty). Or use the default `.dial` (no `encoder_layout` field) for the default composition with full-strip show-through.

## "Icon not found" / fuzzy-match suggestions

`streamdeck_create_icon(icon="mdi:cat-face")` returned something like:

```
{"error": "icon 'mdi:cat-face' not found", "suggestions": ["mdi:cat", "mdi:face", "mdi:emoticon-cool"]}
```

**Fix**: pick the closest suggestion and retry. MDI's naming is consistent (`kebab-case`, `category-subject`), but exact concept fits aren't always there. Don't keep guessing by typing — the suggestions are ranked by edit distance.

If nothing fits: fall back to `text="XY"` (short text icon) or generate the PNG externally and pass `icon_path` directly on `streamdeck_write_page`.

## "Icon + title text are doubled up"

On-device, a button shows both a baked-in text on the icon PNG *and* a title overlaid at the bottom.

**Cause**: you called `streamdeck_create_icon` with both `icon="mdi:..."` and `text="..."`, or you baked a title into a text-only icon and *also* set the button's `title` field.

**Fix**: pick one. For labeled icon buttons: `icon` param on `create_icon` + `title` field on `write_page`. For text-only buttons: `text` param on `create_icon` + no title on `write_page`.

## "Icon looks too small on the key"

- Check `icon_scale`. Default is `1.0` (edge-to-edge). If you set it lower, revisit. For keypad keys with a bottom title, `0.75`–`0.85` is a good range. For touchstrip segments, `1.0` matches Elgato's native sizing.

## "Button press does nothing on-device"

- Action type wrong: if you used `action_type: "next_page"` but the profile has no next page, it silently fails. Add a page or use a different action.
- Shell command fails silently: test the generated script directly (`~/StreamDeckScripts/<slug>.sh`) from a terminal. If it errors, check the `.env` file has values, not placeholders.
- Permissions: macOS sometimes blocks new shell scripts. Right-click the script file, Open With → Terminal, confirm the dialog once. After that, Stream Deck can invoke it.

## "Can't find credentials at button-press time"

Symptoms: the button runs but the integration fails silently (Hue scene doesn't change, OBS command doesn't route, etc.).

- Check `~/StreamDeckScripts/.env` exists and has real values (not `PLACEHOLDER_HUE_KEY`).
- Check each script sources the env file correctly:
  ```bash
  set -a; source "$HOME/StreamDeckScripts/.env"; set +a
  ```
- Run the script manually from a terminal: `bash ~/StreamDeckScripts/scene-chill.sh`. If it fails there, fix the env. If it succeeds there but fails from the deck, it's a Stream Deck process-environment issue — ensure the script is using absolute paths and the `set -a; source ...` pattern (which exports the vars into child processes).

## "I need a totally custom icon (not in MDI)"

Stream Deck keys render any 72×72 PNG. Generate your image externally (even a paint app works) and pass its path directly as `icon_path` on `streamdeck_write_page`. Skip `streamdeck_create_icon` for that button.

For dial icons that need to composite over a touchstrip background, the external PNG should be RGBA with transparency.

## "I want live / dynamic behavior"

That's Phase 2. In Phase 1:
- Don't try to fake live updates with a polling shell script that rewrites the manifest. Manifest rewrites require the Elgato app to be down, so polling at runtime doesn't work.
- Tell the user what Phase 2 will add (live-channel `setFeedback`, MCP-callback actions, progress bars that actually update) and whether a Phase-1-compatible workaround exists for their specific request.

## "Plugin install failed / permission denied"

`streamdeck_install_mcp_plugin` needs write access to the Elgato Plugins directory:
- macOS: `~/Library/Application Support/com.elgato.StreamDeck/Plugins/`
- Windows: `%APPDATA%\Elgato\StreamDeck\Plugins\`

If permission is denied:
- On macOS, check Full Disk Access (Privacy & Security) for Terminal/iTerm.
- The Elgato app shouldn't be running during plugin install — pass `auto_quit_app=True` to `streamdeck_write_page` or quit manually first.

## Still stuck

Open an issue at <https://github.com/verygoodplugins/streamdeck-mcp/issues> with:
- Hardware model + OS.
- The full error message / unexpected behavior.
- The `streamdeck_write_page` arguments you used (sanitize any secrets).
- Output of `streamdeck_read_profiles`.

Most bugs reproduce with those four pieces of info.
