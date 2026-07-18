#!/usr/bin/env python3
"""
Helpers for reading and writing Elgato Stream Deck profile manifests.

The Elgato desktop app stores device profiles in ProfilesV3 on newer installs
and ProfilesV2 on older installs. V3 uses page UUIDs as directory names; V2
uses opaque directory identifiers, so V2 page updates work best when callers
target pages by directory ID or page index.
"""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
import shlex
import shutil
import string
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


DEFAULT_BG_COLOR = "#000000"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_FONT_SIZE = 12
DEFAULT_TITLE_ALIGNMENT = "bottom"
DEFAULT_ICON_SIZE = (72, 72)
TOUCHSTRIP_ICON_SIZE = (200, 100)
ICON_SHAPES = {"button": DEFAULT_ICON_SIZE, "touchstrip": TOUCHSTRIP_ICON_SIZE}

KEYPAD = "Keypad"
ENCODER = "Encoder"

CONTROLLER_ALIASES: dict[str, str] = {
    "keypad": KEYPAD,
    "key": KEYPAD,
    "button": KEYPAD,
    "encoder": ENCODER,
    "dial": ENCODER,
}

DEFAULT_PAGE_MANIFEST = {
    "Controllers": [
        {
            "Actions": None,
            "Type": KEYPAD,
        }
    ],
    "Icon": "",
    "Name": "",
}

MODEL_LAYOUTS: dict[str, dict[str, tuple[int, int]]] = {
    # Stream Deck Original (15 keys)
    "20GBA9901": {KEYPAD: (5, 3)},
    # Stream Deck MK.2 (15 keys)
    "20GAA9901": {KEYPAD: (5, 3)},
    # Stream Deck XL (32 keys)
    "20GAT9902": {KEYPAD: (8, 4)},
    # Stream Deck XL rev2 (32 keys)
    "20GBA9902": {KEYPAD: (8, 4)},
    # Stream Deck + XL (36 keys, 6 dials with 1200x100 touchstrip)
    "20GBX9901": {KEYPAD: (9, 4), ENCODER: (6, 1)},
    # Stream Deck Mini (6 keys)
    "20GAI9501": {KEYPAD: (3, 2)},
    # Stream Deck + (8 keys + 4 dials + 800x100 touchstrip, released 2022).
    # Profile manifests for this model carry a full Encoder controller with
    # 4 dial actions at 0,0…3,0 plus a touchstrip Background image, which
    # is what the encoder layout below records.
    "20GBD9901": {KEYPAD: (4, 2), ENCODER: (4, 1)},
    # Emulator used by the Elgato desktop app ("UI" in older builds, "AI" in recent)
    "UI Stream Deck": {KEYPAD: (4, 2)},
    "AI Stream Deck": {KEYPAD: (4, 2)},
}

# Human-readable names for the model IDs the Elgato desktop app writes to
# profile manifests. Surfaced in streamdeck_read_profiles so LLMs don't have to
# cross-reference product IDs against docs (and mis-translate them under the
# pressure of a complex authoring session). Source: Elgato app profile
# manifests observed in the wild; kept in sync with MODEL_LAYOUTS above.
MODEL_NAMES: dict[str, str] = {
    "20GBA9901": "Stream Deck Original",
    "20GAA9901": "Stream Deck MK.2",
    "20GAT9902": "Stream Deck XL",
    "20GBA9902": "Stream Deck XL rev2",
    "20GBX9901": "Stream Deck + XL",
    "20GAI9501": "Stream Deck Mini",
    "20GBD9901": "Stream Deck +",
    "UI Stream Deck": "UI Stream Deck (emulator)",
    "AI Stream Deck": "AI Stream Deck (virtual deck / Elgato app companion)",
}

# The Elgato Stream Deck desktop app caches every profile in memory and rewrites the
# on-disk manifests when it quits, so any edit made while it is running gets clobbered
# the next time the user closes or restarts the app.
STREAM_DECK_APP_PROCESS_NAMES = ("Stream Deck", "Elgato Stream Deck")
DEFAULT_STREAM_DECK_APP_PATH = Path("/Applications/Elgato Stream Deck.app")
STREAM_DECK_APP_PATH_ENV = "STREAMDECK_APP_PATH"

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
POSITION_PATTERN = re.compile(r"^\d+,\d+$")
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")

# --- Property Inspector settings-schema inference ---------------------------
# Third-party plugins declare the settings fields an action expects in their
# Property Inspector (PI) HTML/JS, not in manifest.json. streamdeck_read_plugins
# best-effort parses those so callers know which Settings keys an action wants.
# Three real-world PI styles are handled (observed across OBS-adjacent, Toggl,
# Voicemod, WiiM, and sdpi-components decks):
#   A. sdpi-components web components — `<sdpi-textfield setting="key">`
#      (high confidence: the setting key is a literal HTML attribute).
#   B. classic sdpi.css + hand-written JS — keys live in `payload.settings.<key>`
#      reads and `setSettings({ ... })` payload literals, NOT the HTML id/name
#      (Toggl's ids deliberately differ from its setting keys).
#   C. fully custom HTML + raw WebSocket — keys referenced as `settings.<key>`.
# HTML id/name attributes are intentionally NOT trusted as keys.
PI_MAX_BYTES = 512 * 1024  # skip pathological/minified bundles (e.g. sdpi-components.js)
PI_MAX_SCRIPT_FILES = 6  # cap linked JS files scanned per PI to bound work
# Library scripts that never declare an action's own settings keys.
PI_LIBRARY_SCRIPTS = {
    "sdpi-components.js",
    "sdtools.common.js",
    "common.js",
    "common_pi.js",
    "property-inspector.js",
    "propertyinspector.js",
    "jquery.js",
    "jquery.min.js",
    "utils.js",
}
# JS identifiers that follow `settings.` but are never real setting keys.
PI_JS_NOISE_KEYS = {
    "hasOwnProperty",
    "length",
    "forEach",
    "map",
    "filter",
    "reduce",
    "keys",
    "values",
    "entries",
    "constructor",
    "prototype",
    "toString",
    "call",
    "apply",
    "bind",
    "then",
    "catch",
    "settings",
    "payload",
    "undefined",
    "push",
    "pop",
    "slice",
}
SDPI_TAG_PATTERN = re.compile(r"<sdpi-([a-zA-Z0-9-]+)\b([^>]*)>", re.IGNORECASE | re.DOTALL)
HTML_ATTR_PATTERN = re.compile(r'([a-zA-Z_][\w:-]*)\s*=\s*"([^"]*)"')
DATA_SETTING_PATTERN = re.compile(r'\bdata-setting\s*=\s*"([^"]+)"')
SCRIPT_SRC_PATTERN = re.compile(r'<script\b[^>]*\bsrc\s*=\s*"([^"]+)"[^>]*>', re.IGNORECASE)
INLINE_SCRIPT_PATTERN = re.compile(
    r"<script\b(?![^>]*\bsrc\b)[^>]*>(.*?)</script[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
JS_SETTINGS_DOT_PATTERN = re.compile(r"(?:payload\??\.)?settings\??\.([A-Za-z_$][\w$]*)")
JS_SETTINGS_INDEX_PATTERN = re.compile(r"settings\??\[\s*[\"']([^\"']+)[\"']\s*\]")

FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSText.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


class ProfileManagerError(Exception):
    """Base exception for profile manager operations."""


class ProfileNotFoundError(ProfileManagerError):
    """Raised when a requested profile cannot be found."""


class PageNotFoundError(ProfileManagerError):
    """Raised when a requested profile page cannot be found."""


class ProfileValidationError(ProfileManagerError):
    """Raised when inputs for profile operations are invalid."""


class StreamDeckAppRunningError(ProfileManagerError):
    """Raised when a write is attempted while the Elgato desktop app is running.

    The app rewrites every profile manifest from its in-memory snapshot on quit, so
    writes made while it is running are silently discarded. Callers must quit the
    app first (pass `auto_quit_app=True` to `write_page`) and then call
    `restart_app` once their edits are complete to see the changes.
    """


@dataclass
class PageRef:
    """Resolved page directory metadata."""

    page_index: int
    directory_id: str
    page_uuid: str | None
    manifest_path: Path
    version: str
    mapping: str
    is_default: bool
    is_current: bool
    name: str
    button_count: int
    icon_count: int

    @property
    def directory_path(self) -> Path:
        return self.manifest_path.parent

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "directory_id": self.directory_id,
            "page_uuid": self.page_uuid,
            "version": self.version,
            "mapping": self.mapping,
            "is_default": self.is_default,
            "is_current": self.is_current,
            "name": self.name,
            "button_count": self.button_count,
            "icon_count": self.icon_count,
            "manifest_path": str(self.manifest_path),
        }


def _normalize_uuid(value: str) -> str:
    return value.strip().lower()


