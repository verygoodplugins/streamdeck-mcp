#!/usr/bin/env python3
"""
Stream Deck MCP Server
Control your Elgato Stream Deck via MCP — set buttons, manage pages, trigger actions.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Optional: Pillow for image generation
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# Stream Deck library
try:
    from StreamDeck.DeviceManager import DeviceManager
    from StreamDeck.ImageHelpers import PILHelper
    HAS_STREAMDECK = True
except ImportError:
    HAS_STREAMDECK = False


# ============================================================================
# Configuration
# ============================================================================

CONFIG_DIR = Path.home() / ".streamdeck-mcp"
PAGES_FILE = CONFIG_DIR / "pages.json"
BUTTONS_FILE = CONFIG_DIR / "buttons.json"

# Default button colors
DEFAULT_BG_COLOR = (0, 0, 0)  # Black
DEFAULT_TEXT_COLOR = (255, 255, 255)  # White


# ============================================================================
# State Management
# ============================================================================

class StreamDeckState:
    """Manages Stream Deck state and page configurations."""
    
    def __init__(self):
        self.deck = None
        self.current_page = "main"
        self.pages: dict = {"main": {}}
        self.button_callbacks: dict = {}
        self._ensure_config_dir()
        self._load_state()
    
    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self):
        """Load saved pages and button configs."""
        if PAGES_FILE.exists():
            try:
                self.pages = json.loads(PAGES_FILE.read_text())
            except json.JSONDecodeError:
                self.pages = {"main": {}}
        
        if BUTTONS_FILE.exists():
            try:
                self.button_callbacks = json.loads(BUTTONS_FILE.read_text())
            except json.JSONDecodeError:
                self.button_callbacks = {}
    
    def _save_state(self):
        """Persist current state to disk."""
        PAGES_FILE.write_text(json.dumps(self.pages, indent=2))
        BUTTONS_FILE.write_text(json.dumps(self.button_callbacks, indent=2))
    
    def connect(self) -> bool:
        """Connect to first available Stream Deck."""
        if not HAS_STREAMDECK:
            return False
        
        decks = DeviceManager().enumerate()
        if not decks:
            return False
        
        self.deck = decks[0]
        self.deck.open()
        self.deck.reset()
        self.deck.set_brightness(70)
        
        # Set up key callback
        self.deck.set_key_callback(self._key_callback)
        
        return True
    
    def _key_callback(self, deck, key, state):
        """Handle physical button presses."""
        if not state:  # Only on key down
            return
        
        # Check if button has a callback registered
        page_buttons = self.button_callbacks.get(self.current_page, {})
        button_config = page_buttons.get(str(key), {})
        
        if "action" in button_config:
            action = button_config["action"]
            # Actions could be: page switch, command execution, etc.
            if action.startswith("page:"):
                new_page = action.split(":", 1)[1]
                self.switch_page(new_page)
    
    def get_deck_info(self) -> dict:
        """Get info about connected deck."""
        if not self.deck:
            return {"connected": False}
        
        return {
            "connected": True,
            "id": self.deck.id(),
            "type": self.deck.deck_type(),
            "serial": self.deck.get_serial_number(),
            "firmware": self.deck.get_firmware_version(),
            "key_count": self.deck.key_count(),
            "columns": self.deck.key_layout()[0],
            "rows": self.deck.key_layout()[1],
            "key_format": {
                "size": self.deck.key_image_format()["size"],
                "format": self.deck.key_image_format()["format"],
            },
            "current_page": self.current_page,
            "brightness": 70,
        }
    
    def set_button_image(self, key: int, image_path: Optional[str] = None, 
                         text: Optional[str] = None, bg_color: tuple = DEFAULT_BG_COLOR,
                         text_color: tuple = DEFAULT_TEXT_COLOR) -> bool:
        """Set a button's image — either from file or generated with text."""
        if not self.deck or not HAS_PILLOW:
            return False
        
        key_format = self.deck.key_image_format()
        key_size = key_format["size"]
        
        if image_path and Path(image_path).exists():
            # Load image from file
            img = Image.open(image_path)
            img = PILHelper.create_scaled_image(self.deck, img)
        else:
            # Generate image with text
            img = Image.new("RGB", key_size, bg_color)
            
            if text:
                draw = ImageDraw.Draw(img)
                # Try to load a nice font, fall back to default
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
                except:
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                    except:
                        font = ImageFont.load_default()
                
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
        
        return True
    
    def set_button_action(self, key: int, action: str, action_type: str = "command") -> bool:
        """Set what happens when a button is pressed."""
        if self.current_page not in self.button_callbacks:
            self.button_callbacks[self.current_page] = {}
        
        self.button_callbacks[self.current_page][str(key)] = {
            "action": action,
            "type": action_type,
        }
        self._save_state()
        return True
    
    def create_page(self, name: str) -> bool:
        """Create a new page."""
        if name in self.pages:
            return False
        self.pages[name] = {}
        self._save_state()
        return True
    
    def switch_page(self, name: str) -> bool:
        """Switch to a different page and render its buttons."""
        if name not in self.pages:
            return False
        
        self.current_page = name
        self._render_current_page()
        return True
    
    def _render_current_page(self):
        """Render all buttons for current page."""
        if not self.deck:
            return
        
        # Clear all buttons first
        for key in range(self.deck.key_count()):
            self.deck.set_key_image(key, None)
        
        # Render saved buttons
        page_config = self.pages.get(self.current_page, {})
        for key_str, config in page_config.items():
            key = int(key_str)
            self.set_button_image(
                key,
                image_path=config.get("image_path"),
                text=config.get("text"),
                bg_color=tuple(config.get("bg_color", DEFAULT_BG_COLOR)),
                text_color=tuple(config.get("text_color", DEFAULT_TEXT_COLOR)),
            )
    
    def set_brightness(self, percent: int) -> bool:
        """Set deck brightness (0-100)."""
        if not self.deck:
            return False
        self.deck.set_brightness(max(0, min(100, percent)))
        return True
    
    def list_pages(self) -> list:
        """List all available pages."""
        return list(self.pages.keys())
    
    def delete_page(self, name: str) -> bool:
        """Delete a page (can't delete 'main')."""
        if name == "main" or name not in self.pages:
            return False
        del self.pages[name]
        if name in self.button_callbacks:
            del self.button_callbacks[name]
        if self.current_page == name:
            self.switch_page("main")
        self._save_state()
        return True
    
    def clear_button(self, key: int) -> bool:
        """Clear a single button."""
        if not self.deck:
            return False
        self.deck.set_key_image(key, None)
        if str(key) in self.pages.get(self.current_page, {}):
            del self.pages[self.current_page][str(key)]
        self._save_state()
        return True
    
    def disconnect(self):
        """Clean up deck connection."""
        if self.deck:
            self.deck.reset()
            self.deck.close()
            self.deck = None


