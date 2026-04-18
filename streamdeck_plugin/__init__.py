"""Bundled streamdeck-mcp Stream Deck plugin.

Shipped as package data so the MCP can install it into the user's Elgato
Plugins directory on demand.
"""

import json
from importlib.resources import as_file, files

PLUGIN_UUID = "io.github.verygoodplugins.streamdeck-mcp"
PLUGIN_DIR_NAME = f"{PLUGIN_UUID}.sdPlugin"
ACTION_UUID = f"{PLUGIN_UUID}.dial"
DEFAULT_ACTION_UUID = ACTION_UUID

# Layout-declaring action variants. Each UUID maps to a plugin-manifest action
# whose `Encoder.layout` is statically set to the corresponding Elgato built-in.
# Callers select one by passing `encoder_layout="$A1"` etc. on an encoder button.
LAYOUT_ACTION_UUIDS: dict[str, str] = {
    "$X1": f"{PLUGIN_UUID}.dial.x1",
    "$A0": f"{PLUGIN_UUID}.dial.a0",
    "$A1": f"{PLUGIN_UUID}.dial.a1",
    "$B1": f"{PLUGIN_UUID}.dial.b1",
    "$B2": f"{PLUGIN_UUID}.dial.b2",
    "$C1": f"{PLUGIN_UUID}.dial.c1",
}
SUPPORTED_ENCODER_LAYOUTS: tuple[str, ...] = tuple(LAYOUT_ACTION_UUIDS.keys())

# Read the plugin version directly from the bundled manifest so there is a
# single source of truth — the manifest — rather than a duplicated constant.
try:
    _manifest_resource = files("streamdeck_plugin").joinpath(f"{PLUGIN_DIR_NAME}/manifest.json")
    with as_file(_manifest_resource) as _manifest_path:
        PLUGIN_VERSION: str = json.loads(_manifest_path.read_text(encoding="utf-8"))["Version"]
except Exception as _exc:  # pragma: no cover
    raise ImportError(
        f"streamdeck_plugin: failed to read version from bundled manifest.json: {_exc}"
    ) from _exc
