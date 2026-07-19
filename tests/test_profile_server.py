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
    assert "streamdeck_find_actions" in names


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


@pytest.mark.asyncio
async def test_profile_server_find_actions_calls_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    class StubManager:
        def find_actions(
            self,
            *,
            query=None,
            plugin_uuid=None,
            action_uuid=None,
            plugin_name=None,
            controller=None,
            profile_name=None,
            profile_id=None,
            limit=50,
        ):
            calls.update(
                {
                    "query": query,
                    "plugin_uuid": plugin_uuid,
                    "action_uuid": action_uuid,
                    "plugin_name": plugin_name,
                    "controller": controller,
                    "profile_name": profile_name,
                    "profile_id": profile_id,
                    "limit": limit,
                }
            )
            return {
                "count": 1,
                "truncated": False,
                "actions": [{"plugin_uuid": "com.example.plugin", "action": {"ActionID": "x"}}],
            }

    monkeypatch.setattr(profile_server, "manager", StubManager())

    response = await profile_server.call_tool(
        "streamdeck_find_actions",
        {
            "query": "hue",
            "controller": "keypad",
            "limit": "10",
        },
    )

    payload = json.loads(response[0].text)
    assert calls["query"] == "hue"
    assert calls["controller"] == "keypad"
    assert calls["limit"] == 10
    assert payload["count"] == 1
    assert payload["actions"][0]["plugin_uuid"] == "com.example.plugin"


@pytest.mark.asyncio
async def test_profile_server_validation_errors_are_mcp_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubManager:
        def read_page(self, **_kwargs):
            raise profile_server.ProfileNotFoundError("Profile not found: <unspecified>")

    monkeypatch.setattr(profile_server, "manager", StubManager())

    response = await profile_server.call_tool(
        "streamdeck_read_page",
        {"directory_id": "missing-page"},
    )

    assert response.isError is True
    assert response.content[0].text == "❌ Profile not found: <unspecified>"


@pytest.mark.asyncio
async def test_profile_server_invalid_buttons_payload_is_mcp_error() -> None:
    response = await profile_server.call_tool(
        "streamdeck_write_page",
        {"buttons": "not json"},
    )

    assert response.isError is True
    assert "'buttons' was a string but not a valid JSON array" in response.content[0].text