def _looks_like_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match(value))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileManagerError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileManagerError(f"Invalid JSON in {path}: {exc}") from exc


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def _candidate_profiles_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library/Application Support/com.elgato.StreamDeck"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise ProfileManagerError("APPDATA is not set; cannot locate Stream Deck profiles.")
        base = Path(appdata) / "Elgato/StreamDeck"
    else:
        base = home / ".local/share/Elgato/StreamDeck"

    return [base / "ProfilesV3", base / "ProfilesV2"]


def get_profiles_dir(version: str = "auto") -> Path:
    """Resolve the active Stream Deck profiles directory."""

    candidates = _candidate_profiles_dirs()
    if version == "auto":
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    normalized = version.lower().removeprefix("profiles")
    if normalized in {"3", "v3"}:
        return candidates[0]
    if normalized in {"2", "v2"}:
        return candidates[1]

    raise ProfileValidationError(
        f"Unsupported profiles version '{version}'. Use 'auto', '2', or '3'."
    )


def _find_controller(page_manifest: dict[str, Any], controller_type: str) -> dict[str, Any] | None:
    for controller in page_manifest.get("Controllers") or []:
        if controller.get("Type") == controller_type:
            return controller
    return None


def _ensure_controller(page_manifest: dict[str, Any], controller_type: str) -> dict[str, Any]:
    controllers = page_manifest.setdefault("Controllers", [])
    for controller in controllers:
        if controller.get("Type") == controller_type:
            return controller
    new_controller: dict[str, Any] = {"Type": controller_type, "Actions": None}
    controllers.append(new_controller)
    return new_controller


def _controller_actions(
    page_manifest: dict[str, Any], controller_type: str = KEYPAD
) -> dict[str, Any]:
    controller = _find_controller(page_manifest, controller_type)
    if not controller:
        return {}
    return controller.get("Actions") or {}


def _normalize_controller(value: str | None) -> str:
    if not value:
        return KEYPAD
    canonical = CONTROLLER_ALIASES.get(value.lower())
    if canonical is None:
        raise ProfileValidationError(
            f"Unknown controller '{value}'. Use one of: {sorted(set(CONTROLLER_ALIASES))}"
        )
    return canonical


def _total_action_count(page_manifest: dict[str, Any]) -> int:
    return sum(
        len(controller.get("Actions") or {})
        for controller in page_manifest.get("Controllers") or []
    )


def _slugify(value: str) -> str:
    slug = SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    return slug or "streamdeck-action"


