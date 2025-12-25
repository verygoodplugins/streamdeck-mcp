#!/usr/bin/env python3
"""
Stream Deck MCP Server
Control your Elgato Stream Deck via MCP — set buttons, manage pages, trigger actions.

https://github.com/verygoodplugins/streamdeck-mcp
"""

import asyncio
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("streamdeck-mcp")

# Optional: Pillow for image generation
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    logger.warning("Pillow not installed — button images will not render. Run: pip install pillow")

# Stream Deck library
try:
    from StreamDeck.DeviceManager import DeviceManager
    from StreamDeck.ImageHelpers import PILHelper
    HAS_STREAMDECK = True
except ImportError:
    HAS_STREAMDECK = False
    logger.warning("streamdeck library not installed. Run: pip install streamdeck")


# ============================================================================
# Configuration
# ============================================================================

CONFIG_DIR = Path.home() / ".streamdeck-mcp"
PAGES_FILE = CONFIG_DIR / "pages.json"
BUTTONS_FILE = CONFIG_DIR / "buttons.json"

# Default button colors
DEFAULT_BG_COLOR: tuple[int, int, int] = (0, 0, 0)  # Black
DEFAULT_TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)  # White

# Validation constants
MAX_PAGE_NAME_LENGTH = 50
PAGE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\s]+$")

# Reconnection settings
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_BASE = 1.0  # seconds


# ============================================================================
# Exceptions
# ============================================================================

class StreamDeckError(Exception):
    """Base exception for Stream Deck operations."""
    pass


class DeckNotConnectedError(StreamDeckError):
    """Raised when deck is not connected."""
    pass


class DeckDisconnectedError(StreamDeckError):
    """Raised when deck becomes disconnected during operation."""
    pass


class ValidationError(StreamDeckError):
    """Raised when input validation fails."""
    pass


# ============================================================================
# State Management
# ============================================================================

