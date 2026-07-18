"""
Tests for the Stream Deck profile-writer MCP server surface.
"""

import json

import pytest

import profile_server


@pytest.mark.asyncio
async def test_profile_server_exposes_read_plugins_tool() -> None:
    tools = await profile_server.list_tools()

    names = {tool.name for tool in tools}
    assert "streamdeck_read_plugins" in names


@pytest.mark.asyncio
async def test_profile_server_read_plugins_calls_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    class StubManager:
        def list_plugins(self, *, plugin_id=None, include_raw_manifest=False):
            calls["plugin_id"] = plugin_id
            calls["include_raw_manifest"] = include_raw_manifest
            return {
                "plugins_dir": "/tmp/plugins",
                "plugin_count": 1,
                "plugins": [{"plugin_uuid": "com.example.plugin"}],
            }

    monkeypatch.setattr(profile_server, "manager", StubManager())

    response = await profile_server.call_tool(
        "streamdeck_read_plugins",
        {"plugin_id": "com.example.plugin", "include_raw_manifest": "true"},
    )

    payload = json.loads(response[0].text)
    assert calls == {"plugin_id": "com.example.plugin", "include_raw_manifest": True}
    assert payload["plugins"][0]["plugin_uuid"] == "com.example.plugin"
