"""
Tests for Stream Deck MCP Server

These tests mock the Stream Deck hardware so they can run without a physical device.
"""

import json

# Mock the StreamDeck module before importing server
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

mock_streamdeck = MagicMock()
mock_streamdeck.DeviceManager = MagicMock
mock_streamdeck.ImageHelpers = MagicMock()
mock_streamdeck.ImageHelpers.PILHelper = MagicMock()
sys.modules["StreamDeck"] = mock_streamdeck
sys.modules["StreamDeck.DeviceManager"] = mock_streamdeck
sys.modules["StreamDeck.ImageHelpers"] = mock_streamdeck.ImageHelpers

from server import (  # noqa: E402,I001
    DeckNotConnectedError,
    StreamDeckState,
    StreamDeckError,
    ValidationError,
    list_tools,
    subprocess as server_subprocess,
)


class TestStreamDeckState:
    """Tests for StreamDeckState class."""

    def _mock_deck(
        self,
        *,
        serial: str,
        deck_type: str = "Stream Deck Original",
        key_count: int = 15,
        is_open: bool = False,
    ) -> MagicMock:
        deck = MagicMock()
        deck.deck_type.return_value = deck_type
        deck.key_count.return_value = key_count
        deck.get_serial_number.return_value = serial
        deck.is_open.return_value = is_open
        deck.key_layout.return_value = (3, 5)
        deck.id.return_value = f"id-{serial}"
        deck.get_firmware_version.return_value = "1.0.0"
        deck.key_image_format.return_value = {"size": (72, 72), "format": "JPEG"}
        return deck

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path):
        """Create a temporary config directory."""
        with patch("server.CONFIG_DIR", tmp_path):
            with patch("server.PAGES_FILE", tmp_path / "pages.json"):
                with patch("server.BUTTONS_FILE", tmp_path / "buttons.json"):
                    yield tmp_path

    @pytest.fixture
    def state(self, temp_config_dir: Path):
        """Create a fresh StreamDeckState instance."""
        return StreamDeckState()

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init_creates_default_page(self, state: StreamDeckState):
        """New state should have 'main' page."""
        assert "main" in state.pages
        assert state.current_page == "main"

    def test_init_loads_existing_state(self, temp_config_dir: Path):
        """State should load from disk if files exist."""
        pages_file = temp_config_dir / "pages.json"
        buttons_file = temp_config_dir / "buttons.json"

        # Write existing state
        pages_file.write_text(
            json.dumps(
                {
                    "main": {"0": {"text": "Hello"}},
                    "gaming": {},
                }
            )
        )
        buttons_file.write_text(
            json.dumps(
                {
                    "main": {"0": {"action": "page:gaming"}},
                }
            )
        )

        with patch("server.CONFIG_DIR", temp_config_dir):
            with patch("server.PAGES_FILE", pages_file):
                with patch("server.BUTTONS_FILE", buttons_file):
                    state = StreamDeckState()

        assert "gaming" in state.pages
        assert state.pages["main"]["0"]["text"] == "Hello"
        assert state.button_callbacks["main"]["0"]["action"] == "page:gaming"

    def test_init_handles_corrupt_state(self, temp_config_dir: Path):
        """State should handle corrupt JSON files gracefully."""
        pages_file = temp_config_dir / "pages.json"
        pages_file.write_text("not valid json {{{")

        with patch("server.CONFIG_DIR", temp_config_dir):
            with patch("server.PAGES_FILE", pages_file):
                with patch("server.BUTTONS_FILE", temp_config_dir / "buttons.json"):
                    state = StreamDeckState()

        # Should fall back to default
        assert state.pages == {"main": {}}

    # ========================================================================
    # Page Management Tests
    # ========================================================================

    def test_create_page(self, state: StreamDeckState):
        """Should create new pages."""
        assert state.create_page("gaming") is True
        assert "gaming" in state.pages

    def test_create_page_duplicate(self, state: StreamDeckState):
        """Should return False for duplicate page names."""
        state.create_page("gaming")
        assert state.create_page("gaming") is False

    def test_create_page_validation(self, state: StreamDeckState):
        """Should validate page names."""
        with pytest.raises(ValidationError):
            state.create_page("")  # Empty name

        with pytest.raises(ValidationError):
            state.create_page("a" * 100)  # Too long

        with pytest.raises(ValidationError):
            state.create_page("invalid@name!")  # Invalid characters

    def test_switch_page(self, state: StreamDeckState):
        """Should switch between pages."""
        state.create_page("gaming")
        assert state.switch_page("gaming") is True
        assert state.current_page == "gaming"

    def test_switch_page_nonexistent(self, state: StreamDeckState):
        """Should raise error for nonexistent page."""
        with pytest.raises(ValidationError, match="does not exist"):
            state.switch_page("nonexistent")

    def test_delete_page(self, state: StreamDeckState):
        """Should delete pages."""
        state.create_page("gaming")
        assert state.delete_page("gaming") is True
        assert "gaming" not in state.pages

    def test_delete_main_page(self, state: StreamDeckState):
        """Should not allow deleting 'main' page."""
        with pytest.raises(ValidationError, match="Cannot delete"):
            state.delete_page("main")

    def test_delete_current_page_switches_to_main(self, state: StreamDeckState):
        """Deleting current page should switch to 'main'."""
        state.create_page("gaming")
        state.switch_page("gaming")
        state.delete_page("gaming")
        assert state.current_page == "main"

    def test_list_pages(self, state: StreamDeckState):
        """Should list all pages."""
        state.create_page("gaming")
        state.create_page("office")
        pages = state.list_pages()
        assert "main" in pages
        assert "gaming" in pages
        assert "office" in pages

    # ========================================================================
    # Validation Tests
    # ========================================================================

    def test_validate_key_negative(self, state: StreamDeckState):
        """Should reject negative key indices."""
        with pytest.raises(ValidationError, match="non-negative"):
            state._validate_key(-1)

    def test_validate_key_non_integer(self, state: StreamDeckState):
        """Should reject non-integer keys."""
        with pytest.raises(ValidationError):
            state._validate_key("0")  # type: ignore

    def test_validate_color_valid(self, state: StreamDeckState):
        """Should validate correct RGB colors."""
        assert state._validate_color((255, 128, 0)) == (255, 128, 0)
        assert state._validate_color([0, 0, 0]) == (0, 0, 0)

    def test_validate_color_out_of_range(self, state: StreamDeckState):
        """Should reject out-of-range color values."""
        with pytest.raises(ValidationError, match="0-255"):
            state._validate_color((256, 0, 0))

        with pytest.raises(ValidationError, match="0-255"):
            state._validate_color((0, -1, 0))

    def test_validate_color_wrong_length(self, state: StreamDeckState):
        """Should reject colors with wrong number of components."""
        with pytest.raises(ValidationError, match="3 values"):
            state._validate_color((255, 128))  # type: ignore

        with pytest.raises(ValidationError, match="3 values"):
            state._validate_color((255, 128, 0, 0))  # type: ignore

    def test_validate_page_name_valid(self, state: StreamDeckState):
        """Should accept valid page names."""
        # These should not raise
        state._validate_page_name("gaming")
        state._validate_page_name("home-office")
        state._validate_page_name("Work_Setup_2025")
        state._validate_page_name("My Page")

    def test_validate_page_name_invalid(self, state: StreamDeckState):
        """Should reject invalid page names."""
        with pytest.raises(ValidationError):
            state._validate_page_name("invalid@name")

        with pytest.raises(ValidationError):
            state._validate_page_name("no/slashes")

    # ========================================================================
    # Connection Tests
    # ========================================================================

    def test_check_deck_not_connected(self, state: StreamDeckState):
        """Should raise error when deck not connected."""
        with pytest.raises(DeckNotConnectedError, match="No Stream Deck connected"):
            state._check_deck_connected()

    def test_disconnect_without_deck(self, state: StreamDeckState):
        """Disconnect should be safe without connected deck."""
        state.disconnect()  # Should not raise

    def test_get_deck_info_not_connected(self, state: StreamDeckState):
        """Should return connected=False when no deck."""
        info = state.get_deck_info()
        assert info["connected"] is False

    def test_list_devices_returns_serial_type_and_key_count(self, state: StreamDeckState):
        """Should enumerate connected deck metadata without keeping devices open."""
        original = self._mock_deck(serial="ORIGINAL123", deck_type="Stream Deck Original")
        plus = self._mock_deck(serial="PLUS456", deck_type="Stream Deck Plus", key_count=8)

        with patch("server.DeviceManager") as mock_device_manager:
            mock_device_manager.return_value.enumerate.return_value = [original, plus]

            devices = state.list_devices()

        assert devices == [
            {
                "serial": "ORIGINAL123",
                "deck_type": "Stream Deck Original",
                "key_count": 15,
            },
            {
                "serial": "PLUS456",
                "deck_type": "Stream Deck Plus",
                "key_count": 8,
            },
        ]
        original.open.assert_called_once_with()
        original.close.assert_called_once_with()
        plus.open.assert_called_once_with()
        plus.close.assert_called_once_with()

    def test_connect_without_serial_opens_first_deck(self, state: StreamDeckState):
        """Default connect behavior should preserve the first enumerated deck choice."""
        original = self._mock_deck(serial="ORIGINAL123")
        plus = self._mock_deck(serial="PLUS456", deck_type="Stream Deck Plus", key_count=8)

        with patch("server.DeviceManager") as mock_device_manager:
            mock_device_manager.return_value.enumerate.return_value = [original, plus]
            with patch.object(state, "_render_current_page"):
                info = state.connect()

        assert state.deck is original
        assert info["serial"] == "ORIGINAL123"
        original.open.assert_called_once_with()
        plus.open.assert_not_called()

    def test_connect_with_serial_opens_matching_deck(self, state: StreamDeckState):
        """A provided serial should select that device from the enumerated decks."""
        original = self._mock_deck(serial="ORIGINAL123")
        plus = self._mock_deck(serial="PLUS456", deck_type="Stream Deck Plus", key_count=8)

        with patch("server.DeviceManager") as mock_device_manager:
            mock_device_manager.return_value.enumerate.return_value = [original, plus]
            with patch.object(state, "_render_current_page"):
                info = state.connect(serial="PLUS456")

        assert state.deck is plus
        assert info["serial"] == "PLUS456"
        original.open.assert_called_once_with()
        original.close.assert_called_once_with()
        plus.open.assert_called_once_with()
        plus.close.assert_not_called()

    def test_connect_with_unknown_serial_lists_available_serials(self, state: StreamDeckState):
        """Unknown serial errors should include available serials for self-correction."""
        original = self._mock_deck(serial="ORIGINAL123")
        plus = self._mock_deck(serial="PLUS456", deck_type="Stream Deck Plus", key_count=8)

        with patch("server.DeviceManager") as mock_device_manager:
            mock_device_manager.return_value.enumerate.return_value = [original, plus]
            with pytest.raises(StreamDeckError, match="MISSING789") as exc_info:
                state.connect(serial="MISSING789")

        message = str(exc_info.value)
        assert "ORIGINAL123" in message
        assert "PLUS456" in message
        assert state.deck is None
        original.close.assert_called_once_with()
        plus.close.assert_called_once_with()

    # ========================================================================
    # Button Action Tests
    # ========================================================================

    def test_set_button_action(self, state: StreamDeckState):
        """Should set button actions."""
        state.set_button_action(0, "open -a Spotify")
        assert state.button_callbacks["main"]["0"]["action"] == "open -a Spotify"
        assert state.button_callbacks["main"]["0"]["type"] == "command"

    def test_set_button_action_page_switch(self, state: StreamDeckState):
        """Should set page switch actions."""
        state.create_page("gaming")
        state.set_button_action(0, "page:gaming", "page")
        assert state.button_callbacks["main"]["0"]["action"] == "page:gaming"

    def test_set_button_action_empty(self, state: StreamDeckState):
        """Should reject empty actions."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            state.set_button_action(0, "")

    def test_key_callback_executes_commands_without_shell(self, state: StreamDeckState):
        """Commands should be tokenized and executed without a shell."""
        state.button_callbacks["main"] = {"0": {"action": "echo 'hello world'", "type": "command"}}

        with patch("server.subprocess.Popen") as mock_popen:
            state._key_callback(deck=MagicMock(), key=0, state=True)

        args, kwargs = mock_popen.call_args
        assert args[0] == ["echo", "hello world"]
        assert kwargs["shell"] is False
        assert kwargs["stdout"] is server_subprocess.DEVNULL
        assert kwargs["stderr"] is server_subprocess.DEVNULL

    # ========================================================================
    # State Persistence Tests
    # ========================================================================

    def test_state_persists_pages(self, temp_config_dir: Path, state: StreamDeckState):
        """Pages should be saved to disk."""
        pages_file = temp_config_dir / "pages.json"

        with patch("server.PAGES_FILE", pages_file):
            state.create_page("gaming")

        # Verify file was written
        assert pages_file.exists()
        saved_pages = json.loads(pages_file.read_text())
        assert "gaming" in saved_pages

    def test_state_persists_button_callbacks(self, temp_config_dir: Path, state: StreamDeckState):
        """Button callbacks should be saved to disk."""
        buttons_file = temp_config_dir / "buttons.json"

        with patch("server.BUTTONS_FILE", buttons_file):
            state.set_button_action(0, "test-action")

        # Verify file was written
        assert buttons_file.exists()
        saved_callbacks = json.loads(buttons_file.read_text())
        assert "main" in saved_callbacks


class TestMCPToolHandlers:
    """Tests for MCP tool call handlers."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock state object."""
        return MagicMock(spec=StreamDeckState)

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Tool handlers should catch and format errors properly."""
        # This would require more setup to test properly
        # Left as placeholder for integration tests
        pass

    @pytest.mark.asyncio
    async def test_tool_schema_includes_device_listing_and_connect_serial(self):
        """MCP schema should expose device listing and optional serial connect."""
        tools = await list_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        assert "streamdeck_list_devices" in tools_by_name

        connect_schema = tools_by_name["streamdeck_connect"].inputSchema
        assert "serial" in connect_schema["properties"]
        assert "serial" not in connect_schema.get("required", [])


# Run with: pytest tests/test_server.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
