"""Bundled streamdeck-mcp Stream Deck plugin.

Shipped as package data so the MCP can install it into the user's Elgato
Plugins directory on demand.
"""

import json
from importlib.resources import as_file, files

PLUGIN_UUID = "io.github.verygoodplugins.streamdeck-mcp"
PLUGIN_DIR_NAME = f"{PLUGIN_UUID}.sdPlugin"
ACTION_UUID = f"{PLUGIN_UUID}.dial"

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