def _quote_open_path(path: Path) -> str:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _ensure_hex_color(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not HEX_COLOR_PATTERN.match(normalized):
        raise ProfileValidationError(
            f"{field_name} must be a hex color like '#112233', got '{value}'."
        )
    return normalized.lower()


def _resolve_font(size: int) -> Any:
    for font_path in FONT_PATHS:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _count_icons(page_dir: Path) -> int:
    images_dir = page_dir / "Images"
    if not images_dir.exists():
        return 0
    return len([path for path in images_dir.iterdir() if path.is_file()])


def _resolve_app_path() -> Path:
    override = os.environ.get(STREAM_DECK_APP_PATH_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_STREAM_DECK_APP_PATH


def get_plugins_dir() -> Path:
    """Return the Elgato Stream Deck plugins directory for the current OS."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library/Application Support/com.elgato.StreamDeck/Plugins"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise ProfileManagerError("APPDATA is not set; cannot locate Stream Deck plugins.")
        return Path(appdata) / "Elgato/StreamDeck/Plugins"
    return home / ".local/share/Elgato/StreamDeck/Plugins"


def ensure_mcp_plugin_installed(*, force: bool = False) -> dict[str, Any]:
    """Install the bundled streamdeck-mcp plugin into the Elgato Plugins directory.

    The plugin declares an encoder-capable action so that the Stream Deck app
    accepts per-instance ``Encoder.Icon`` and ``Encoder.background`` writes made
    by the profile writer. Without it, those fields are stripped on quit for any
    action whose plugin does not declare encoder support.

    Idempotent: returns ``installed=False`` when the plugin directory already
    exists at the current bundled version, unless ``force=True`` is passed.
    Automatically upgrades when the installed manifest version is older than the
    bundled version so that new action UUIDs (e.g. layout variants) are available.
    """
    from importlib.resources import as_file, files

    from streamdeck_plugin import PLUGIN_DIR_NAME, PLUGIN_VERSION

    plugins_dir = get_plugins_dir()
    dst = plugins_dir / PLUGIN_DIR_NAME

    if dst.exists() and not force:
        installed_version: str | None = None
        try:
            installed_manifest = dst / "manifest.json"
            installed_version = json.loads(installed_manifest.read_text(encoding="utf-8")).get(
                "Version"
            )
        except Exception:
            pass

        if installed_version == PLUGIN_VERSION:
            return {"installed": False, "reason": "already installed", "path": str(dst)}
        # Installed version is missing or outdated — fall through to reinstall.

    plugins_dir.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)

    src_resource = files("streamdeck_plugin").joinpath(PLUGIN_DIR_NAME)
    with as_file(src_resource) as src_path:
        shutil.copytree(src_path, dst)

    return {"installed": True, "path": str(dst)}


def is_stream_deck_app_running() -> bool:
    """Return True if the Elgato Stream Deck desktop app is currently running."""

    if sys.platform != "darwin":
        return False

    for name in STREAM_DECK_APP_PROCESS_NAMES:
        result = subprocess.run(
            ["pgrep", "-x", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    return False


def stop_stream_deck_app(*, graceful_timeout: float = 3.0) -> dict[str, Any]:
    """Quit the Elgato Stream Deck desktop app.

    Tries an AppleScript quit first so the app can persist any unrelated state, then
    falls back to `killall` if it does not exit in time. Returns a small report about
    which path was taken.
    """

    if sys.platform != "darwin":
        return {"stopped": False, "graceful": [], "forced": [], "reason": "non-darwin platform"}

    if not is_stream_deck_app_running():
        return {"stopped": False, "graceful": [], "forced": [], "reason": "not running"}

    graceful: list[str] = []
    for name in STREAM_DECK_APP_PROCESS_NAMES:
        result = subprocess.run(
            ["osascript", "-e", f'tell application "{name}" to quit'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            graceful.append(name)

    deadline = time.monotonic() + graceful_timeout
    while time.monotonic() < deadline and is_stream_deck_app_running():
        time.sleep(0.2)

    forced: list[str] = []
    if is_stream_deck_app_running():
        for name in STREAM_DECK_APP_PROCESS_NAMES:
            result = subprocess.run(
                ["killall", name],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                forced.append(name)

    return {
        "stopped": not is_stream_deck_app_running(),
        "graceful": graceful,
        "forced": forced,
    }


class ProfileManager:
    """Read and write Elgato Stream Deck profiles."""

    def __init__(
        self,
        profiles_dir: Path | None = None,
        *,
        profiles_version: str = "auto",
        scripts_dir: Path | None = None,
        generated_icons_dir: Path | None = None,
    ) -> None:
        self.profiles_dir = (
            Path(profiles_dir) if profiles_dir else get_profiles_dir(profiles_version)
        )
        self.scripts_dir = (
            Path(scripts_dir).expanduser() if scripts_dir else (Path.home() / "StreamDeckScripts")
        )
        self.generated_icons_dir = (
            Path(generated_icons_dir).expanduser()
            if generated_icons_dir
            else (Path.home() / ".streamdeck-mcp" / "generated-icons")
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        """List profiles in the selected Elgato profiles directory."""

        if not self.profiles_dir.exists():
            return []

        profiles: list[dict[str, Any]] = []
        for profile_dir in sorted(self.profiles_dir.glob("*.sdProfile")):
            manifest = _load_json(profile_dir / "manifest.json")
            page_refs = self._page_refs(profile_dir, manifest)
            device = dict(manifest.get("Device") or {})
            model_id = device.get("Model")
            if model_id and "ModelName" not in device:
                device["ModelName"] = MODEL_NAMES.get(
                    model_id, f"Unknown Stream Deck model ({model_id})"
                )
            profiles.append(
                {
                    "profile_id": profile_dir.stem,
                    "name": manifest.get("Name", profile_dir.stem),
                    "version": manifest.get("Version", "unknown"),
                    "profiles_dir": str(self.profiles_dir),
                    "profiles_root": self.profiles_dir.name,
                    "profile_path": str(profile_dir),
                    "device": device,
                    "current_page_uuid": manifest.get("Pages", {}).get("Current"),
                    "default_page_uuid": manifest.get("Pages", {}).get("Default"),
                    "page_count": len(page_refs),
                    "pages": [page_ref.to_dict() for page_ref in page_refs],
                }
            )
        return profiles

    def list_plugins(
        self,
        *,
        plugin_id: str | None = None,
        include_raw_manifest: bool = False,
        include_settings_schema: bool = True,
    ) -> dict[str, Any]:
        """List installed Stream Deck plugins and their declared actions.

        The official Elgato app may install protected/binary manifests for some
        first-party plugins (OBS, Home Assistant, Hue, Spotify, Zoom, …). Those
        entries are reported with diagnostics instead of aborting the whole
        catalog, so agents can still use readable plugins.

        When ``include_settings_schema`` is true (the default), each readable
        action is enriched with ``state_count`` plus a best-effort
        ``settings_fields`` list inferred from the action's Property Inspector
        (see the PI-parsing note above). This tells callers which ``Settings``
        keys a third-party action expects so they can author it with
        ``streamdeck_write_page``. Fields are heuristic: absence of a field does
        not prove it is unused, and a listed field is not guaranteed required.
        """

        plugins_dir = get_plugins_dir()
        plugins: list[dict[str, Any]] = []

        if plugins_dir.exists():
            for plugin_dir in sorted(plugins_dir.glob("*.sdPlugin"), key=lambda p: p.name.lower()):
                plugin = self._read_plugin_manifest(
                    plugin_dir,
                    include_raw_manifest=include_raw_manifest,
                    include_settings_schema=include_settings_schema,
                )
                if self._matches_plugin_filter(plugin, plugin_id):
                    plugins.append(plugin)

        return {
            "plugins_dir": str(plugins_dir),
            "plugin_count": len(plugins),
            "plugins": plugins,
        }

    def _read_plugin_manifest(
        self,
        plugin_dir: Path,
        *,
        include_raw_manifest: bool,
        include_settings_schema: bool = True,
    ) -> dict[str, Any]:
        folder_id = self._plugin_folder_id(plugin_dir)
        manifest_path = plugin_dir / "manifest.json"
        base: dict[str, Any] = {
            "folder_name": plugin_dir.name,
            "folder_id": folder_id,
            "plugin_uuid": folder_id,
            "manifest_uuid": None,
            "name": None,
            "version": None,
            "author": None,
            "category": None,
            "sdk_version": None,
            "description": None,
            "url": None,
            "manifest_path": str(manifest_path),
            "parse_status": "ok",
            "actions": [],
        }

        try:
            raw = manifest_path.read_bytes()
        except OSError as exc:
            base["parse_status"] = "unreadable"
            base["error"] = f"Could not read manifest: {exc}"
            return base

        if raw.startswith(b"ELGATO"):
            base["parse_status"] = "binary_or_protected"
            base["error"] = "ELGATO protected/binary manifest; action metadata unavailable."
            return base

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            base["parse_status"] = "binary_or_protected"
            base["error"] = "Manifest is binary or protected; action metadata unavailable."
            return base

        try:
            manifest = json.loads(text)
        except json.JSONDecodeError as exc:
            base["parse_status"] = "invalid_json"
            base["error"] = f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}."
            return base

        if not isinstance(manifest, dict):
            base["parse_status"] = "invalid_json"
            base["error"] = "Invalid JSON: manifest root must be an object."
            return base

        manifest_uuid = self._string_or_none(manifest.get("UUID"))
        manifest_actions = manifest.get("Actions")
        actions = manifest_actions if isinstance(manifest_actions, list) else []
        default_pi_path = self._string_or_none(manifest.get("PropertyInspectorPath"))
        simplified = [
            self._simplify_plugin_action(action) for action in actions if isinstance(action, dict)
        ]
        if include_settings_schema:
            for action in simplified:
                self._enrich_action_settings_schema(action, plugin_dir, default_pi_path)
        base.update(
            {
                "plugin_uuid": manifest_uuid or folder_id,
                "manifest_uuid": manifest_uuid,
                "name": self._string_or_none(manifest.get("Name")),
                "version": self._string_or_none(manifest.get("Version")),
                "author": self._string_or_none(manifest.get("Author")),
                "category": self._string_or_none(manifest.get("Category")),
                "sdk_version": manifest.get("SDKVersion"),
                "description": self._string_or_none(manifest.get("Description")),
                "url": self._string_or_none(manifest.get("URL")),
                "property_inspector_path": default_pi_path,
                "actions": simplified,
            }
        )
        if include_raw_manifest:
            base["raw_manifest"] = manifest
        return base

    @staticmethod
    def _plugin_folder_id(plugin_dir: Path) -> str:
        name = plugin_dir.name
        if name.lower().endswith(".sdplugin"):
            return name[: -len(".sdPlugin")]
        return plugin_dir.stem

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _list_or_empty(value: Any) -> list[Any]:
        if isinstance(value, list):
            return copy.deepcopy(value)
        return []

    @classmethod
    def _simplify_plugin_action(cls, action: dict[str, Any]) -> dict[str, Any]:
        return {
            "uuid": cls._string_or_none(action.get("UUID")),
            "name": cls._string_or_none(action.get("Name")),
            "icon": cls._string_or_none(action.get("Icon")),
            "tooltip": cls._string_or_none(action.get("Tooltip")),
            "controllers": cls._list_or_empty(action.get("Controllers")),
            "property_inspector_path": cls._string_or_none(action.get("PropertyInspectorPath")),
            "states": cls._list_or_empty(action.get("States")),
            "encoder": copy.deepcopy(action.get("Encoder"))
            if isinstance(action.get("Encoder"), dict)
            else None,
            "supported_in_multi_actions": action.get("SupportedInMultiActions"),
            "category": cls._string_or_none(action.get("Category")),
            "category_icon": cls._string_or_none(action.get("CategoryIcon")),
        }

    @classmethod
    def _enrich_action_settings_schema(
        cls,
        action: dict[str, Any],
        plugin_dir: Path,
        default_pi_path: str | None,
    ) -> None:
        """Add ``state_count`` and best-effort ``settings_fields`` to a simplified
        action, parsed from its Property Inspector. Mutates ``action`` in place.

        ``settings_fields_source`` records how the inference went so callers know
        how much to trust the list:
        - ``property_inspector``: PI file read and at least one field inferred.
        - ``property_inspector_empty``: PI read but no fields could be inferred.
        - ``property_inspector_missing``: PI declared but the file is absent.
        - ``property_inspector_unreadable``: PI present but could not be read.
        - ``none``: the action declares no Property Inspector.
        """

        states = action.get("states")
        action["state_count"] = len(states) if isinstance(states, list) else 0

        pi_rel = action.get("property_inspector_path") or default_pi_path
        if not pi_rel:
            action["settings_fields"] = []
            action["settings_fields_source"] = "none"
            return

        pi_path = cls._resolve_plugin_relative_path(plugin_dir, pi_rel)
        if pi_path is None or not pi_path.is_file():
            action["settings_fields"] = []
            action["settings_fields_source"] = "property_inspector_missing"
            return

        try:
            fields, source = cls._infer_settings_fields(pi_path, plugin_dir)
        except OSError:
            action["settings_fields"] = []
            action["settings_fields_source"] = "property_inspector_unreadable"
            return

        action["settings_fields"] = fields
        action["settings_fields_source"] = source

    @staticmethod
    def _resolve_plugin_relative_path(plugin_dir: Path, rel: str) -> Path | None:
        """Resolve a manifest-relative path, refusing to escape the plugin dir."""

        cleaned = rel.strip().lstrip("/").replace("\\", "/")
        if not cleaned:
            return None
        candidate = (plugin_dir / cleaned).resolve()
        try:
            candidate.relative_to(plugin_dir.resolve())
        except ValueError:
            return None
        return candidate

    @classmethod
    def _infer_settings_fields(
        cls, pi_path: Path, plugin_dir: Path
    ) -> tuple[list[dict[str, Any]], str]:
        """Parse a Property Inspector HTML file (and its local scripts) into a
        list of ``{name, source, type?, label?, required?}`` setting descriptors.

        Best-effort and heuristic — see the PI-parsing note at module scope.
        """

        html = cls._read_text_capped(pi_path)
        if html is None:
            return [], "property_inspector_unreadable"

        fields: dict[str, dict[str, Any]] = {}

        # Style A — sdpi-components: the setting key is a literal HTML attribute.
        for tag_match in SDPI_TAG_PATTERN.finditer(html):
            tag_name = tag_match.group(1).lower()
            attrs_text = tag_match.group(2)
            attrs = {key.lower(): value for key, value in HTML_ATTR_PATTERN.findall(attrs_text)}
            setting_key = attrs.get("setting")
            if not setting_key:
                continue
            entry: dict[str, Any] = {
                "name": setting_key,
                "source": "sdpi",
                "type": f"sdpi-{tag_name}",
            }
            if attrs.get("label"):
                entry["label"] = attrs["label"]
            if re.search(r"(?:^|\s)required(?:\s|=|$)", attrs_text, re.IGNORECASE):
                entry["required"] = True
            fields.setdefault(setting_key, entry)

        # Legacy sdpi.css: some PIs annotate inputs with data-setting attributes.
        for setting_key in DATA_SETTING_PATTERN.findall(html):
            fields.setdefault(setting_key, {"name": setting_key, "source": "data-setting"})

        # Styles B & C — keys live in inline and linked JS, not the HTML ids.
        js_blobs: list[str] = [match.group(1) for match in INLINE_SCRIPT_PATTERN.finditer(html)]
        for src in SCRIPT_SRC_PATTERN.findall(html)[:PI_MAX_SCRIPT_FILES]:
            if "://" in src:
                continue  # remote script — not on disk
            script_name = src.rsplit("/", 1)[-1].lower()
            if script_name in PI_LIBRARY_SCRIPTS:
                continue
            script_path = cls._resolve_plugin_relative_path(plugin_dir, src)
            if script_path is None or not script_path.is_file():
                # PI paths are often relative to the PI file, not the plugin root.
                script_path = (pi_path.parent / src.lstrip("/")).resolve()
                try:
                    script_path.relative_to(plugin_dir.resolve())
                except ValueError:
                    continue
                if not script_path.is_file():
                    continue
            script_text = cls._read_text_capped(script_path)
            if script_text:
                js_blobs.append(script_text)

        for blob in js_blobs:
            for key in JS_SETTINGS_DOT_PATTERN.findall(blob):
                if key in PI_JS_NOISE_KEYS:
                    continue
                fields.setdefault(key, {"name": key, "source": "javascript"})
            for key in JS_SETTINGS_INDEX_PATTERN.findall(blob):
                if key in PI_JS_NOISE_KEYS:
                    continue
                fields.setdefault(key, {"name": key, "source": "javascript"})

        ordered = [fields[name] for name in sorted(fields)]
        source = "property_inspector" if ordered else "property_inspector_empty"
        return ordered, source

    @staticmethod
    def _read_text_capped(path: Path) -> str | None:
        """Read up to ``PI_MAX_BYTES`` of UTF-8 text, or None if binary/oversized."""

        try:
            if path.stat().st_size > PI_MAX_BYTES:
                return None
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

    @staticmethod
    def _matches_plugin_filter(plugin: dict[str, Any], plugin_id: str | None) -> bool:
        if not plugin_id:
            return True
        target = plugin_id.strip().lower()
        if not target:
            return True
        candidates = (
            plugin.get("manifest_uuid"),
            plugin.get("plugin_uuid"),
            plugin.get("folder_id"),
            plugin.get("folder_name"),
            plugin.get("name"),
        )
        return any(
            isinstance(candidate, str) and candidate.lower() == target for candidate in candidates
        )

    def read_page(
        self,
        *,
        profile_name: str | None = None,
        profile_id: str | None = None,
        page_index: int | None = None,
        directory_id: str | None = None,
    ) -> dict[str, Any]:
        """Read a specific page manifest and return a simplified view."""

        profile_dir, profile_manifest = self._resolve_profile(
            profile_name=profile_name, profile_id=profile_id
        )
        page_ref = self._resolve_page_ref(
            profile_dir,
            profile_manifest,
            page_index=page_index,
            directory_id=directory_id,
        )
        page_manifest = _load_json(page_ref.manifest_path)
        keypad_cols, keypad_rows = self._resolve_layout(profile_manifest, page_manifest, KEYPAD)

        buttons: list[dict[str, Any]] = []
        layouts: dict[str, dict[str, int]] = {}

        for controller in page_manifest.get("Controllers") or []:
            controller_type = controller.get("Type", KEYPAD)
            cols, rows = self._resolve_layout(profile_manifest, page_manifest, controller_type)
            layouts[controller_type.lower()] = {"columns": cols, "rows": rows}

            actions = controller.get("Actions") or {}
            for position, action in sorted(
                actions.items(),
                key=lambda item: self._position_sort_key(item[0]),
            ):
                col, row = [int(part) for part in position.split(",")]
                key = (row * cols + col) if cols else col
                states = action.get("States") or [{}]
                state_index = min(max(int(action.get("State", 0)), 0), max(len(states) - 1, 0))
                active_state = states[state_index] if states else {}
                buttons.append(
                    {
                        "controller": controller_type.lower(),
                        "key": key,
                        "position": position,
                        "action_id": action.get("ActionID"),
                        "action_uuid": action.get("UUID"),
                        "plugin_uuid": action.get("Plugin", {}).get("UUID"),
                        "plugin_name": action.get("Plugin", {}).get("Name"),
                        "name": action.get("Name"),
                        "state": action.get("State", 0),
                        "title": active_state.get("Title"),
                        "image": active_state.get("Image"),
                        "settings": action.get("Settings", {}),
                        "show_title": active_state.get("ShowTitle"),
                        "raw": action,
                    }
                )

        return {
            "profiles_root": self.profiles_dir.name,
            "profile": {
                "profile_id": profile_dir.stem,
                "name": profile_manifest.get("Name", profile_dir.stem),
                "version": profile_manifest.get("Version", "unknown"),
                "device": profile_manifest.get("Device", {}),
                "current_page_uuid": profile_manifest.get("Pages", {}).get("Current"),
                "default_page_uuid": profile_manifest.get("Pages", {}).get("Default"),
            },
            "page": page_ref.to_dict(),
            "layout": {"columns": keypad_cols, "rows": keypad_rows},
            "layouts": layouts,
            "buttons": buttons,
            "raw_manifest": page_manifest,
        }

    def write_page(
        self,
        *,
        profile_name: str | None = None,
        profile_id: str | None = None,
        page_index: int | None = None,
        directory_id: str | None = None,
        page_name: str | None = None,
        buttons: list[dict[str, Any]] | None = None,
        clear_existing: bool = True,
        create_new: bool = False,
        make_current: bool = False,
        auto_quit_app: bool = False,
    ) -> dict[str, Any]:
        """Create a page or rewrite an existing page manifest."""

        app_stop_report: dict[str, Any] | None = None
        if is_stream_deck_app_running():
            if not auto_quit_app:
                raise StreamDeckAppRunningError(
                    "The Elgato Stream Deck app is running and will overwrite this "
                    "edit on quit. Retry with auto_quit_app=True to quit it first, "
                    "then call streamdeck_restart_app once your edits are complete "
                    "to apply the changes."
                )
            app_stop_report = stop_stream_deck_app()
            stop_failed = not app_stop_report.get("stopped", False)
            still_running = is_stream_deck_app_running()
            if stop_failed or still_running:
                reason = app_stop_report.get("reason", "")
                detail = f" Reason: {reason}." if reason else ""
                raise StreamDeckAppRunningError(
                    f"The Elgato Stream Deck app could not be stopped.{detail} Aborting "
                    "page write because the running app may overwrite these edits on quit."
                )

        profile_dir, profile_manifest = self._resolve_profile(
            profile_name=profile_name, profile_id=profile_id
        )
        buttons = buttons or []
        version = str(profile_manifest.get("Version", "2.0"))
        page_uuid: str | None

        if create_new:
            page_uuid = str(uuid.uuid4())
            directory_name = (
                page_uuid.upper() if version.startswith("3") else self._generate_directory_id()
            )
            page_dir = profile_dir / "Profiles" / directory_name
            page_dir.mkdir(parents=True, exist_ok=False)
            (page_dir / "Images").mkdir(exist_ok=True)
            page_manifest = copy.deepcopy(DEFAULT_PAGE_MANIFEST)
        else:
            page_ref = self._resolve_page_ref(
                profile_dir,
                profile_manifest,
                page_index=page_index,
                directory_id=directory_id,
            )
            page_uuid = page_ref.page_uuid
            page_dir = page_ref.directory_path
            page_manifest = _load_json(page_ref.manifest_path)

        if page_name is not None:
            page_manifest["Name"] = page_name

        # Group incoming buttons by the controller they target so a single write can
        # update the Keypad and Encoder controllers together without touching the other.
        buttons_by_controller: dict[str, list[dict[str, Any]]] = {}
        for button in buttons:
            controller_type = _normalize_controller(button.get("controller"))
            buttons_by_controller.setdefault(controller_type, []).append(button)

        # When clear_existing is requested but no buttons were supplied, default to
        # targeting the Keypad controller so that the caller can still clear a page
        # by writing an empty button list (restores pre-multi-controller behaviour).
        if clear_existing and not buttons_by_controller:
            buttons_by_controller[KEYPAD] = []

        layouts_out: dict[str, dict[str, int]] = {}

        # If any encoder button will land on the bundled streamdeck-mcp dial plugin,
        # make sure the plugin bundle is actually installed in the Elgato Plugins dir.
        # The app just quit (or was already stopped) so now is the right window for
        # a filesystem install that the app will pick up on relaunch.
        plugin_install_report: dict[str, Any] | None = None
        if self._any_button_needs_mcp_plugin(buttons_by_controller):
            plugin_install_report = ensure_mcp_plugin_installed()

        # Non-fatal validation notes surfaced back to the caller (e.g. a
        # third-party action written without the settings its Property Inspector
        # expects). Hard problems — an unknown plugin/action UUID — raise instead.
        warnings: list[str] = []
        # Only pay the cost of reading the installed-plugin catalog when a button
        # actually asks us to synthesize a third-party plugin action from fields.
        plugin_catalog: dict[str, dict[str, Any]] | None = None
        if any(self._button_targets_third_party_plugin(button) for button in buttons):
            plugin_catalog = self._plugin_action_catalog()

        for controller_type, ctl_buttons in buttons_by_controller.items():
            cols, rows = self._resolve_layout(profile_manifest, page_manifest, controller_type)
            if cols <= 0 or rows <= 0:
                raise ProfileValidationError(
                    f"Device model does not expose a '{controller_type}' controller."
                )
            controller = _ensure_controller(page_manifest, controller_type)
            existing = {} if clear_existing else copy.deepcopy(controller.get("Actions") or {})
            for button in ctl_buttons:
                position = self._resolve_button_position(button, columns=cols, rows=rows)
                existing[position] = self._materialize_action(
                    button,
                    page_dir,
                    controller_type=controller_type,
                    plugin_catalog=plugin_catalog,
                    warnings=warnings,
                )
            controller["Actions"] = existing or None
            layouts_out[controller_type.lower()] = {"columns": cols, "rows": rows}

        # New pages always carry a Keypad controller slot so the Elgato app can render them.
        if create_new:
            _ensure_controller(page_manifest, KEYPAD)

        primary_cols, primary_rows = self._resolve_layout(profile_manifest, page_manifest, KEYPAD)
        total_button_count = _total_action_count(page_manifest)

        if create_new:
            pages_section = profile_manifest.setdefault("Pages", {})
            pages_section.setdefault("Pages", [])
            pages_section["Pages"].append(page_uuid)
            pages_section["Current"] = (
                page_uuid
                if make_current or not pages_section.get("Current")
                else pages_section["Current"]
            )
            if not pages_section.get("Default"):
                pages_section["Default"] = page_uuid
        elif make_current:
            if not page_uuid:
                raise ProfileValidationError(
                    "Cannot mark an existing ProfilesV2 page current without a stable page UUID."
                )
            profile_manifest.setdefault("Pages", {})["Current"] = page_uuid

        _write_json_atomic(page_dir / "manifest.json", page_manifest)
        if create_new or make_current:
            _write_json_atomic(profile_dir / "manifest.json", profile_manifest)

        return {
            "created": create_new,
            "profiles_root": self.profiles_dir.name,
            "profile_id": profile_dir.stem,
            "page_index": None if create_new else page_index,
            "directory_id": page_dir.name,
            "page_uuid": page_uuid,
            "layout": {"columns": primary_cols, "rows": primary_rows},
            "layouts": layouts_out,
            "button_count": total_button_count,
            "page_name": page_manifest.get("Name", ""),
            "manifest_path": str(page_dir / "manifest.json"),
            "app_quit": app_stop_report,
            "mcp_plugin_install": plugin_install_report,
            "warnings": warnings,
        }

    def create_icon(
        self,
        *,
        text: str | None = None,
        icon: str | None = None,
        icon_color: str | None = None,
        icon_scale: float = 1.0,
        bg_color: str = DEFAULT_BG_COLOR,
        text_color: str = DEFAULT_TEXT_COLOR,
        font_size: int = 18,
        filename: str | None = None,
        shape: str = "button",
        transparent_bg: bool = False,
    ) -> dict[str, Any]:
        """Generate a PNG icon.

        ``shape`` controls the output canvas:
        - ``"button"`` (default): 72x72 — keypad keys and encoder dial faces.
        - ``"touchstrip"``: 200x100 — the per-segment strip background above a
          Stream Deck + / + XL dial, set via ``strip_background_path`` on
          ``streamdeck_write_page``.

        ``transparent_bg=True`` produces an RGBA PNG with a transparent canvas
        (``bg_color`` is ignored). Use this for dial Icons that overlay a
        touchstrip background so the glyph composes cleanly like Elgato's own
        transparent icons. Keypad faces and touchstrip backgrounds usually want
        the solid-background default.

        Provide exactly one of:
        - ``icon``: a Material Design Icons name (e.g. ``mdi:cpu-64-bit``) rendered in
          ``icon_color`` over ``bg_color``. Labels should be set via the button's
          ``title`` field on ``streamdeck_write_page`` — Elgato renders titles over the
          image, so baking text into the PNG would produce double text.
        - ``text``: centered text rendered in ``text_color`` over ``bg_color``.

        Icon names accept ``mdi:cpu``, ``mdi-cpu``, or bare ``cpu``; aliases are
        honored. On an unknown name the error message lists close-match suggestions.
        """

        if not HAS_PILLOW:
            raise ProfileManagerError("Pillow is required for icon generation.")

        if not text and not icon:
            raise ProfileValidationError("create_icon requires 'text' or 'icon'.")

        if text and icon:
            raise ProfileValidationError(
                "create_icon accepts either 'text' or 'icon', not both. "
                "Use the button's 'title' field on streamdeck_write_page for labels."
            )

        if not 0.1 <= icon_scale <= 1.0:
            raise ProfileValidationError("icon_scale must be between 0.1 and 1.0.")

        if shape not in ICON_SHAPES:
            raise ProfileValidationError(
                f"shape must be one of {sorted(ICON_SHAPES)}, got '{shape}'."
            )
        canvas_size = ICON_SHAPES[shape]

        if not transparent_bg:
            bg_color = _ensure_hex_color(bg_color, field_name="bg_color")
        text_color = _ensure_hex_color(text_color, field_name="text_color")
        resolved_icon_color = _ensure_hex_color(icon_color or text_color, field_name="icon_color")

        self.generated_icons_dir.mkdir(parents=True, exist_ok=True)
        canonical_icon_name: str | None = None
        glyph: str | None = None
        if icon:
            from mdi_icons import font_path as _mdi_font_path
            from mdi_icons import resolve as _resolve_mdi

            canonical_icon_name, glyph = _resolve_mdi(icon)

        stem_source = filename or canonical_icon_name or text or "streamdeck-icon"
        stem = _slugify(stem_source)
        if shape != "button" and filename is None:
            stem = f"{stem}-{shape}"
        icon_path = self.generated_icons_dir / f"{stem}.png"

        if transparent_bg:
            image = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        else:
            image = Image.new("RGB", canvas_size, bg_color)
        draw = ImageDraw.Draw(image)

        if glyph is not None:
            short_side = min(canvas_size)
            target_glyph_px = max(8, int(short_side * icon_scale))
            from importlib.resources import as_file as _as_file

            try:
                with _as_file(_mdi_font_path()) as font_file:
                    # MDI glyphs have built-in em-square padding, so a font set to N
                    # px renders a visual glyph noticeably smaller than N. Measure the
                    # actual bbox at a reference size, then pick the real font size
                    # that makes the bbox fill `icon_scale * short_side` pixels.
                    ref_size = 200
                    ref_font = ImageFont.truetype(str(font_file), ref_size)
                    ref_bbox = draw.textbbox((0, 0), glyph, font=ref_font)
                    ref_w = max(1, ref_bbox[2] - ref_bbox[0])
                    ref_h = max(1, ref_bbox[3] - ref_bbox[1])
                    scale = target_glyph_px / max(ref_w, ref_h)
                    glyph_font_size = max(8, int(round(ref_size * scale)))
                    glyph_font = ImageFont.truetype(str(font_file), glyph_font_size)
            except OSError as exc:
                raise ProfileManagerError(f"Could not load bundled MDI font: {exc}") from exc
            bbox = draw.textbbox((0, 0), glyph, font=glyph_font)
            gw = bbox[2] - bbox[0]
            gh = bbox[3] - bbox[1]
            gx = (canvas_size[0] - gw) / 2 - bbox[0]
            gy = (canvas_size[1] - gh) / 2 - bbox[1]
            draw.text((gx, gy), glyph, font=glyph_font, fill=resolved_icon_color)
        else:
            label_font = _resolve_font(font_size)
            bbox = draw.multiline_textbbox((0, 0), text or "", font=label_font, align="center")
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (canvas_size[0] - tw) / 2
            ty = (canvas_size[1] - th) / 2
            draw.multiline_text(
                (tx, ty), text or "", font=label_font, fill=text_color, align="center"
            )

        image.save(icon_path, format="PNG")

        result: dict[str, Any] = {
            "path": str(icon_path),
            "size": {"width": canvas_size[0], "height": canvas_size[1]},
            "shape": shape,
            "transparent_bg": transparent_bg,
        }
        if canonical_icon_name:
            result["icon"] = f"mdi:{canonical_icon_name}"
        return result

    def create_icons(
        self,
        specs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate multiple icons in one call.

        Each element of ``specs`` is a dict of keyword arguments passed through to
        ``create_icon``. Returns a list of result dicts in the same order. If one
        icon fails its validation, the returned entry carries an ``"error"`` key
        with the message so a single bad spec doesn't abort the rest of the batch.

        This exists so LLMs authoring full decks (32 keypad icons + 6 dial icons
        is normal) don't round-trip one MCP call per icon and time out.
        """

        if not isinstance(specs, list) or not specs:
            raise ProfileValidationError("create_icons requires a non-empty list of icon specs.")

        results: list[dict[str, Any]] = []
        for index, spec in enumerate(specs):
            if not isinstance(spec, dict):
                results.append({"error": f"specs[{index}] must be a dict."})
                continue

            # Coerce per-spec string values that may arrive stringified from
            # LLM output or transport coercion.
            scale_raw = spec.get("icon_scale")
            if isinstance(scale_raw, str):
                try:
                    scale_raw = float(scale_raw)
                except ValueError:
                    pass  # let downstream raise a clear TypeError/ValueError

            font_size_raw = spec.get("font_size", 18)
            if isinstance(font_size_raw, str):
                try:
                    font_size_raw = int(font_size_raw)
                except ValueError:
                    pass

            tb_raw = spec.get("transparent_bg", False)
            if isinstance(tb_raw, str):
                lowered = tb_raw.strip().lower()
                if lowered in ("true", "1", "yes"):
                    tb_raw = True
                elif lowered in ("false", "0", "no"):
                    tb_raw = False
                # Unrecognized strings (including "") are left as-is;
                # bool() below will treat non-empty strings as True.
            transparent_bg = bool(tb_raw)

            kwargs = {
                "text": spec.get("text"),
                "icon": spec.get("icon"),
                "icon_color": spec.get("icon_color"),
                "icon_scale": 1.0 if scale_raw is None else scale_raw,
                "bg_color": spec.get("bg_color", DEFAULT_BG_COLOR),
                "text_color": spec.get("text_color", DEFAULT_TEXT_COLOR),
                "font_size": font_size_raw,
                "filename": spec.get("filename"),
                "shape": spec.get("shape", "button"),
                "transparent_bg": transparent_bg,
            }
            try:
                results.append(self.create_icon(**kwargs))
            except (ProfileValidationError, ProfileManagerError, ValueError, TypeError) as exc:
                # ValueError covers mdi_icons.IconNotFoundError (a ValueError
                # subclass). TypeError covers bad numeric types after coercion.
                # Record the failure so one bad spec doesn't abort the batch.
                results.append({"error": str(exc), "spec_index": index})
        return results

    def create_action(
        self,
        *,
        name: str,
        command: str,
        working_directory: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Create a shell script and return an Open action block for it."""

        if not command.strip():
            raise ProfileValidationError("command cannot be empty.")
        if sys.platform == "win32":
            raise ProfileValidationError(
                "streamdeck_create_action is currently only supported on POSIX systems."
            )

        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        stem = _slugify(filename or name)
        script_path = self.scripts_dir / f"{stem}.sh"

        lines = ["#!/bin/bash", "set -e"]
        if working_directory:
            lines.append(f"cd {shlex.quote(working_directory)}")
        lines.append(command)
        script_path.write_text("\n".join(lines) + "\n")
        script_path.chmod(0o755)

        action = self._build_open_action(path=script_path, title=name)
        return {
            "script_path": str(script_path),
            "action": action,
        }

    def restart_app(self) -> dict[str, Any]:
        """Restart the Stream Deck desktop app on macOS."""

        if sys.platform != "darwin":
            raise ProfileManagerError(
                "streamdeck_restart_app is currently only supported on macOS."
            )

        app_path = _resolve_app_path()
        if not app_path.exists():
            raise ProfileManagerError(
                f"Stream Deck app not found at {app_path}. "
                f"Set {STREAM_DECK_APP_PATH_ENV} to override the default install path."
            )

        stop_report = stop_stream_deck_app()

        # `open -a <name>` relies on LaunchServices name lookup, which returns error
        # -600 on some systems even when the bundle is present. Launching by explicit
        # path bypasses that lookup.
        result = subprocess.run(
            ["open", str(app_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise ProfileManagerError(
                f"Failed to relaunch Stream Deck ({app_path}): {message or 'unknown error'}"
            )

        return {
            "restarted": True,
            "app_path": str(app_path),
            "stop": stop_report,
        }

    def _resolve_profile(
        self,
        *,
        profile_name: str | None,
        profile_id: str | None,
    ) -> tuple[Path, dict[str, Any]]:
        if not self.profiles_dir.exists():
            raise ProfileNotFoundError(f"Profiles directory does not exist: {self.profiles_dir}")

        matches: list[tuple[Path, dict[str, Any]]] = []
        for profile_dir in sorted(self.profiles_dir.glob("*.sdProfile")):
            manifest = _load_json(profile_dir / "manifest.json")
            if profile_id and profile_dir.stem.lower() == profile_id.lower():
                return profile_dir, manifest
            if profile_name and str(manifest.get("Name", "")).lower() == profile_name.lower():
                matches.append((profile_dir, manifest))

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ProfileValidationError(
                f"Multiple profiles match '{profile_name}'. Use profile_id instead."
            )

        requested = profile_id or profile_name or "<unspecified>"
        raise ProfileNotFoundError(f"Profile not found: {requested}")

    def _page_refs(self, profile_dir: Path, profile_manifest: dict[str, Any]) -> list[PageRef]:
        profiles_path = profile_dir / "Profiles"
        if not profiles_path.exists():
            return []

        version = str(profile_manifest.get("Version", "2.0"))
        if version.startswith("3"):
            return self._page_refs_v3(profiles_path, profile_manifest)
        return self._page_refs_v2(profiles_path, profile_manifest)

    def _page_refs_v3(self, profiles_path: Path, profile_manifest: dict[str, Any]) -> list[PageRef]:
        page_refs: list[PageRef] = []
        ordered_page_ids: list[tuple[str, bool]] = []
        pages = profile_manifest.get("Pages", {})
        default_uuid = pages.get("Default")
        if default_uuid:
            ordered_page_ids.append((default_uuid, True))
        for page_uuid in pages.get("Pages", []):
            ordered_page_ids.append((page_uuid, False))

        used: set[str] = set()
        for page_index, (page_uuid, is_default) in enumerate(ordered_page_ids):
            directory_id = str(page_uuid).upper()
            manifest_path = profiles_path / directory_id / "manifest.json"
            if not manifest_path.exists():
                continue
            used.add(directory_id)
            page_refs.append(
                self._build_page_ref(
                    page_index=page_index,
                    directory_id=directory_id,
                    page_uuid=str(page_uuid).lower(),
                    manifest_path=manifest_path,
                    version=str(profile_manifest.get("Version", "unknown")),
                    mapping="page-uuid",
                    is_default=is_default,
                    is_current=_normalize_uuid(str(page_uuid))
                    == _normalize_uuid(str(pages.get("Current", ""))),
                )
            )

        for manifest_path in sorted(profiles_path.glob("*/manifest.json")):
            directory_id = manifest_path.parent.name.upper()
            if directory_id in used:
                continue
            page_refs.append(
                self._build_page_ref(
                    page_index=len(page_refs),
                    directory_id=directory_id,
                    page_uuid=directory_id.lower() if _looks_like_uuid(directory_id) else None,
                    manifest_path=manifest_path,
                    version=str(profile_manifest.get("Version", "unknown")),
                    mapping="unreferenced",
                    is_default=False,
                    is_current=False,
                )
            )

        return page_refs

    def _page_refs_v2(self, profiles_path: Path, profile_manifest: dict[str, Any]) -> list[PageRef]:
        page_refs: list[PageRef] = []
        entries = sorted(
            (Path(entry.path) for entry in os.scandir(profiles_path) if entry.is_dir()),
            key=lambda path: path.name.lower(),
        )
        for page_index, page_dir in enumerate(entries):
            page_refs.append(
                self._build_page_ref(
                    page_index=page_index,
                    directory_id=page_dir.name,
                    page_uuid=None,
                    manifest_path=page_dir / "manifest.json",
                    version=str(profile_manifest.get("Version", "unknown")),
                    mapping="directory-order",
                    is_default=False,
                    is_current=False,
                )
            )
        return page_refs

    def _build_page_ref(
        self,
        *,
        page_index: int,
        directory_id: str,
        page_uuid: str | None,
        manifest_path: Path,
        version: str,
        mapping: str,
        is_default: bool,
        is_current: bool,
    ) -> PageRef:
        page_manifest = _load_json(manifest_path)
        return PageRef(
            page_index=page_index,
            directory_id=directory_id,
            page_uuid=page_uuid,
            manifest_path=manifest_path,
            version=version,
            mapping=mapping,
            is_default=is_default,
            is_current=is_current,
            name=str(page_manifest.get("Name", "")),
            button_count=_total_action_count(page_manifest),
            icon_count=_count_icons(manifest_path.parent),
        )

    def _resolve_page_ref(
        self,
        profile_dir: Path,
        profile_manifest: dict[str, Any],
        *,
        page_index: int | None,
        directory_id: str | None,
    ) -> PageRef:
        page_refs = self._page_refs(profile_dir, profile_manifest)
        if directory_id:
            for page_ref in page_refs:
                if page_ref.directory_id.lower() == directory_id.lower():
                    return page_ref
            raise PageNotFoundError(f"Page directory not found: {directory_id}")

        if page_index is None:
            raise ProfileValidationError("Provide either page_index or directory_id.")

        for page_ref in page_refs:
            if page_ref.page_index == page_index:
                return page_ref

        raise PageNotFoundError(f"Page index not found: {page_index}")

    def _resolve_layout(
        self,
        profile_manifest: dict[str, Any],
        page_manifest: dict[str, Any] | None = None,
        controller_type: str = KEYPAD,
    ) -> tuple[int, int]:
        device_model = str(profile_manifest.get("Device", {}).get("Model", ""))
        model_entry = MODEL_LAYOUTS.get(device_model)
        if model_entry and controller_type in model_entry:
            return model_entry[controller_type]

        if page_manifest:
            actions = _controller_actions(page_manifest, controller_type)
            if actions:
                cols = max(int(position.split(",")[0]) for position in actions) + 1
                rows = max(int(position.split(",")[1]) for position in actions) + 1
                if cols > 0 and rows > 0:
                    return cols, rows

        if controller_type == ENCODER:
            return (0, 0)

        return (5, 3)

    def _resolve_button_position(
        self,
        button: dict[str, Any],
        *,
        columns: int,
        rows: int,
    ) -> str:
        position = button.get("position")
        if position:
            if not isinstance(position, str) or not POSITION_PATTERN.match(position):
                raise ProfileValidationError(
                    f"Invalid button position '{position}'. Use 'col,row'."
                )
            col, row = [int(part) for part in position.split(",")]
        elif "key" in button:
            key = button["key"]
            if not isinstance(key, int) or key < 0:
                raise ProfileValidationError(f"Invalid button key '{key}'.")
            col = key % columns
            row = key // columns
        else:
            raise ProfileValidationError("Each button needs either 'key' or 'position'.")

        if col >= columns or row >= rows:
            raise ProfileValidationError(
                f"Button position {col},{row} exceeds the inferred deck layout {columns}x{rows}."
            )

        return f"{col},{row}"

    def _materialize_action(
        self,
        button: dict[str, Any],
        page_dir: Path,
        *,
        controller_type: str = KEYPAD,
        plugin_catalog: dict[str, dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        raw_action = button.get("action")
        if raw_action is None:
            action = self._build_action_from_fields(
                button,
                controller_type=controller_type,
                plugin_catalog=plugin_catalog,
                warnings=warnings,
            )
        elif isinstance(raw_action, str):
            try:
                action = json.loads(raw_action)
            except json.JSONDecodeError as exc:
                raise ProfileValidationError(f"Button action is not valid JSON: {exc}") from exc
        elif isinstance(raw_action, dict):
            action = copy.deepcopy(raw_action)
        else:
            raise ProfileValidationError("Button action must be an object or JSON string.")

        states = copy.deepcopy(action.get("States") or [{}])
        state_index = min(max(int(action.get("State", 0)), 0), max(len(states) - 1, 0))
        state_data = copy.deepcopy(states[state_index] or {})

        if button.get("title") is not None:
            state_data["Title"] = button["title"]
        if button.get("font_size") is not None:
            state_data["FontSize"] = int(button["font_size"])
        elif "Title" in state_data and "FontSize" not in state_data:
            state_data["FontSize"] = DEFAULT_FONT_SIZE
        if button.get("title_color") is not None:
            state_data["TitleColor"] = _ensure_hex_color(
                button["title_color"], field_name="title_color"
            )
        elif "Title" in state_data and "TitleColor" not in state_data:
            state_data["TitleColor"] = DEFAULT_TEXT_COLOR.lower()
        if button.get("title_alignment") is not None:
            state_data["TitleAlignment"] = button["title_alignment"]
        elif "Title" in state_data and "TitleAlignment" not in state_data:
            state_data["TitleAlignment"] = DEFAULT_TITLE_ALIGNMENT
        if button.get("show_title") is not None:
            state_data["ShowTitle"] = bool(button["show_title"])
        elif "Title" in state_data and "ShowTitle" not in state_data:
            state_data["ShowTitle"] = True
        if "FontFamily" not in state_data:
            state_data["FontFamily"] = state_data.get("FontFamily", "")
        if "FontStyle" not in state_data:
            state_data["FontStyle"] = state_data.get("FontStyle", "")
        if "FontUnderline" not in state_data:
            state_data["FontUnderline"] = state_data.get("FontUnderline", False)
        if "OutlineThickness" not in state_data:
            state_data["OutlineThickness"] = state_data.get("OutlineThickness", 2)

        icon_path = button.get("icon_path")
        strip_background_path = button.get("strip_background_path")

        if controller_type == ENCODER:
            encoder_section = action.setdefault("Encoder", {})
            if icon_path:
                encoder_section["Icon"] = self._copy_icon_to_page(
                    Path(icon_path).expanduser(), page_dir
                )
            if strip_background_path:
                encoder_section["background"] = self._copy_icon_to_page(
                    Path(strip_background_path).expanduser(), page_dir
                )
        else:
            if strip_background_path:
                raise ProfileValidationError(
                    "strip_background_path is only valid for encoder/dial buttons."
                )
            if button.get("encoder_layout") is not None:
                raise ProfileValidationError(
                    "encoder_layout is only valid for encoder/dial buttons."
                )
            if icon_path:
                state_data["Image"] = self._copy_icon_to_page(
                    Path(icon_path).expanduser(), page_dir
                )

        states[state_index] = state_data
        action["States"] = states
        return action

    def _build_action_from_fields(
        self,
        button: dict[str, Any],
        *,
        controller_type: str = KEYPAD,
        plugin_catalog: dict[str, dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        encoder_layout = button.get("encoder_layout")
        if encoder_layout is not None and controller_type != ENCODER:
            raise ProfileValidationError("encoder_layout is only valid for encoder/dial buttons.")
        if encoder_layout is not None and any(
            button.get(k) for k in ("path", "action_type", "plugin_uuid", "action_uuid")
        ):
            raise ProfileValidationError(
                "encoder_layout is a convenience field for the built-in MCP dial. "
                "Do not combine with path/action_type/plugin_uuid/action_uuid."
            )
        action_type = button.get("action_type")
        if action_type == "next_page":
            return self._build_navigation_action(direction="next")
        if action_type == "previous_page":
            return self._build_navigation_action(direction="previous")

        path = button.get("path")
        if path:
            return self._build_open_action(path=Path(path).expanduser(), title=button.get("title"))

        plugin_uuid = button.get("plugin_uuid")
        action_uuid = button.get("action_uuid")
        if plugin_uuid and action_uuid:
            return self._build_third_party_action(
                button, plugin_catalog=plugin_catalog, warnings=warnings
            )

        # Encoder/dial buttons without any explicit action fields fall back to the
        # bundled streamdeck-mcp dial plugin, which is the only action shell that
        # allows per-instance Encoder.Icon / Encoder.background writes to survive.
        if controller_type == ENCODER:
            return self._build_mcp_dial_action(button)

        raise ProfileValidationError(
            "Button needs either 'action', 'path', 'action_type', "
            "or explicit plugin/action UUID fields."
        )

    @staticmethod
    def _button_targets_third_party_plugin(button: dict[str, Any]) -> bool:
        """True when a button asks us to synthesize a native action from a
        plugin_uuid + action_uuid pair (rather than copy a raw ``action`` or use
        a convenience path/action_type). These are the only buttons that need the
        installed-plugin catalog for validation and metadata defaults.
        """

        if button.get("action") is not None:
            return False
        if button.get("path") or button.get("action_type"):
            return False
        return bool(button.get("plugin_uuid")) and bool(button.get("action_uuid"))

    def _plugin_action_catalog(self) -> dict[str, dict[str, Any]]:
        """Index installed plugins by every UUID/folder id they answer to.

        Returns ``{}`` when the plugins directory is missing or unreadable so
        callers can distinguish "not installed" (non-empty catalog, UUID absent)
        from "cannot verify" (empty catalog).
        """

        try:
            listing = self.list_plugins(include_settings_schema=True)
        except (ProfileManagerError, OSError):
            return {}
        catalog: dict[str, dict[str, Any]] = {}
        for plugin in listing.get("plugins", []):
            for key in (
                plugin.get("plugin_uuid"),
                plugin.get("manifest_uuid"),
                plugin.get("folder_id"),
            ):
                if isinstance(key, str) and key:
                    catalog.setdefault(key.lower(), plugin)
        return catalog

    @staticmethod
    def _match_plugin_action(
        plugin_meta: dict[str, Any], action_uuid: str
    ) -> dict[str, Any] | None:
        target = action_uuid.strip().lower()
        for action in plugin_meta.get("actions") or []:
            uuid_val = action.get("uuid")
            if isinstance(uuid_val, str) and uuid_val.lower() == target:
                return action
        return None

    @staticmethod
    def _warn_missing_settings(
        action_meta: dict[str, Any],
        settings: dict[str, Any],
        action_uuid: str,
        warnings: list[str],
    ) -> None:
        fields = action_meta.get("settings_fields") or []
        field_names = [
            field["name"] for field in fields if isinstance(field, dict) and field.get("name")
        ]
        required = [
            field["name"]
            for field in fields
            if isinstance(field, dict) and field.get("required") and field.get("name")
        ]
        provided = set(settings.keys()) if isinstance(settings, dict) else set()
        missing_required = [name for name in required if name not in provided]
        if missing_required:
            warnings.append(
                f"Action '{action_uuid}' expects required settings "
                f"{missing_required} but they were not provided "
                f"(settings keys given: {sorted(provided)})."
            )
        elif field_names and not provided:
            warnings.append(
                f"Action '{action_uuid}' declares settings fields "
                f"{sorted(set(field_names))} but no settings were provided. The "
                "button may render but stay inert until configured — call "
                "streamdeck_read_plugins for each field's details."
            )

    def _build_third_party_action(
        self,
        button: dict[str, Any],
        *,
        plugin_catalog: dict[str, dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build a native action object for an arbitrary installed plugin.

        Validates the plugin_uuid/action_uuid against the installed catalog when
        one is available, defaults Plugin metadata and the per-instance ``States``
        array from the plugin manifest, and copies the caller's ``settings`` in
        the same shape Stream Deck itself writes so the action survives the Elgato
        app's overwrite-on-quit.
        """

        plugin_uuid = button["plugin_uuid"]
        action_uuid = button["action_uuid"]

        plugin_meta: dict[str, Any] | None = None
        action_meta: dict[str, Any] | None = None
        if plugin_catalog is not None:
            plugin_meta = plugin_catalog.get(plugin_uuid.strip().lower())
            if plugin_meta is None:
                if plugin_catalog:
                    available = sorted(
                        {
                            plugin.get("plugin_uuid")
                            for plugin in plugin_catalog.values()
                            if plugin.get("plugin_uuid")
                        }
                    )
                    raise ProfileValidationError(
                        f"plugin_uuid '{plugin_uuid}' is not installed. Installed "
                        f"plugin UUIDs: {available}. Call streamdeck_read_plugins "
                        "to see installed plugins and their action UUIDs."
                    )
                if warnings is not None:
                    warnings.append(
                        f"Could not verify plugin_uuid '{plugin_uuid}': no readable "
                        "plugins were found in the Elgato Plugins directory. Writing "
                        "the action unverified."
                    )
            else:
                action_meta = self._match_plugin_action(plugin_meta, action_uuid)
                if action_meta is None:
                    declared = [
                        action.get("uuid")
                        for action in plugin_meta.get("actions") or []
                        if action.get("uuid")
                    ]
                    raise ProfileValidationError(
                        f"action_uuid '{action_uuid}' is not declared by plugin "
                        f"'{plugin_uuid}'. Declared actions: {declared}. Call "
                        "streamdeck_read_plugins for each action's UUID and "
                        "settings fields."
                    )

        plugin_name = button.get("plugin_name") or (plugin_meta or {}).get("name") or plugin_uuid
        plugin_version = button.get("plugin_version") or (plugin_meta or {}).get("version") or "1.0"
        action_name = button.get("action_name") or button.get("title")
        if not action_name:
            action_name = (action_meta or {}).get("name") or ""

        # Default the per-instance States array to the manifest-declared count so
        # multi-state actions (toggles, dual-state entities) round-trip cleanly.
        if button.get("states") is not None:
            states = copy.deepcopy(button["states"])
        else:
            declared_states = (action_meta or {}).get("states")
            if isinstance(declared_states, list) and declared_states:
                states = [{} for _ in declared_states]
            else:
                states = [{}]

        settings = copy.deepcopy(button.get("settings", {}))
        if warnings is not None and action_meta is not None:
            self._warn_missing_settings(action_meta, settings, action_uuid, warnings)

        state_value = int(button.get("state", 0))
        if states:
            state_value = min(max(state_value, 0), len(states) - 1)

        return {
            "ActionID": button.get("action_id", str(uuid.uuid4())),
            "LinkedTitle": bool(button.get("linked_title", False)),
            "Name": action_name,
            "Plugin": {
                "Name": plugin_name,
                "UUID": plugin_uuid,
                "Version": plugin_version,
            },
            "Settings": settings,
            "State": state_value,
            "States": states,
            "UUID": action_uuid,
        }

    @staticmethod
    def _any_button_needs_mcp_plugin(
        buttons_by_controller: dict[str, list[dict[str, Any]]],
    ) -> bool:
        from streamdeck_plugin import PLUGIN_UUID

        for controller_type, buttons in buttons_by_controller.items():
            if controller_type != ENCODER:
                continue
            for button in buttons:
                raw_action = button.get("action")
                if isinstance(raw_action, dict):
                    if (raw_action.get("Plugin") or {}).get("UUID") == PLUGIN_UUID:
                        return True
                elif isinstance(raw_action, str):
                    # Action may be a JSON-encoded dict — parse and check UUID.
                    try:
                        parsed = json.loads(raw_action)
                        if isinstance(parsed, dict) and (
                            (parsed.get("Plugin") or {}).get("UUID") == PLUGIN_UUID
                        ):
                            return True
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif raw_action is None:
                    # Will be built as an MCP dial action iff no other action spec present.
                    if not any(
                        button.get(k) for k in ("path", "action_type", "plugin_uuid", "action_uuid")
                    ):
                        return True
                if button.get("plugin_uuid") == PLUGIN_UUID:
                    return True
        return False

    def install_mcp_plugin(self, *, force: bool = False) -> dict[str, Any]:
        """Install the bundled streamdeck-mcp plugin into the Elgato Plugins dir.

        Thin instance wrapper so callers that already hold a ProfileManager can
        trigger an explicit install without importing the module-level helper.
        """
        return ensure_mcp_plugin_installed(force=force)

    def _build_mcp_dial_action(self, button: dict[str, Any]) -> dict[str, Any]:
        from streamdeck_plugin import (
            DEFAULT_ACTION_UUID,
            LAYOUT_ACTION_UUIDS,
            PLUGIN_UUID,
            PLUGIN_VERSION,
            SUPPORTED_ENCODER_LAYOUTS,
        )

        encoder_layout = button.get("encoder_layout")
        if encoder_layout is not None:
            if encoder_layout not in LAYOUT_ACTION_UUIDS:
                raise ProfileValidationError(
                    f"Unknown encoder_layout '{encoder_layout}'. "
                    f"Supported: {', '.join(SUPPORTED_ENCODER_LAYOUTS)}."
                )
            action_uuid = LAYOUT_ACTION_UUIDS[encoder_layout]
            name = f"MCP Dial ({encoder_layout})"
        else:
            action_uuid = DEFAULT_ACTION_UUID
            name = "MCP Dial"

        return {
            "ActionID": str(uuid.uuid4()),
            "LinkedTitle": False,
            "Name": name,
            "Plugin": {
                "Name": "streamdeck-mcp",
                "UUID": PLUGIN_UUID,
                "Version": PLUGIN_VERSION,
            },
            "Settings": copy.deepcopy(button.get("settings", {})),
            "State": 0,
            "States": [{}],
            "UUID": action_uuid,
        }

    def _build_navigation_action(self, *, direction: str) -> dict[str, Any]:
        if direction not in {"next", "previous"}:
            raise ProfileValidationError(f"Unsupported navigation direction '{direction}'.")
        action_uuid = f"com.elgato.streamdeck.page.{direction}"
        name = "Next Page" if direction == "next" else "Previous Page"
        return {
            "ActionID": str(uuid.uuid4()),
            "LinkedTitle": True,
            "Name": name,
            "Plugin": {
                "Name": "Pages",
                "UUID": "com.elgato.streamdeck.page",
                "Version": "1.0",
            },
            "Settings": {},
            "State": 0,
            "States": [{}],
            "UUID": action_uuid,
        }

    def _build_open_action(self, *, path: Path, title: str | None) -> dict[str, Any]:
        return {
            "ActionID": str(uuid.uuid4()),
            "LinkedTitle": title is None,
            "Name": "Open",
            "Plugin": {
                "Name": "Open",
                "UUID": "com.elgato.streamdeck.system.open",
                "Version": "1.0",
            },
            "Settings": {
                "path": _quote_open_path(path),
            },
            "State": 0,
            "States": [
                {
                    "Title": title or "",
                    "FontSize": DEFAULT_FONT_SIZE,
                    "FontFamily": "",
                    "FontStyle": "",
                    "FontUnderline": False,
                    "OutlineThickness": 2,
                    "TitleAlignment": DEFAULT_TITLE_ALIGNMENT,
                    "TitleColor": DEFAULT_TEXT_COLOR.lower(),
                    "ShowTitle": bool(title),
                }
            ],
            "UUID": "com.elgato.streamdeck.system.open",
        }

    def _copy_icon_to_page(self, source_path: Path, page_dir: Path) -> str:
        if not source_path.exists():
            raise ProfileValidationError(f"Icon file not found: {source_path}")

        images_dir = page_dir / "Images"
        images_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{self._generate_directory_id(length=27)}.png"
        target_path = images_dir / target_name

        if source_path.suffix.lower() == ".png":
            shutil.copy2(source_path, target_path)
        else:
            if not HAS_PILLOW:
                raise ProfileManagerError("Pillow is required to convert non-PNG icons.")
            image = Image.open(source_path)
            image.save(target_path, format="PNG")

        return f"Images/{target_name}"

    def _position_sort_key(self, position: str) -> tuple[int, int]:
        col, row = [int(part) for part in position.split(",")]
        return (row, col)

    def _generate_directory_id(self, *, length: int = 27) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))
