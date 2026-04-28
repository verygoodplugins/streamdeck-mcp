# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0](https://github.com/verygoodplugins/streamdeck-mcp/compare/v0.2.0...v0.3.0) (2026-04-28)


### Features

* **icons:** bundle Material Design Icons for offline glyph rendering ([#19](https://github.com/verygoodplugins/streamdeck-mcp/issues/19)) ([459d410](https://github.com/verygoodplugins/streamdeck-mcp/commit/459d41032bf60375b3fc480a13fb123d2f1457c5))
* **profile:** preserve encoder controller + Stream Deck + XL layout ([#15](https://github.com/verygoodplugins/streamdeck-mcp/issues/15)) ([f4a8402](https://github.com/verygoodplugins/streamdeck-mcp/commit/f4a840219ea7e4ff81e9bec51352518458ce16f9))
* **profile:** refuse writes while Elgato app is running + restart_app path fix ([#16](https://github.com/verygoodplugins/streamdeck-mcp/issues/16)) ([e1cb4e3](https://github.com/verygoodplugins/streamdeck-mcp/commit/e1cb4e37e053bbaa7b69ef1984d1e322a98d061a))
* **skill:** streamdeck-designer Agent Skill + MCP transport hardening ([#22](https://github.com/verygoodplugins/streamdeck-mcp/issues/22)) ([fd3ec6f](https://github.com/verygoodplugins/streamdeck-mcp/commit/fd3ec6fc105b0781e85a4d39b16a0df52c76544b))
* **touchstrip:** expose $X1/$A0/$A1/$B1/$B2/$C1 encoder layouts ([#21](https://github.com/verygoodplugins/streamdeck-mcp/issues/21)) ([efa66e4](https://github.com/verygoodplugins/streamdeck-mcp/commit/efa66e48f9158c5e21f871aeceef78e53b1f75ad))
* **touchstrip:** per-segment icon and background on Stream Deck + / + XL ([#20](https://github.com/verygoodplugins/streamdeck-mcp/issues/20)) ([a41a31c](https://github.com/verygoodplugins/streamdeck-mcp/commit/a41a31ca8bbda7bb2ed9cc0e3b6c7ab9da267f97))


### Bug Fixes

* add Stream Deck XL and missing device layouts ([#10](https://github.com/verygoodplugins/streamdeck-mcp/issues/10)) ([c89435b](https://github.com/verygoodplugins/streamdeck-mcp/commit/c89435bcab50cd85f855f255c22fdb8304e11f3f))
* **profile:** correct Stream Deck + XL keypad layout to 9x4 ([#18](https://github.com/verygoodplugins/streamdeck-mcp/issues/18)) ([d6da4b2](https://github.com/verygoodplugins/streamdeck-mcp/commit/d6da4b29af60a0c724ecc6e57bd0ba28ab951f0d))
* **profile:** map 20GBD9901 to Stream Deck + (4 dials + 4x2 keypad) ([#25](https://github.com/verygoodplugins/streamdeck-mcp/issues/25)) ([da0ada5](https://github.com/verygoodplugins/streamdeck-mcp/commit/da0ada56ba2f8efdbd683abb9eb5158664896f5c))

## [0.2.0](https://github.com/verygoodplugins/streamdeck-mcp/compare/v0.1.2...v0.2.0) (2026-03-23)


### Features

* make profile writer the default streamdeck server ([#1](https://github.com/verygoodplugins/streamdeck-mcp/issues/1)) ([bdc73c0](https://github.com/verygoodplugins/streamdeck-mcp/commit/bdc73c0654f661dc905eeaddf3791248694db6da))

### Added

- New `profile_server.py` MCP server that writes directly to Stream Deck desktop profiles
- `profile_manager.py` with ProfilesV3-first support and ProfilesV2 fallback
- New tools: `streamdeck_read_profiles`, `streamdeck_read_page`, `streamdeck_write_page`
- `streamdeck_create_icon` for generating 72x72 PNG icons
- `streamdeck_create_action` for generating script-backed Open action blocks
- `streamdeck_restart_app` for macOS desktop app reloads after profile writes
- New package entrypoints: `streamdeck-mcp` for profile writing and `streamdeck-mcp-usb` for legacy USB control
- Profile writer skill documentation for agents without MCP access
- PR title and Dependabot workflows for alignment with the shared MCP ecosystem standards

### Changed

- The default packaged server direction now targets desktop profile writing instead of exclusive USB control
- Registry metadata and package configuration now describe the profile writer as the default experience
- Security workflow now scans this repo structure instead of a non-existent `src/` directory

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