class StreamDeckState:
    """
    Manages Stream Deck connection, state, and page configurations.

    Handles:
    - USB connection/disconnection with automatic reconnection
    - Button appearance and action configuration
    - Page management (create, switch, delete)
    - State persistence to disk

    Example:
        state = StreamDeckState()
        state.connect()
        state.set_button_image(0, text="Hello", bg_color=(0, 0, 255))
    """

    def __init__(self) -> None:
        self.deck: Any = None
        self.current_page: str = "main"
        self.pages: dict[str, dict[str, Any]] = {"main": {}}
        self.button_callbacks: dict[str, dict[str, Any]] = {}
        self._brightness: int = 70
        self._last_connect_attempt: float = 0
        self._connect_attempts: int = 0
        self._ensure_config_dir()
        self._load_state()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create config directory: {e}")

    def _load_state(self) -> None:
        """Load saved pages and button configs from disk."""
        if PAGES_FILE.exists():
            try:
                data = json.loads(PAGES_FILE.read_text())
                if isinstance(data, dict) and "main" in data:
                    self.pages = data
                    logger.info(f"Loaded {len(self.pages)} pages from disk")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load pages: {e}")
                self.pages = {"main": {}}

        if BUTTONS_FILE.exists():
            try:
                data = json.loads(BUTTONS_FILE.read_text())
                if isinstance(data, dict):
                    self.button_callbacks = data
                    logger.info(f"Loaded button configs for {len(self.button_callbacks)} pages")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load button callbacks: {e}")
                self.button_callbacks = {}

    def _save_state(self) -> None:
        """Persist current state to disk."""
        try:
            PAGES_FILE.write_text(json.dumps(self.pages, indent=2))
            BUTTONS_FILE.write_text(json.dumps(self.button_callbacks, indent=2))
        except OSError as e:
            logger.error(f"Failed to save state: {e}")

    def _validate_key(self, key: int) -> None:
        """
        Validate button key index.

        Args:
            key: Button index (0-based)

        Raises:
            ValidationError: If key is out of range
        """
        if not isinstance(key, int) or key < 0:
            raise ValidationError(f"Key must be a non-negative integer, got: {key}")

        if self.deck:
            max_keys = self.deck.key_count()
            if key >= max_keys:
                raise ValidationError(f"Key {key} out of range. This deck has {max_keys} keys (0-{max_keys - 1})")

    def _validate_page_name(self, name: str) -> None:
        """
        Validate page name.

        Args:
            name: Page name to validate

        Raises:
            ValidationError: If name is invalid
        """
        if not name or not isinstance(name, str):
            raise ValidationError("Page name cannot be empty")

        if len(name) > MAX_PAGE_NAME_LENGTH:
            raise ValidationError(f"Page name too long (max {MAX_PAGE_NAME_LENGTH} characters)")

        if not PAGE_NAME_PATTERN.match(name):
            raise ValidationError("Page name can only contain letters, numbers, underscores, hyphens, and spaces")

    def _validate_color(self, color: tuple[int, ...], name: str = "color") -> tuple[int, int, int]:
        """
        Validate and normalize RGB color tuple.

        Args:
            color: RGB color tuple
            name: Name of the color parameter (for error messages)

        Returns:
            Validated RGB tuple

        Raises:
            ValidationError: If color is invalid
        """
        if not isinstance(color, (tuple, list)) or len(color) != 3:
            raise ValidationError(f"{name} must be [R, G, B] with 3 values")

        validated = []
        for i, component in enumerate(color):
            if not isinstance(component, (int, float)):
                raise ValidationError(f"{name} component {i} must be a number")
            val = int(component)
            if val < 0 or val > 255:
                raise ValidationError(f"{name} values must be 0-255, got {val}")
            validated.append(val)

        return (validated[0], validated[1], validated[2])

    def _check_deck_connected(self) -> None:
        """
        Verify deck is connected and responsive.

        Raises:
            DeckNotConnectedError: If deck is not connected
            DeckDisconnectedError: If deck became disconnected
        """
        if not self.deck:
            raise DeckNotConnectedError("No Stream Deck connected. Use streamdeck_connect first.")

        try:
            # Quick health check — try to read key count
            self.deck.key_count()
        except Exception as e:
            logger.error(f"Deck became unresponsive: {e}")
            self.deck = None
            raise DeckDisconnectedError("Stream Deck disconnected. Reconnect with streamdeck_connect.")

    def connect(self) -> dict[str, Any]:
        """
        Connect to the first available Stream Deck.

        Returns:
            Dict with connection result and deck info

        Raises:
            StreamDeckError: If connection fails
        """
        if not HAS_STREAMDECK:
            raise StreamDeckError(
                "streamdeck library not installed. Run: pip install streamdeck pillow"
            )

        # Rate limit reconnection attempts
        now = time.time()
        if now - self._last_connect_attempt < RECONNECT_DELAY_BASE:
            time.sleep(RECONNECT_DELAY_BASE)
        self._last_connect_attempt = now

        try:
            decks = DeviceManager().enumerate()
        except Exception as e:
            logger.error(f"Failed to enumerate devices: {e}")
            raise StreamDeckError(f"Failed to scan for Stream Deck devices: {e}")

        if not decks:
            raise StreamDeckError(
                "No Stream Deck found. Check USB connection and permissions."
            )

        try:
            self.deck = decks[0]
            self.deck.open()
            self.deck.reset()
            self.deck.set_brightness(self._brightness)
            self.deck.set_key_callback(self._key_callback)

            self._connect_attempts = 0
            logger.info(f"Connected to {self.deck.deck_type()} (serial: {self.deck.get_serial_number()})")

            # Render current page after connecting
            self._render_current_page()

            return self.get_deck_info()

        except Exception as e:
            self._connect_attempts += 1
            logger.error(f"Connection attempt {self._connect_attempts} failed: {e}")
            self.deck = None

            if self._connect_attempts >= MAX_RECONNECT_ATTEMPTS:
                raise StreamDeckError(
                    f"Failed to connect after {MAX_RECONNECT_ATTEMPTS} attempts. "
                    "Check USB connection and permissions."
                )

            raise StreamDeckError(f"Failed to open Stream Deck: {e}")

    def _key_callback(self, deck: Any, key: int, state: bool) -> None:
        """
        Handle physical button presses.

        Args:
            deck: The deck that triggered the callback
            key: Button index
            state: True for press, False for release
        """
        if not state:  # Only handle key down
            return

        logger.debug(f"Button {key} pressed on page '{self.current_page}'")

        page_buttons = self.button_callbacks.get(self.current_page, {})
        button_config = page_buttons.get(str(key), {})

        if "action" not in button_config:
            return

        action = button_config["action"]
        action_type = button_config.get("type", "command")

        try:
            if action.startswith("page:"):
                # Page switch action
                new_page = action.split(":", 1)[1]
                self.switch_page(new_page)
                logger.info(f"Switched to page '{new_page}'")
            elif action_type == "command":
                # Shell command execution
                logger.info(f"Executing command: {action}")
                subprocess.Popen(
                    action,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            logger.error(f"Action failed for button {key}: {e}")

    def get_deck_info(self) -> dict[str, Any]:
        """
        Get information about the connected deck.

        Returns:
            Dict with deck info or connection status
        """
        if not self.deck:
            return {"connected": False}

        try:
            layout = self.deck.key_layout()
            return {
                "connected": True,
                "id": self.deck.id(),
                "type": self.deck.deck_type(),
                "serial": self.deck.get_serial_number(),
                "firmware": self.deck.get_firmware_version(),
                "key_count": self.deck.key_count(),
                "columns": layout[0],
                "rows": layout[1],
                "key_format": {
                    "size": self.deck.key_image_format()["size"],
                    "format": self.deck.key_image_format()["format"],
                },
                "current_page": self.current_page,
                "brightness": self._brightness,
            }
        except Exception as e:
            logger.error(f"Failed to get deck info: {e}")
            self.deck = None
            return {"connected": False, "error": str(e)}

    def set_button_image(
        self,
        key: int,
        image_path: Optional[str] = None,
        text: Optional[str] = None,
        bg_color: tuple[int, int, int] = DEFAULT_BG_COLOR,
        text_color: tuple[int, int, int] = DEFAULT_TEXT_COLOR,
    ) -> bool:
        """
        Set a button's image — either from file or generated with text.

        Args:
            key: Button index (0-based)
            image_path: Path to image file (PNG/JPG)
            text: Text label to display
            bg_color: Background RGB color
            text_color: Text RGB color

        Returns:
            True if successful

        Raises:
            ValidationError: If inputs are invalid
            DeckNotConnectedError: If deck is not connected
        """
        self._check_deck_connected()
        self._validate_key(key)
        bg_color = self._validate_color(bg_color, "bg_color")
        text_color = self._validate_color(text_color, "text_color")

        if not HAS_PILLOW:
            raise StreamDeckError("Pillow not installed. Run: pip install pillow")

        try:
            key_format = self.deck.key_image_format()
            key_size = key_format["size"]

            if image_path and Path(image_path).expanduser().exists():
                # Load image from file
                img_path = Path(image_path).expanduser()
                img = Image.open(img_path)
                img = PILHelper.create_scaled_image(self.deck, img)
                logger.debug(f"Loaded image from {img_path}")
            else:
                # Generate image with text/color
                img = Image.new("RGB", key_size, bg_color)

                if text:
                    draw = ImageDraw.Draw(img)
                    font = self._get_font(14)

                    # Center text
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    x = (key_size[0] - text_width) // 2
                    y = (key_size[1] - text_height) // 2
                    draw.text((x, y), text, font=font, fill=text_color)

            # Convert and set
            image = PILHelper.to_native_format(self.deck, img)
            self.deck.set_key_image(key, image)

            # Save to current page state
            if self.current_page not in self.pages:
                self.pages[self.current_page] = {}

            self.pages[self.current_page][str(key)] = {
                "text": text,
                "image_path": image_path,
                "bg_color": list(bg_color),
                "text_color": list(text_color),
            }
            self._save_state()

            logger.debug(f"Set button {key}: text='{text}', bg={bg_color}")
            return True

        except Exception as e:
            logger.error(f"Failed to set button {key}: {e}")
            raise StreamDeckError(f"Failed to set button {key}: {e}")

    def _get_font(self, size: int) -> Any:
        """
        Get a font for button text rendering.

        Args:
            size: Font size in points

        Returns:
            PIL ImageFont object
        """
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "/System/Library/Fonts/SFNSText.ttf",   # macOS newer
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
            "C:/Windows/Fonts/arial.ttf",  # Windows
        ]

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue

        logger.debug("Using default PIL font")
        return ImageFont.load_default()

    def set_button_action(self, key: int, action: str, action_type: str = "command") -> bool:
        """
        Set what happens when a button is pressed.

        Args:
            key: Button index
            action: Action string. Use 'page:name' for page switch, or shell command.
            action_type: Type of action ('command' or 'page')

        Returns:
            True if successful
        """
        self._validate_key(key)

        if not action or not isinstance(action, str):
            raise ValidationError("Action cannot be empty")

        if self.current_page not in self.button_callbacks:
            self.button_callbacks[self.current_page] = {}

        self.button_callbacks[self.current_page][str(key)] = {
            "action": action,
            "type": action_type,
        }
        self._save_state()

        logger.debug(f"Set action for button {key}: {action}")
        return True

    def create_page(self, name: str) -> bool:
        """
        Create a new page.

        Args:
            name: Page name

        Returns:
            True if created, False if already exists
        """
        self._validate_page_name(name)

        if name in self.pages:
            return False

        self.pages[name] = {}
        self._save_state()
        logger.info(f"Created page '{name}'")
        return True

    def switch_page(self, name: str) -> bool:
        """
        Switch to a different page and render its buttons.

        Args:
            name: Page name to switch to

        Returns:
            True if successful
        """
        if name not in self.pages:
            raise ValidationError(f"Page '{name}' does not exist")

        self.current_page = name
        self._render_current_page()
        logger.info(f"Switched to page '{name}'")
        return True

    def _render_current_page(self) -> None:
        """Render all buttons for current page."""
        if not self.deck:
            return

        try:
            # Clear all buttons first
            for key in range(self.deck.key_count()):
                self.deck.set_key_image(key, None)

            # Render saved buttons
            page_config = self.pages.get(self.current_page, {})
            for key_str, config in page_config.items():
                try:
                    key = int(key_str)
                    self.set_button_image(
                        key,
                        image_path=config.get("image_path"),
                        text=config.get("text"),
                        bg_color=tuple(config.get("bg_color", DEFAULT_BG_COLOR)),
                        text_color=tuple(config.get("text_color", DEFAULT_TEXT_COLOR)),
                    )
                except (ValueError, ValidationError) as e:
                    logger.warning(f"Skipping invalid button config: {e}")
        except Exception as e:
            logger.error(f"Failed to render page '{self.current_page}': {e}")

    def set_brightness(self, percent: int) -> bool:
        """
        Set deck brightness (0-100).

        Args:
            percent: Brightness level 0-100

        Returns:
            True if successful
        """
        self._check_deck_connected()

        if not isinstance(percent, (int, float)):
            raise ValidationError("Brightness must be a number")

        percent = max(0, min(100, int(percent)))

        try:
            self.deck.set_brightness(percent)
            self._brightness = percent
            logger.debug(f"Set brightness to {percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            raise StreamDeckError(f"Failed to set brightness: {e}")

    def list_pages(self) -> list[str]:
        """
        List all available pages.

        Returns:
            List of page names
        """
        return list(self.pages.keys())

    def delete_page(self, name: str) -> bool:
        """
        Delete a page (cannot delete 'main').

        Args:
            name: Page name to delete

        Returns:
            True if deleted
        """
        if name == "main":
            raise ValidationError("Cannot delete the 'main' page")

        if name not in self.pages:
            raise ValidationError(f"Page '{name}' does not exist")

        del self.pages[name]
        if name in self.button_callbacks:
            del self.button_callbacks[name]

        if self.current_page == name:
            self.switch_page("main")

        self._save_state()
        logger.info(f"Deleted page '{name}'")
        return True

    def clear_button(self, key: int) -> bool:
        """
        Clear a single button.

        Args:
            key: Button index to clear

        Returns:
            True if successful
        """
        self._check_deck_connected()
        self._validate_key(key)

        try:
            self.deck.set_key_image(key, None)

            if str(key) in self.pages.get(self.current_page, {}):
                del self.pages[self.current_page][str(key)]

            if str(key) in self.button_callbacks.get(self.current_page, {}):
                del self.button_callbacks[self.current_page][str(key)]

            self._save_state()
            logger.debug(f"Cleared button {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear button {key}: {e}")
            raise StreamDeckError(f"Failed to clear button {key}: {e}")

    def disconnect(self) -> None:
        """Clean up deck connection."""
        if self.deck:
            try:
                self.deck.reset()
                self.deck.close()
                logger.info("Disconnected from Stream Deck")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.deck = None


# ============================================================================
# MCP Server
# ============================================================================

state = StreamDeckState()
server = Server("streamdeck-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Stream Deck tools."""
    return [
        Tool(
            name="streamdeck_connect",
            description="Connect to a Stream Deck device. Call this first before other operations.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="streamdeck_info",
            description="Get info about the connected Stream Deck (model, key count, current page, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="streamdeck_set_button",
            description="Set a button's appearance and optional action. Use text for labels or image_path for icons.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "integer",
                        "description": "Button index (0-based, left-to-right, top-to-bottom)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text label to display on button",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to image file (PNG/JPG) to display",
                    },
                    "bg_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Background RGB color [r, g, b] (0-255 each)",
                    },
                    "text_color": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Text RGB color [r, g, b] (0-255 each)",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action when pressed. Use 'page:name' to switch pages, or a shell command.",
                    },
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="streamdeck_clear_button",
            description="Clear a button (remove image and text)",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "integer",
                        "description": "Button index to clear",
                    },
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="streamdeck_set_brightness",
            description="Set the Stream Deck screen brightness",
            inputSchema={
                "type": "object",
                "properties": {
                    "percent": {
                        "type": "integer",
                        "description": "Brightness level 0-100",
                    },
                },
                "required": ["percent"],
            },
        ),
        Tool(
            name="streamdeck_create_page",
            description="Create a new button page/profile",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the new page",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="streamdeck_switch_page",
            description="Switch to a different button page",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of page to switch to",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="streamdeck_list_pages",
            description="List all available pages",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="streamdeck_delete_page",
            description="Delete a page (cannot delete 'main')",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of page to delete",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="streamdeck_disconnect",
            description="Disconnect from Stream Deck and reset it",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with proper error handling."""

    try:
        if name == "streamdeck_connect":
            if not HAS_STREAMDECK:
                return [TextContent(
                    type="text",
                    text="❌ streamdeck library not installed. Run: pip install streamdeck pillow"
                )]

            info = state.connect()
            return [TextContent(
                type="text",
                text=f"✅ Connected to {info['type']}\n"
                     f"   Serial: {info['serial']}\n"
                     f"   Keys: {info['key_count']} ({info['columns']}x{info['rows']})\n"
                     f"   Firmware: {info['firmware']}"
            )]

        elif name == "streamdeck_info":
            info = state.get_deck_info()
            return [TextContent(type="text", text=json.dumps(info, indent=2))]

        elif name == "streamdeck_set_button":
            key = arguments["key"]
            text = arguments.get("text")
            image_path = arguments.get("image_path")
            bg_color = tuple(arguments.get("bg_color", DEFAULT_BG_COLOR))
            text_color = tuple(arguments.get("text_color", DEFAULT_TEXT_COLOR))
            action = arguments.get("action")

            state.set_button_image(key, image_path, text, bg_color, text_color)

            if action:
                state.set_button_action(key, action)

            return [TextContent(type="text", text=f"✅ Button {key} configured")]

        elif name == "streamdeck_clear_button":
            key = arguments["key"]
            state.clear_button(key)
            return [TextContent(type="text", text=f"✅ Button {key} cleared")]

        elif name == "streamdeck_set_brightness":
            percent = arguments["percent"]
            state.set_brightness(percent)
            return [TextContent(type="text", text=f"✅ Brightness set to {percent}%")]

        elif name == "streamdeck_create_page":
            name_arg = arguments["name"]
            success = state.create_page(name_arg)
            if success:
                return [TextContent(type="text", text=f"✅ Page '{name_arg}' created")]
            else:
                return [TextContent(type="text", text=f"⚠️ Page '{name_arg}' already exists")]

        elif name == "streamdeck_switch_page":
            name_arg = arguments["name"]
            state.switch_page(name_arg)
            return [TextContent(type="text", text=f"✅ Switched to page '{name_arg}'")]

        elif name == "streamdeck_list_pages":
            pages = state.list_pages()
            current = state.current_page
            lines = [f"{'→ ' if p == current else '  '}{p}" for p in pages]
            return [TextContent(type="text", text="Pages:\n" + "\n".join(lines))]

        elif name == "streamdeck_delete_page":
            name_arg = arguments["name"]
            state.delete_page(name_arg)
            return [TextContent(type="text", text=f"✅ Page '{name_arg}' deleted")]

        elif name == "streamdeck_disconnect":
            state.disconnect()
            return [TextContent(type="text", text="✅ Disconnected from Stream Deck")]

        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]

    except ValidationError as e:
        return [TextContent(type="text", text=f"⚠️ {e}")]

    except DeckNotConnectedError as e:
        return [TextContent(type="text", text=f"❌ {e}")]

    except DeckDisconnectedError as e:
        return [TextContent(type="text", text=f"❌ {e}")]

    except StreamDeckError as e:
        return [TextContent(type="text", text=f"❌ {e}")]

    except Exception as e:
        logger.exception(f"Unexpected error in {name}")
        return [TextContent(type="text", text=f"❌ Unexpected error: {e}")]


async def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Stream Deck MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
