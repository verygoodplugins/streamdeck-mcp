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
    # Stream Deck (Original)
    "20GBA9901": {KEYPAD: (5, 3)},
    # Stream Deck + XL (36 keys, 6 dials with 1200x100 touchstrip)
    "20GBX9901": {KEYPAD: (9, 4), ENCODER: (6, 1)},
    # Emulator used by the Elgato desktop app
    "UI Stream Deck": {KEYPAD: (4, 2)},
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
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ProfileManagerError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileManagerError(f"Invalid JSON in {path}: {exc}") from exc


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True))
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
            profiles.append(
                {
                    "profile_id": profile_dir.stem,
                    "name": manifest.get("Name", profile_dir.stem),
                    "version": manifest.get("Version", "unknown"),
                    "profiles_dir": str(self.profiles_dir),
                    "profiles_root": self.profiles_dir.name,
                    "profile_path": str(profile_dir),
                    "device": manifest.get("Device", {}),
                    "current_page_uuid": manifest.get("Pages", {}).get("Current"),
                    "default_page_uuid": manifest.get("Pages", {}).get("Default"),
                    "page_count": len(page_refs),
                    "pages": [page_ref.to_dict() for page_ref in page_refs],
                }
            )
        return profiles

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
                existing[position] = self._materialize_action(button, page_dir)
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
        }

    def create_icon(
        self,
        *,
        text: str,
        bg_color: str = DEFAULT_BG_COLOR,
        text_color: str = DEFAULT_TEXT_COLOR,
        font_size: int = 18,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Generate a simple 72x72 PNG icon with centered text."""

        if not HAS_PILLOW:
            raise ProfileManagerError("Pillow is required for icon generation.")

        bg_color = _ensure_hex_color(bg_color, field_name="bg_color")
        text_color = _ensure_hex_color(text_color, field_name="text_color")

        self.generated_icons_dir.mkdir(parents=True, exist_ok=True)
        stem = _slugify(filename or text or "streamdeck-icon")
        icon_path = self.generated_icons_dir / f"{stem}.png"

        image = Image.new("RGB", DEFAULT_ICON_SIZE, bg_color)
        draw = ImageDraw.Draw(image)
        font = _resolve_font(font_size)
        bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (DEFAULT_ICON_SIZE[0] - text_width) / 2
        y = (DEFAULT_ICON_SIZE[1] - text_height) / 2
        draw.multiline_text((x, y), text, font=font, fill=text_color, align="center")
        image.save(icon_path, format="PNG")

        return {
            "path": str(icon_path),
            "size": {"width": DEFAULT_ICON_SIZE[0], "height": DEFAULT_ICON_SIZE[1]},
        }

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

    def _materialize_action(self, button: dict[str, Any], page_dir: Path) -> dict[str, Any]:
        raw_action = button.get("action")
        if raw_action is None:
            action = self._build_action_from_fields(button)
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
        if icon_path:
            state_data["Image"] = self._copy_icon_to_page(Path(icon_path).expanduser(), page_dir)

        states[state_index] = state_data
        action["States"] = states
        return action

    def _build_action_from_fields(self, button: dict[str, Any]) -> dict[str, Any]:
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
            return {
                "ActionID": button.get("action_id", str(uuid.uuid4())),
                "LinkedTitle": bool(button.get("linked_title", False)),
                "Name": button.get("action_name", button.get("title", "")),
                "Plugin": {
                    "Name": button.get("plugin_name", plugin_uuid),
                    "UUID": plugin_uuid,
                    "Version": button.get("plugin_version", "1.0"),
                },
                "Settings": copy.deepcopy(button.get("settings", {})),
                "State": int(button.get("state", 0)),
                "States": copy.deepcopy(button.get("states", [{}])),
                "UUID": action_uuid,
            }

        raise ProfileValidationError(
            "Button needs either 'action', 'path', 'action_type', "
            "or explicit plugin/action UUID fields."
        )

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
