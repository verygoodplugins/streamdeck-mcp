#!/usr/bin/env python3
"""
Stream Deck Profile Writer MCP Server

Writes directly to the Elgato Stream Deck desktop app profile manifests instead
of taking exclusive USB control of the hardware.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)

from profile_manager import (
    PageNotFoundError,
    ProfileManager,
    ProfileManagerError,
    ProfileNotFoundError,
    ProfileValidationError,
    StreamDeckAppRunningError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("streamdeck-profile-mcp")

manager = ProfileManager()
server = Server("streamdeck-profile-mcp")

_SKILL_PATH = (
    Path(__file__).parent
    / "streamdeck_assets"
    / "skill"
    / "streamdeck-designer"
    / "SKILL.md"
)


def _scalar_or_string(base_type: str) -> dict[str, Any]:
    """Schema helper: field accepts either a native JSON value or a string
    form of it. Works around MCP clients (notably Claude Code's tool-call
    transport as of April 2026) that serialize non-string tool-call
    arguments as JSON strings before schema validation runs.

    ``base_type`` is one of 'integer', 'number', 'boolean'. For arrays, use a
    custom ``oneOf`` that preserves the ``items`` schema for the array branch.
    """

    return {"oneOf": [{"type": base_type}, {"type": "string"}]}


def _coerce_arguments(
    arguments: dict[str, Any],
    *,
    ints: tuple[str, ...] = (),
    nums: tuple[str, ...] = (),
    bools: tuple[str, ...] = (),
    arrays: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Convert stringified tool arguments back to native types.

    MCP clients sometimes stringify typed args in transit (Claude Code does
    this with booleans, numbers, integers and nested arrays). Schemas here
    declare ``oneOf [native, string]`` so validation passes either shape;
    this helper normalizes before the handler runs. Unknown/unconvertible
    strings are left as-is so the downstream handler's error message wins.
    """

    out = dict(arguments)
    for key in ints:
        v = out.get(key)
        if isinstance(v, str):
            try:
                out[key] = int(v)
            except ValueError:
                pass
    for key in nums:
        v = out.get(key)
        if isinstance(v, str):
            try:
                out[key] = float(v)
            except ValueError:
                pass
    for key in bools:
        v = out.get(key)
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in ("true", "1", "yes"):
                out[key] = True
            elif lowered in ("false", "0", "no"):
                out[key] = False
            # Empty strings intentionally pass through — let the handler's
            # `arguments.get(key, default)` path apply rather than silently
            # coerce them to False.
    for key in arrays:
        v = out.get(key)
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    out[key] = parsed
            except (json.JSONDecodeError, TypeError):
                pass
    return out


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available profile writer tools."""

    button_schema = {
        "type": "object",
        "properties": {
            "controller": {
                "type": "string",
                "enum": ["keypad", "key", "button", "encoder", "dial"],
                "default": "keypad",
                "description": (
                    "Which physical controller this button targets. "
                    "'keypad' (default) addresses the LCD keys; "
                    "'encoder' (aka 'dial') addresses the rotary/touch dials on "
                    "Stream Deck + and + XL. "
                    "The key/position indexes are scoped to the chosen controller."
                ),
            },
            "key": {
                "type": "integer",
                "description": (
                    "Button index scoped to the chosen controller (0-based). "
                    "For keypad controllers the index is row-major "
                    "(left-to-right, then top-to-bottom). "
                    "For encoder/dial controllers it is a simple 0..N-1 dial index."
                ),
            },
            "position": {
                "type": "string",
                "description": (
                    "Native position string 'col,row' within the chosen controller. "
                    "Use this when you already know the grid slot."
                ),
            },
            "title": {
                "type": "string",
                "description": "Button title to write into the first active state.",
            },
            "icon_path": {
                "type": "string",
                "description": (
                    "Path to a local icon file. PNG preferred; other formats are converted. "
                    "Keypad buttons: 72x72 key face image. Encoder buttons: 72x72 dial Icon "
                    "overlay on the touchstrip."
                ),
            },
            "strip_background_path": {
                "type": "string",
                "description": (
                    "Encoder/dial only: path to a 200x100 PNG used as the touchstrip "
                    "segment background behind the dial. Generate one with "
                    "streamdeck_create_icon(shape='touchstrip'). Writing this field on a "
                    "keypad button is an error."
                ),
            },
            "encoder_layout": {
                "type": "string",
                "enum": ["$X1", "$A0", "$A1", "$B1", "$B2", "$C1"],
                "description": (
                    "Encoder/dial only: built-in Elgato touchstrip layout. Omit for "
                    "the default (no declared layout → Elgato default composition with "
                    "full-strip background show-through). Choose a variant for plugin-"
                    "rendered layouts: $X1 (title + centered icon), $A0 (title + full-"
                    "width image), $A1 (title + icon + value slot), $B1 (progress bar), "
                    "$B2 (gradient progress), $C1 (dual icon/progress rows). Selecting "
                    "a layout forgoes strip-background show-through — the declared "
                    "layout replaces the default composition. Do not combine with "
                    "path/action_type/plugin_uuid/action_uuid."
                ),
            },
            "path": {
                "type": "string",
                "description": (
                    "Convenience field for Open actions. "
                    "Usually a script generated by streamdeck_create_action."
                ),
            },
            "action_type": {
                "type": "string",
                "description": "Convenience action type: 'next_page' or 'previous_page'.",
            },
            "action": {
                "type": "object",
                "description": "Full native Stream Deck action object to write at this position.",
            },
            "plugin_uuid": {
                "type": "string",
                "description": (
                    "For advanced actions, the plugin UUID used "
                    "when building a native action object."
                ),
            },
            "plugin_name": {
                "type": "string",
            },
            "plugin_version": {
                "type": "string",
            },
            "action_uuid": {
                "type": "string",
                "description": (
                    "For advanced actions, the native action UUID, "
                    "for example com.elgato.streamdeck.page.next."
                ),
            },
            "action_name": {
                "type": "string",
            },
            "settings": {
                "type": "object",
                "description": "Native action settings object.",
            },
            "state": {
                "type": "integer",
            },
            "font_size": {
                "type": "integer",
            },
            "title_color": {
                "type": "string",
                "description": "Hex color for the title, for example #ffffff.",
            },
            "title_alignment": {
                "type": "string",
                "description": "Title placement such as top or bottom.",
            },
            "show_title": {
                "type": "boolean",
            },
        },
    }

    return [
        Tool(
            name="streamdeck_read_profiles",
            description=(
                "List Stream Deck desktop profiles from the active "
                "ProfilesV3 or ProfilesV2 directory."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="streamdeck_read_page",
            description="Read a profile page by profile name or ID and page index or directory ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_name": {
                        "type": "string",
                        "description": "Exact profile name as shown in the Elgato app.",
                    },
                    "profile_id": {
                        "type": "string",
                        "description": (
                            "Directory-based profile ID, usually the "
                            ".sdProfile folder name without the suffix."
                        ),
                    },
                    "page_index": {
                        **_scalar_or_string("integer"),
                        "description": (
                            "Zero-based page index from streamdeck_read_profiles. "
                            "Accepts int or a string form."
                        ),
                    },
                    "directory_id": {
                        "type": "string",
                        "description": (
                            "Page directory ID from streamdeck_read_profiles. "
                            "This is the safest target for updates."
                        ),
                    },
                },
            },
        ),
        Tool(
            name="streamdeck_write_page",
            description=(
                "Create a new page or replace/update an existing Stream Deck desktop "
                "page manifest. IMPORTANT: the Elgato desktop app overwrites profile "
                "manifests from its in-memory state on quit, so writes made while the "
                "app is running are lost. This tool refuses to write when the app is "
                "running unless auto_quit_app=True is passed. Call streamdeck_restart_app "
                "once your edits are complete to make the changes visible on the device."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_name": {"type": "string"},
                    "profile_id": {"type": "string"},
                    "page_index": {
                        **_scalar_or_string("integer"),
                        "description": "Zero-based page index. Accepts int or string form.",
                    },
                    "directory_id": {"type": "string"},
                    "page_name": {
                        "type": "string",
                        "description": "Optional page name stored in the page manifest.",
                    },
                    "buttons": {
                        "description": (
                            "Buttons to write. Use streamdeck_create_action to "
                            "build Open or script-backed actions. Accepts a JSON "
                            "array or a JSON-encoded string — some MCP clients "
                            "stringify nested arrays in transit."
                        ),
                        "oneOf": [
                            {"type": "array", "items": button_schema},
                            {"type": "string"},
                        ],
                    },
                    "clear_existing": {
                        **_scalar_or_string("boolean"),
                        "description": (
                            "If true, replace the page contents with the "
                            "provided buttons. Defaults to true. Accepts bool "
                            "or string form."
                        ),
                    },
                    "create_new": {
                        **_scalar_or_string("boolean"),
                        "description": "Create a new page instead of updating an existing one.",
                    },
                    "make_current": {
                        **_scalar_or_string("boolean"),
                        "description": (
                            "When true, make the page the active current page after writing."
                        ),
                    },
                    "auto_quit_app": {
                        **_scalar_or_string("boolean"),
                        "description": (
                            "If true and the Elgato Stream Deck desktop app is "
                            "running, quit it (graceful AppleScript first, then "
                            "killall) before writing. Required when the app is "
                            "running or the write will raise an error. Defaults "
                            "to false so callers must explicitly consent to quitting it."
                        ),
                    },
                },
            },
        ),
        Tool(
            name="streamdeck_create_icon",
            description=(
                "Generate one or many 72x72 PNG icons. For a single icon: pass "
                "'icon' (a Material Design Icons name like 'mdi:cpu-64-bit') OR "
                "'text' (mutually exclusive with 'icon' — titles go on "
                "streamdeck_write_page's 'title' field since Elgato overlays them "
                "on images). For a full deck (often 30+ icons): pass 'icons' as a "
                "list of spec dicts to generate them all in one call and avoid the "
                "round-trip timeouts serial calls hit. ~7400 MDI icons bundled "
                "offline; unknown names return close-match suggestions. Returns "
                "either a single {path, size, ...} dict or {\"icons\": [...]} when "
                "'icons' is used (each list element is a per-icon result or an "
                "{\"error\"} entry for that spec)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "icon": {
                        "type": "string",
                        "description": (
                            "Material Design Icons name, e.g. 'mdi:cpu-64-bit', "
                            "'mdi:volume-high', 'mdi:microphone'. The 'mdi:' prefix is "
                            "optional. Aliases are honored."
                        ),
                    },
                    "icon_color": {
                        "type": "string",
                        "description": (
                            "Hex color for the icon glyph, e.g. '#00ff88'. "
                            "Defaults to text_color."
                        ),
                    },
                    "icon_scale": {
                        **_scalar_or_string("number"),
                        "description": (
                            "Fraction of the canvas the glyph bounding box fills "
                            "(0.1-1.0). Defaults to 1.0 — edge-to-edge, matching how "
                            "Elgato's own icons fill the touchstrip slot. Reduce to "
                            "~0.75-0.85 for keypad buttons that also have a bottom "
                            "title so the glyph doesn't touch the label."
                        ),
                    },
                    "shape": {
                        "type": "string",
                        "enum": ["button", "touchstrip"],
                        "description": (
                            "Output canvas. 'button' (default) is 72x72 — keypad keys "
                            "and encoder dial faces. 'touchstrip' is 200x100 — per-segment "
                            "background above a Stream Deck + / + XL dial; pair with a "
                            "button's strip_background_path on streamdeck_write_page."
                        ),
                    },
                    "transparent_bg": {
                        **_scalar_or_string("boolean"),
                        "description": (
                            "Generate an RGBA PNG with a transparent canvas instead of "
                            "filling with bg_color. Use this for dial Icons that overlay a "
                            "touchstrip background so the glyph composes naturally. Leave "
                            "false (default) for keypad faces and touchstrip backgrounds."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Text for a centered text-only icon. Mutually exclusive "
                            "with 'icon'. For icon buttons that need a label, use "
                            "the button's 'title' field on streamdeck_write_page."
                        ),
                    },
                    "bg_color": {"type": "string"},
                    "text_color": {"type": "string"},
                    "font_size": _scalar_or_string("integer"),
                    "filename": {"type": "string"},
                    "icons": {
                        "description": (
                            "Batch generation: a list of icon spec objects, each "
                            "carrying the same fields as a single-icon call "
                            "(icon/text/icon_color/bg_color/icon_scale/shape/"
                            "transparent_bg/text_color/font_size/filename). When "
                            "this field is present, all other single-icon fields "
                            "at the top level are ignored and the response shape "
                            "becomes {\"icons\": [per-spec result]}. Use this for "
                            "30+ icon decks to avoid per-call round-trip cost. "
                            "Accepts either a JSON array or a JSON-encoded string "
                            "containing an array — some MCP clients stringify "
                            "nested arrays in transit."
                        ),
                        "oneOf": [
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "icon": {"type": "string"},
                                        "text": {"type": "string"},
                                        "icon_color": {"type": "string"},
                                        "icon_scale": {"type": "number"},
                                        "bg_color": {"type": "string"},
                                        "text_color": {"type": "string"},
                                        "font_size": {"type": "integer"},
                                        "filename": {"type": "string"},
                                        "shape": {
                                            "type": "string",
                                            "enum": ["button", "touchstrip"],
                                        },
                                        "transparent_bg": {"type": "boolean"},
                                    },
                                },
                            },
                            {"type": "string"},
                        ],
                    },
                },
            },
        ),
        Tool(
            name="streamdeck_create_action",
            description=(
                "Create an executable shell script in ~/StreamDeckScripts "
                "and return a native Open action block for it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Human-readable action name used for the "
                            "script filename and button label."
                        ),
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to run when the button is pressed.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": (
                            "Optional working directory to cd into before executing the command."
                        ),
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional override for the script filename.",
                    },
                },
                "required": ["name", "command"],
            },
        ),
        Tool(
            name="streamdeck_restart_app",
            description="Restart the macOS Stream Deck desktop app after profile changes.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="streamdeck_install_mcp_plugin",
            description=(
                "Install the bundled streamdeck-mcp Stream Deck plugin into the user's "
                "Elgato Plugins directory. The plugin is a minimal shell that declares "
                "encoder support so that per-instance touchstrip icons and backgrounds "
                "written by streamdeck_write_page survive an Elgato app restart. Idempotent "
                "— returns installed=false when already present unless force=true. "
                "streamdeck_write_page also auto-installs this plugin when an encoder "
                "button targets it, so most callers do not need to invoke this directly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        **_scalar_or_string("boolean"),
                        "description": (
                            "Reinstall the plugin even if it already exists. Useful after "
                            "upgrading streamdeck-mcp."
                        ),
                    }
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle profile writer tool calls."""

    # Normalize stringified args from MCP clients that serialize non-string
    # tool-call parameters as JSON strings in transit. Schemas declare
    # oneOf [native, string] so validation passes either shape; this brings
    # the values back to the types the handlers expect.
    arguments = _coerce_arguments(
        arguments,
        ints=("page_index", "font_size", "state", "key"),
        nums=("icon_scale",),
        bools=(
            "clear_existing",
            "create_new",
            "make_current",
            "auto_quit_app",
            "transparent_bg",
            "force",
            "show_title",
        ),
        arrays=("buttons", "icons"),
    )

    try:
        if name == "streamdeck_read_profiles":
            profiles = manager.list_profiles()
            return [TextContent(type="text", text=json.dumps(profiles, indent=2))]

        if name == "streamdeck_read_page":
            payload = manager.read_page(
                profile_name=arguments.get("profile_name"),
                profile_id=arguments.get("profile_id"),
                page_index=arguments.get("page_index"),
                directory_id=arguments.get("directory_id"),
            )
            return [TextContent(type="text", text=json.dumps(payload, indent=2))]

        if name == "streamdeck_write_page":
            # If coercion couldn't parse a stringified `buttons` array,
            # surface a clear error here instead of letting the downstream
            # handler iterate the string one char at a time.
            raw_buttons = arguments.get("buttons")
            if isinstance(raw_buttons, str):
                return [
                    TextContent(
                        type="text",
                        text=(
                            "❌ 'buttons' was a string but not a valid JSON "
                            "array. Pass either a JSON array or a JSON-encoded "
                            "string of an array."
                        ),
                    )
                ]
            result = manager.write_page(
                profile_name=arguments.get("profile_name"),
                profile_id=arguments.get("profile_id"),
                page_index=arguments.get("page_index"),
                directory_id=arguments.get("directory_id"),
                page_name=arguments.get("page_name"),
                buttons=arguments.get("buttons"),
                clear_existing=arguments.get("clear_existing", True),
                create_new=arguments.get("create_new", False),
                make_current=arguments.get("make_current", False),
                auto_quit_app=arguments.get("auto_quit_app", False),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "streamdeck_create_icon":
            batch = arguments.get("icons")
            if isinstance(batch, str):
                # Some MCP clients stringify nested arrays in transit
                # (observed with Claude Code's tool-call serialization).
                # Parse on the server so callers can pass either shape.
                try:
                    batch = json.loads(batch)
                except json.JSONDecodeError as exc:
                    return [
                        TextContent(
                            type="text",
                            text=(
                                "❌ 'icons' was a string but not valid JSON: "
                                f"{exc}. Pass either a JSON array or a "
                                "JSON-encoded string."
                            ),
                        )
                    ]
            if batch is not None:
                icons_result = manager.create_icons(batch)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"icons": icons_result}, indent=2),
                    )
                ]
            _scale = arguments.get("icon_scale")
            result = manager.create_icon(
                text=arguments.get("text"),
                icon=arguments.get("icon"),
                icon_color=arguments.get("icon_color"),
                icon_scale=1.0 if _scale is None else _scale,
                bg_color=arguments.get("bg_color", "#000000"),
                text_color=arguments.get("text_color", "#ffffff"),
                font_size=arguments.get("font_size", 18),
                filename=arguments.get("filename"),
                shape=arguments.get("shape", "button"),
                transparent_bg=bool(arguments.get("transparent_bg", False)),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "streamdeck_install_mcp_plugin":
            result = manager.install_mcp_plugin(force=bool(arguments.get("force", False)))
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "streamdeck_create_action":
            result = manager.create_action(
                name=arguments["name"],
                command=arguments["command"],
                working_directory=arguments.get("working_directory"),
                filename=arguments.get("filename"),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "streamdeck_restart_app":
            result = manager.restart_app()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]

    except StreamDeckAppRunningError as exc:
        return [TextContent(type="text", text=f"⚠️ {exc}")]
    except (
        ProfileManagerError,
        ProfileNotFoundError,
        PageNotFoundError,
        ProfileValidationError,
    ) as exc:
        return [TextContent(type="text", text=f"❌ {exc}")]
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error in %s", name)
        return [TextContent(type="text", text=f"❌ Unexpected error: {exc}")]


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List MCP prompts. The design_streamdeck_deck prompt mirrors the bundled
    streamdeck-designer skill for MCP clients that don't load Claude Code skills
    (Claude Desktop, Cursor, ChatGPT-with-MCP, etc.).
    """

    return [
        Prompt(
            name="design_streamdeck_deck",
            description=(
                "Prime Claude with the streamdeck-designer authoring vocabulary: "
                "hardware inventory, palette/typography planning, integration discovery, "
                "icon generation, dial layouts, and guardrails. Invoke before authoring "
                "a themed or integrated Stream Deck layout — especially on clients that "
                "don't auto-load the bundled Claude Code skill. Optional 'intent' arg "
                "appends the user's specific ask."
            ),
            arguments=[
                PromptArgument(
                    name="intent",
                    description=(
                        "Optional one-line description of what the user wants "
                        "(e.g. 'hello-kitty Twitch deck with Hue light controls')."
                    ),
                    required=False,
                ),
            ],
        ),
    ]


def _load_skill_body() -> str:
    """Return the streamdeck-designer SKILL.md body (frontmatter stripped)."""

    try:
        raw = _SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "# Stream Deck Designer\n\n"
            "The bundled streamdeck-designer skill was not found at "
            f"{_SKILL_PATH}. Reinstall streamdeck-mcp or check package data.\n"
        )

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return raw


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Return the design_streamdeck_deck priming message."""

    if name != "design_streamdeck_deck":
        raise ValueError(f"Unknown prompt: {name}")

    body = _load_skill_body()
    intent = (arguments or {}).get("intent")

    message_text = body
    if intent:
        message_text = (
            f"{body}\n\n---\n\n"
            f"User intent for this authoring session: {intent}\n\n"
            "Apply the guidance above. Start by calling streamdeck_read_profiles."
        )

    return GetPromptResult(
        description="Stream Deck authoring vocabulary + the user's intent.",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=message_text),
            ),
        ],
    )


async def main() -> None:
    """Run the profile writer MCP server."""

    logger.info("Starting Stream Deck Profile Writer MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Synchronous wrapper for package entrypoints."""

    asyncio.run(main())


if __name__ == "__main__":
    run()
