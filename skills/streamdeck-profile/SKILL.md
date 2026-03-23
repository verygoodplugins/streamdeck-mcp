# Stream Deck Profile Writer

Use this skill when you need to configure Elgato Stream Deck desktop profiles without taking USB control of the hardware.

## Default Workflow

1. Call `streamdeck_read_profiles` to discover the active profiles root and page `directory_id` values.
2. Call `streamdeck_read_page` before editing an existing page so you can inspect the current native action objects.
3. Use `streamdeck_create_icon` when you need a quick text icon.
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