# ============================================================================
# MCP Server
# ============================================================================

state = StreamDeckState()
server = Server("streamdeck-mcp")


@server.list_tools()
async def list_tools():
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
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    
    if name == "streamdeck_connect":
        if not HAS_STREAMDECK:
            return [TextContent(
                type="text",
                text="❌ streamdeck library not installed. Run: pip install streamdeck pillow"
            )]
        
        success = state.connect()
        if success:
            info = state.get_deck_info()
            return [TextContent(
                type="text",
                text=f"✅ Connected to {info['type']}\n"
                     f"   Serial: {info['serial']}\n"
                     f"   Keys: {info['key_count']} ({info['columns']}x{info['rows']})\n"
                     f"   Firmware: {info['firmware']}"
            )]
        else:
            return [TextContent(
                type="text",
                text="❌ No Stream Deck found. Make sure it's plugged in and you have USB permissions."
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
        
        success = state.set_button_image(key, image_path, text, bg_color, text_color)
        
        if action:
            state.set_button_action(key, action)
        
        if success:
            return [TextContent(type="text", text=f"✅ Button {key} configured")]
        else:
            return [TextContent(type="text", text=f"❌ Failed to set button {key}. Is deck connected?")]
    
    elif name == "streamdeck_clear_button":
        key = arguments["key"]
        success = state.clear_button(key)
        return [TextContent(
            type="text",
            text=f"✅ Button {key} cleared" if success else f"❌ Failed to clear button {key}"
        )]
    
    elif name == "streamdeck_set_brightness":
        percent = arguments["percent"]
        success = state.set_brightness(percent)
        return [TextContent(
            type="text",
            text=f"✅ Brightness set to {percent}%" if success else "❌ Failed to set brightness"
        )]
    
    elif name == "streamdeck_create_page":
        name_arg = arguments["name"]
        success = state.create_page(name_arg)
        return [TextContent(
            type="text",
            text=f"✅ Page '{name_arg}' created" if success else f"❌ Page '{name_arg}' already exists"
        )]
    
    elif name == "streamdeck_switch_page":
        name_arg = arguments["name"]
        success = state.switch_page(name_arg)
        return [TextContent(
            type="text",
            text=f"✅ Switched to page '{name_arg}'" if success else f"❌ Page '{name_arg}' not found"
        )]
    
    elif name == "streamdeck_list_pages":
        pages = state.list_pages()
        current = state.current_page
        lines = [f"{'→ ' if p == current else '  '}{p}" for p in pages]
        return [TextContent(type="text", text="Pages:\n" + "\n".join(lines))]
    
    elif name == "streamdeck_delete_page":
        name_arg = arguments["name"]
        success = state.delete_page(name_arg)
        return [TextContent(
            type="text",
            text=f"✅ Page '{name_arg}' deleted" if success else f"❌ Cannot delete '{name_arg}'"
        )]
    
    elif name == "streamdeck_disconnect":
        state.disconnect()
        return [TextContent(type="text", text="✅ Disconnected from Stream Deck")]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
