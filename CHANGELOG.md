# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-25

### Added

- Initial release of Stream Deck MCP server
- `streamdeck_connect` - Connect to first available Stream Deck
- `streamdeck_info` - Get deck model, key count, current page
- `streamdeck_set_button` - Set text, image, colors, and shell action
- `streamdeck_clear_button` - Clear a single button
- `streamdeck_set_brightness` - Adjust brightness (0-100%)
- `streamdeck_create_page` - Create new button profile/page
- `streamdeck_switch_page` - Switch active page
- `streamdeck_list_pages` - List all configured pages
- `streamdeck_delete_page` - Delete a page (except "main")
- `streamdeck_disconnect` - Clean USB disconnect
- Multi-page state persistence at `~/.streamdeck-mcp/`
- Support for Stream Deck, Mini, XL, MK.2, and Plus models
- Custom icon support (PNG/JPG auto-scaled to button size)
- Shell command actions triggered on button press
- CI/CD with GitHub Actions

### Notes

- Requires exclusive USB access (quit Elgato Stream Deck software first)
- Requires `hidapi` library on macOS (`brew install hidapi`)
- Linux users need udev rules for non-root USB access
