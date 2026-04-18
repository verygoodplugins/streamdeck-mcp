"""
Tests for the Stream Deck desktop profile manager.
"""

import json
import shlex
from pathlib import Path
from unittest.mock import patch

import pytest

from profile_manager import (
    PageNotFoundError,
    ProfileManager,
    ProfileManagerError,
    ProfileValidationError,
    StreamDeckAppRunningError,
)


@pytest.fixture(autouse=True)
def _stub_stream_deck_app_not_running():
    """Default: act as if the Stream Deck app is not running so tests hit the write path."""

    with patch("profile_manager.is_stream_deck_app_running", return_value=False):
        yield


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _make_page_manifest(actions: dict | None = None, *, name: str = "") -> dict:
    return {
        "Controllers": [
            {
                "Actions": actions,
                "Type": "Keypad",
            }
        ],
        "Icon": "",
        "Name": name,
    }


@pytest.fixture
def sample_profiles_v3(tmp_path: Path) -> Path:
    profiles_dir = tmp_path / "ProfilesV3"
    profile_dir = profiles_dir / "PROFILE-ONE.sdProfile"

    profile_manifest = {
        "AppIdentifier": "*",
        "Device": {"Model": "20GBA9901", "UUID": "@(1)[4057/128/DL17K1A70403]"},
        "Name": "Default Profile",
        "Pages": {
            "Current": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "Default": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "Pages": [
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "cccccccc-cccc-cccc-cccc-cccccccccccc",
            ],
        },
        "Version": "3.0",
    }

    default_page = _make_page_manifest()
    current_page = _make_page_manifest(
        {
            "0,0": {
                "ActionID": "action-open",
                "LinkedTitle": False,
                "Name": "Open",
                "Plugin": {
                    "Name": "Open",
                    "UUID": "com.elgato.streamdeck.system.open",
                    "Version": "1.0",
                },
                "Settings": {"path": '"/tmp/example.sh"'},
                "State": 0,
                "States": [
                    {
                        "Title": "Deploy",
                        "Image": "Images/deploy.png",
                        "FontSize": 12,
                        "TitleAlignment": "bottom",
                        "TitleColor": "#ffffff",
                        "ShowTitle": True,
                    }
                ],
                "UUID": "com.elgato.streamdeck.system.open",
            }
        },
        name="Work",
    )
    extra_page = _make_page_manifest(name="Lights")

    _write_json(profile_dir / "manifest.json", profile_manifest)
    _write_json(
        profile_dir / "Profiles" / "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA" / "manifest.json",
        default_page,
    )
    _write_json(
        profile_dir / "Profiles" / "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB" / "manifest.json",
        current_page,
    )
    _write_json(
        profile_dir / "Profiles" / "CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC" / "manifest.json",
        extra_page,
    )

    return profiles_dir


@pytest.fixture
def sample_profiles_v2(tmp_path: Path) -> Path:
    profiles_dir = tmp_path / "ProfilesV2"
    profile_dir = profiles_dir / "LEGACY.sdProfile"
    profile_manifest = {
        "Device": {"Model": "20GBA9901", "UUID": "@(1)[4057/128/DL17K1A70403]"},
        "Name": "Legacy Profile",
        "Pages": {
            "Current": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "Default": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "Pages": ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
        },
        "Version": "2.0",
    }
    _write_json(profile_dir / "manifest.json", profile_manifest)
    _write_json(
        profile_dir / "Profiles" / "PAGEDEFAULTTOKEN1234567890AB" / "manifest.json",
        _make_page_manifest(name="Default"),
    )
    _write_json(
        profile_dir / "Profiles" / "PAGEWORKTOKEN1234567890ABCD" / "manifest.json",
        _make_page_manifest(
            {
                "4,2": {
                    "ActionID": "next-page",
                    "LinkedTitle": True,
                    "Name": "Next Page",
                    "Plugin": {
                        "Name": "Pages",
                        "UUID": "com.elgato.streamdeck.page",
                        "Version": "1.0",
                    },
                    "Settings": {},
                    "State": 0,
                    "States": [{}],
                    "UUID": "com.elgato.streamdeck.page.next",
                }
            },
            name="Page 1",
        ),
    )
    return profiles_dir


def test_list_profiles_reads_v3_pages(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    profiles = manager.list_profiles()

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["version"] == "3.0"
    assert profile["page_count"] == 3
    assert profile["pages"][0]["is_default"] is True
    assert profile["pages"][1]["is_current"] is True
    assert profile["pages"][1]["directory_id"] == "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"


def test_read_page_returns_simplified_buttons(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    page = manager.read_page(profile_name="Default Profile", page_index=1)

    assert page["layout"] == {"columns": 5, "rows": 3}
    assert page["page"]["name"] == "Work"
    assert page["buttons"][0]["key"] == 0
    assert page["buttons"][0]["title"] == "Deploy"
    assert page["buttons"][0]["plugin_uuid"] == "com.elgato.streamdeck.system.open"


def test_write_page_updates_existing_v3_page(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(text="Ship")

    result = manager.write_page(
        profile_name="Default Profile",
        directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
        page_name="Shipping",
        buttons=[
            {
                "key": 1,
                "title": "Ship",
                "icon_path": icon["path"],
                "path": str(tmp_path / "ship.sh"),
            }
        ],
    )

    assert result["created"] is False
    page = manager.read_page(
        profile_name="Default Profile", directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
    )
    assert page["page"]["name"] == "Shipping"
    assert page["buttons"][0]["key"] == 1
    assert page["buttons"][0]["title"] == "Ship"
    assert page["buttons"][0]["image"].startswith("Images/")


def test_write_page_creates_new_v3_page_and_sets_current(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    result = manager.write_page(
        profile_id="PROFILE-ONE",
        create_new=True,
        page_name="Podcast",
        make_current=True,
        buttons=[
            {
                "key": 0,
                "action_type": "next_page",
                "title": "Next",
            }
        ],
    )

    assert result["created"] is True
    profile_manifest = json.loads(
        (sample_profiles_v3 / "PROFILE-ONE.sdProfile" / "manifest.json").read_text()
    )
    assert profile_manifest["Pages"]["Current"] == result["page_uuid"]
    assert result["page_uuid"] in profile_manifest["Pages"]["Pages"]
    assert (
        sample_profiles_v3 / "PROFILE-ONE.sdProfile" / "Profiles" / result["directory_id"]
    ).exists()


def test_create_action_writes_script_and_returns_open_action(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    project_dir = tmp_path / "project"

    result = manager.create_action(
        name="Git Pull",
        command="git pull",
        working_directory=str(project_dir),
    )

    script_path = Path(result["script_path"])
    assert script_path.exists()
    assert f"cd {shlex.quote(str(project_dir))}" in script_path.read_text()
    assert result["action"]["Settings"]["path"] == f'"{script_path}"'
    assert result["action"]["UUID"] == "com.elgato.streamdeck.system.open"


def test_create_action_rejects_windows_runtime(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with patch("profile_manager.sys.platform", "win32"):
        with pytest.raises(ProfileValidationError, match="only supported on POSIX systems"):
            manager.create_action(name="Git Pull", command="git pull")


def test_v2_pages_can_be_targeted_by_directory_id(sample_profiles_v2: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v2,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    page = manager.read_page(
        profile_name="Legacy Profile",
        directory_id="PAGEWORKTOKEN1234567890ABCD",
    )

    assert page["profile"]["version"] == "2.0"
    assert page["page"]["mapping"] == "directory-order"
    assert page["buttons"][0]["position"] == "4,2"


def test_v2_page_indices_are_sorted_by_directory_id(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "ProfilesV2"
    profile_dir = profiles_dir / "LEGACY.sdProfile"
    profile_manifest = {
        "Device": {"Model": "20GBA9901", "UUID": "@(1)[4057/128/DL17K1A70403]"},
        "Name": "Legacy Profile",
        "Pages": {
            "Current": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "Default": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "Pages": ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
        },
        "Version": "2.0",
    }
    _write_json(profile_dir / "manifest.json", profile_manifest)
    _write_json(
        profile_dir / "Profiles" / "ZZZPAGE" / "manifest.json",
        _make_page_manifest(name="Later"),
    )
    _write_json(
        profile_dir / "Profiles" / "AAAPAGE" / "manifest.json",
        _make_page_manifest(name="Earlier"),
    )

    manager = ProfileManager(
        profiles_dir=profiles_dir,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    first_page = manager.read_page(profile_name="Legacy Profile", page_index=0)
    second_page = manager.read_page(profile_name="Legacy Profile", page_index=1)

    assert first_page["page"]["directory_id"] == "AAAPAGE"
    assert second_page["page"]["directory_id"] == "ZZZPAGE"


def test_write_page_rejects_positions_outside_columns(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError, match="exceeds the inferred deck layout 5x3"):
        manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[
                {
                    "position": "5,0",
                    "path": str(tmp_path / "ship.sh"),
                }
            ],
        )


def test_read_page_requires_locator(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError):
        manager.read_page(profile_name="Default Profile")

    with pytest.raises(PageNotFoundError):
        manager.read_page(profile_name="Default Profile", directory_id="DOES-NOT-EXIST")


@pytest.fixture
def sample_profiles_plus_xl(tmp_path: Path) -> Path:
    """Profile shaped like a Stream Deck + XL: Keypad 9x4 + Encoder 6x1 on the same page."""

    profiles_dir = tmp_path / "ProfilesV3"
    profile_dir = profiles_dir / "PLUSXL.sdProfile"
    page_uuid = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    profile_manifest = {
        "AppIdentifier": "*",
        "Device": {"Model": "20GBX9901", "UUID": "@(1)[4057/198/AD4MA610100UAO]"},
        "Name": "Plus XL",
        "Pages": {
            "Current": page_uuid,
            "Default": page_uuid,
            "Pages": [page_uuid],
        },
        "Version": "3.0",
    }
    dial_action = {
        "ActionID": "dial-volume",
        "LinkedTitle": True,
        "Name": "Volume",
        "Plugin": {"Name": "Wave Link", "UUID": "com.elgato.wave-link", "Version": "1.0"},
        "Settings": {"channelId": "mic"},
        "State": 0,
        "States": [{"Title": "Mic"}, {}],
        "UUID": "com.elgato.wave-link.wavecontrol",
    }
    key_action = {
        "ActionID": "action-open",
        "LinkedTitle": False,
        "Name": "Open",
        "Plugin": {
            "Name": "Open",
            "UUID": "com.elgato.streamdeck.system.open",
            "Version": "1.0",
        },
        "Settings": {"path": '"/tmp/example.sh"'},
        "State": 0,
        "States": [{"Title": "Run"}],
        "UUID": "com.elgato.streamdeck.system.open",
    }
    page_manifest = {
        "Controllers": [
            {"Type": "Keypad", "Actions": {"0,0": key_action}},
            {"Type": "Encoder", "Actions": {"2,0": dial_action}},
        ],
        "Icon": "",
        "Name": "Plus XL Page",
    }

    _write_json(profile_dir / "manifest.json", profile_manifest)
    _write_json(
        profile_dir / "Profiles" / page_uuid.upper() / "manifest.json",
        page_manifest,
    )
    return profiles_dir


def test_read_page_returns_both_controllers(sample_profiles_plus_xl: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    page = manager.read_page(profile_name="Plus XL", page_index=0)

    assert page["layout"] == {"columns": 9, "rows": 4}
    assert page["layouts"] == {
        "keypad": {"columns": 9, "rows": 4},
        "encoder": {"columns": 6, "rows": 1},
    }
    controllers = {button["controller"] for button in page["buttons"]}
    assert controllers == {"keypad", "encoder"}

    dial = next(button for button in page["buttons"] if button["controller"] == "encoder")
    assert dial["position"] == "2,0"
    assert dial["key"] == 2
    assert dial["plugin_uuid"] == "com.elgato.wave-link"


def test_write_page_preserves_encoder_when_updating_keypad(
    sample_profiles_plus_xl: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "key": 1,
                "title": "Hello",
                "path": str(tmp_path / "hello.sh"),
            }
        ],
    )

    page = manager.read_page(profile_name="Plus XL", page_index=0)
    encoder_buttons = [b for b in page["buttons"] if b["controller"] == "encoder"]
    assert len(encoder_buttons) == 1
    assert encoder_buttons[0]["plugin_uuid"] == "com.elgato.wave-link"

    keypad_buttons = [b for b in page["buttons"] if b["controller"] == "keypad"]
    assert {b["position"] for b in keypad_buttons} == {"1,0"}
    assert keypad_buttons[0]["title"] == "Hello"


def test_write_page_targets_encoder_controller(
    sample_profiles_plus_xl: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "controller": "dial",
                "key": 0,
                "action_type": "next_page",
                "title": "Next",
            }
        ],
        clear_existing=False,
    )

    page = manager.read_page(profile_name="Plus XL", page_index=0)
    encoder_positions = {b["position"] for b in page["buttons"] if b["controller"] == "encoder"}
    assert encoder_positions == {"0,0", "2,0"}

    keypad_positions = {b["position"] for b in page["buttons"] if b["controller"] == "keypad"}
    assert keypad_positions == {"0,0"}


def test_write_page_rejects_encoder_on_keypad_only_device(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError, match="Encoder"):
        manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[
                {
                    "controller": "encoder",
                    "key": 0,
                    "action_type": "next_page",
                }
            ],
        )


def test_write_page_rejects_unknown_controller(
    sample_profiles_plus_xl: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError, match="Unknown controller"):
        manager.write_page(
            profile_name="Plus XL",
            page_index=0,
            buttons=[{"controller": "mystery", "key": 0, "action_type": "next_page"}],
        )


def test_write_page_clear_existing_with_empty_buttons_clears_keypad(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    """Regression: clear_existing=True with an empty button list must clear the Keypad."""
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    # Pre-populate a button so there is something to clear.
    manager.write_page(
        profile_name="Default Profile",
        directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
        buttons=[{"key": 0, "title": "Before", "action_type": "next_page"}],
        clear_existing=True,
    )
    page = manager.read_page(
        profile_name="Default Profile", directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
    )
    assert len(page["buttons"]) == 1

    # Now clear with no buttons — the page should have no buttons afterwards.
    manager.write_page(
        profile_name="Default Profile",
        directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
        buttons=[],
        clear_existing=True,
    )
    page = manager.read_page(
        profile_name="Default Profile", directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
    )
    assert page["buttons"] == []


def test_write_page_refuses_while_app_running(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with patch("profile_manager.is_stream_deck_app_running", return_value=True):
        with pytest.raises(StreamDeckAppRunningError, match="running"):
            manager.write_page(
                profile_name="Default Profile",
                directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
                buttons=[{"key": 0, "title": "x", "action_type": "next_page"}],
            )


def test_write_page_auto_quit_app_stops_then_writes(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    stop_report = {"stopped": True, "graceful": ["Stream Deck"], "forced": []}

    with (
        patch("profile_manager.is_stream_deck_app_running", side_effect=[True, False]),
        patch("profile_manager.stop_stream_deck_app", return_value=stop_report) as stop_mock,
    ):
        result = manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[{"key": 0, "title": "x", "action_type": "next_page"}],
            auto_quit_app=True,
        )

    stop_mock.assert_called_once()
    assert result["app_quit"] == stop_report
    page = manager.read_page(
        profile_name="Default Profile",
        directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
    )
    assert page["buttons"][0]["title"] == "x"


def test_write_page_auto_quit_app_raises_when_stop_fails(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    stop_report = {"stopped": False, "graceful": [], "forced": [], "reason": "killall failed"}

    with (
        patch("profile_manager.is_stream_deck_app_running", return_value=True),
        patch("profile_manager.stop_stream_deck_app", return_value=stop_report),
    ):
        with pytest.raises(StreamDeckAppRunningError, match="could not be stopped"):
            manager.write_page(
                profile_name="Default Profile",
                directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
                buttons=[{"key": 0, "title": "x", "action_type": "next_page"}],
                auto_quit_app=True,
            )


def test_write_page_records_no_quit_when_app_not_running(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    # autouse fixture already pins is_stream_deck_app_running to False
    result = manager.write_page(
        profile_name="Default Profile",
        directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
        buttons=[{"key": 0, "title": "x", "action_type": "next_page"}],
    )
    assert result["app_quit"] is None


def test_restart_app_launches_by_explicit_path(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    fake_app = tmp_path / "Fake Stream Deck.app"
    fake_app.mkdir()
    open_call = {"args": None}

    def _fake_run(cmd, **kwargs):
        open_call["args"] = cmd
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with (
        patch("profile_manager.sys.platform", "darwin"),
        patch.dict("os.environ", {"STREAMDECK_APP_PATH": str(fake_app)}),
        patch("profile_manager.stop_stream_deck_app", return_value={"stopped": True}),
        patch("profile_manager.subprocess.run", side_effect=_fake_run),
    ):
        result = manager.restart_app()

    assert open_call["args"] == ["open", str(fake_app)]
    assert result["app_path"] == str(fake_app)
    assert result["restarted"] is True


def test_restart_app_errors_when_app_missing(sample_profiles_v3: Path, tmp_path: Path) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    missing_app = tmp_path / "nope.app"

    with (
        patch("profile_manager.sys.platform", "darwin"),
        patch.dict("os.environ", {"STREAMDECK_APP_PATH": str(missing_app)}),
    ):
        with pytest.raises(ProfileManagerError, match="not found"):
            manager.restart_app()


def _icon_manager(tmp_path: Path) -> ProfileManager:
    return ProfileManager(
        profiles_dir=tmp_path / "profiles",
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )


def test_create_icon_mdi_glyph_only(tmp_path: Path) -> None:
    from PIL import Image

    manager = _icon_manager(tmp_path)
    result = manager.create_icon(
        icon="mdi:cpu-64-bit",
        icon_color="#00ff88",
        bg_color="#1a1a1a",
    )

    assert result["icon"] == "mdi:cpu-64-bit"
    assert result["size"] == {"width": 72, "height": 72}

    png = Image.open(result["path"])
    assert png.size == (72, 72)
    # Avoid asserting on a single center pixel: some glyphs have holes/empty centers
    # and antialiasing can shift exact pixel values between environments. Instead,
    # verify the rendered image contains a meaningful number of non-background pixels
    # that lean toward the requested icon color (#00ff88) rather than the background
    # color (#1a1a1a).
    bg_rgb = (0x1A, 0x1A, 0x1A)
    greenish_pixels = 0
    for pixel in png.convert("RGBA").getdata():
        r, g, b, a = pixel
        if a == 0:
            continue
        if (r, g, b) == bg_rgb:
            continue
        if g > r and g > b and g > bg_rgb[1] + 40:
            greenish_pixels += 1

    assert greenish_pixels >= 25, (
        f"expected rendered glyph to contain greenish non-background pixels, got "
        f"{greenish_pixels}"
    )


def test_create_icon_rejects_icon_and_text_together(tmp_path: Path) -> None:
    """The Elgato app overlays the button 'title' on top of its image; baking text
    into the PNG on an icon button produces doubled text. The tool enforces that
    callers pick one or the other."""
    manager = _icon_manager(tmp_path)

    with pytest.raises(ProfileValidationError, match="either 'text' or 'icon'"):
        manager.create_icon(icon="mdi:volume-high", text="Vol")


def test_create_icon_legacy_text_only_still_works(tmp_path: Path) -> None:
    manager = _icon_manager(tmp_path)
    result = manager.create_icon(text="Hi", bg_color="#1e40af", text_color="#ffffff")

    assert "icon" not in result
    assert result["size"] == {"width": 72, "height": 72}
    assert Path(result["path"]).exists()


def test_create_icon_unknown_name_suggests_alternatives(tmp_path: Path) -> None:
    manager = _icon_manager(tmp_path)

    with pytest.raises(ValueError) as excinfo:
        manager.create_icon(icon="mdi:cpuuu")

    msg = str(excinfo.value)
    assert "not found" in msg
    # Fuzzy match should point toward a real cpu icon.
    assert "cpu" in msg.lower()


def test_create_icon_resolves_alias_to_canonical_name(tmp_path: Path) -> None:
    # 'computer' is a known alias that resolves to a canonical MDI name; verify it
    # both renders and that the canonical name is reported back to the caller.
    manager = _icon_manager(tmp_path)
    result = manager.create_icon(icon="mdi:computer")

    assert result["icon"].startswith("mdi:")
    assert result["icon"] != "mdi:computer"


def test_create_icon_rejects_empty_spec(tmp_path: Path) -> None:
    manager = _icon_manager(tmp_path)

    with pytest.raises(ProfileValidationError, match="requires"):
        manager.create_icon()


def test_create_icon_rejects_out_of_range_scale(tmp_path: Path) -> None:
    manager = _icon_manager(tmp_path)

    with pytest.raises(ProfileValidationError, match="icon_scale"):
        manager.create_icon(icon="mdi:cpu", icon_scale=1.5)


def test_create_icon_touchstrip_shape_emits_200x100(tmp_path: Path) -> None:
    from PIL import Image

    manager = _icon_manager(tmp_path)
    result = manager.create_icon(
        icon="mdi:volume-high", icon_color="#00ff88", bg_color="#1a1a1a", shape="touchstrip"
    )

    assert result["shape"] == "touchstrip"
    assert result["size"] == {"width": 200, "height": 100}
    png = Image.open(result["path"])
    assert png.size == (200, 100)


def test_create_icon_rejects_unknown_shape(tmp_path: Path) -> None:
    manager = _icon_manager(tmp_path)

    with pytest.raises(ProfileValidationError, match="shape"):
        manager.create_icon(icon="mdi:cpu", shape="donut")


def test_install_mcp_plugin_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from profile_manager import ensure_mcp_plugin_installed
    from streamdeck_plugin import PLUGIN_DIR_NAME

    plugins_dir = tmp_path / "plugins"
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: plugins_dir)

    first = ensure_mcp_plugin_installed()
    assert first["installed"] is True
    assert (plugins_dir / PLUGIN_DIR_NAME / "manifest.json").exists()
    assert (plugins_dir / PLUGIN_DIR_NAME / "plugin.js").exists()
    assert (plugins_dir / PLUGIN_DIR_NAME / "Images" / "plugin.png").exists()

    second = ensure_mcp_plugin_installed()
    assert second["installed"] is False
    assert second["reason"] == "already installed"

    forced = ensure_mcp_plugin_installed(force=True)
    assert forced["installed"] is True


def test_install_mcp_plugin_upgrades_outdated_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ensure_mcp_plugin_installed reinstalls when the installed manifest version is older."""
    import json as _json

    from profile_manager import ensure_mcp_plugin_installed
    from streamdeck_plugin import PLUGIN_DIR_NAME

    plugins_dir = tmp_path / "plugins"
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: plugins_dir)

    # Install the current version first.
    ensure_mcp_plugin_installed()

    # Simulate an older installed version by overwriting the manifest version.
    manifest_path = plugins_dir / PLUGIN_DIR_NAME / "manifest.json"
    manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["Version"] = "0.0.1"
    manifest_path.write_text(_json.dumps(manifest), encoding="utf-8")

    # Should detect the version mismatch and reinstall.
    result = ensure_mcp_plugin_installed()
    assert result["installed"] is True

    # Reinstalled manifest should now carry the current bundled version.
    from streamdeck_plugin import PLUGIN_VERSION

    reinstalled_version = _json.loads(manifest_path.read_text(encoding="utf-8")).get("Version")
    assert reinstalled_version == PLUGIN_VERSION


def test_write_page_encoder_writes_encoder_icon_and_background(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Encoder buttons route icon_path to Action.Encoder.Icon and strip_background_path
    to Action.Encoder.background, rather than the keypad State[0].Image."""
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: tmp_path / "plugins")

    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(icon="mdi:volume-high", filename="vol")
    strip = manager.create_icon(
        icon="mdi:volume-high", shape="touchstrip", filename="vol-strip"
    )

    manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "controller": "encoder",
                "key": 0,
                "icon_path": icon["path"],
                "strip_background_path": strip["path"],
                "title": "Volume",
            }
        ],
        clear_existing=False,
    )

    raw = json.loads(
        (
            sample_profiles_plus_xl
            / "PLUSXL.sdProfile"
            / "Profiles"
            / "DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"
            / "manifest.json"
        ).read_text()
    )
    encoder_actions = next(
        c["Actions"] for c in raw["Controllers"] if c["Type"] == "Encoder"
    )
    action = encoder_actions["0,0"]
    assert action["UUID"] == "io.github.verygoodplugins.streamdeck-mcp.dial"
    assert action["Encoder"]["Icon"].startswith("Images/")
    assert action["Encoder"]["background"].startswith("Images/")
    assert "Image" not in action["States"][0]


def test_write_page_rejects_strip_background_on_keypad(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    strip = manager.create_icon(icon="mdi:volume-high", shape="touchstrip", filename="bg")

    with pytest.raises(ProfileValidationError, match="strip_background_path"):
        manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[
                {
                    "key": 0,
                    "title": "Nope",
                    "strip_background_path": strip["path"],
                    "action_type": "next_page",
                }
            ],
        )


def test_write_page_auto_installs_mcp_plugin_for_encoder_default(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from streamdeck_plugin import PLUGIN_DIR_NAME

    plugins_dir = tmp_path / "plugins"
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: plugins_dir)

    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(icon="mdi:volume-high", filename="vol")

    result = manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {"controller": "encoder", "key": 0, "icon_path": icon["path"], "title": "V"}
        ],
        clear_existing=False,
    )
    assert result["mcp_plugin_install"]["installed"] is True
    assert (plugins_dir / PLUGIN_DIR_NAME / "manifest.json").exists()


def _read_plus_xl_encoder_action(profiles_dir: Path, key: str) -> dict:
    raw = json.loads(
        (
            profiles_dir
            / "PLUSXL.sdProfile"
            / "Profiles"
            / "DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"
            / "manifest.json"
        ).read_text()
    )
    encoder_actions = next(
        c["Actions"] for c in raw["Controllers"] if c["Type"] == "Encoder"
    )
    return encoder_actions[key]


def test_write_page_encoder_layout_routes_to_variant_uuid(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from streamdeck_plugin import LAYOUT_ACTION_UUIDS, PLUGIN_UUID

    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: tmp_path / "plugins")
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(icon="mdi:volume-high", filename="vol")

    manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "controller": "encoder",
                "key": 0,
                "icon_path": icon["path"],
                "title": "Volume",
                "encoder_layout": "$A1",
            }
        ],
        clear_existing=False,
    )

    action = _read_plus_xl_encoder_action(sample_profiles_plus_xl, "0,0")
    assert action["UUID"] == LAYOUT_ACTION_UUIDS["$A1"]
    assert action["Plugin"]["UUID"] == PLUGIN_UUID
    assert action["Encoder"]["Icon"].startswith("Images/")


def test_write_page_encoder_layout_default_uses_default_uuid(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from streamdeck_plugin import DEFAULT_ACTION_UUID

    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: tmp_path / "plugins")
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(icon="mdi:volume-high", filename="vol")

    manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "controller": "encoder",
                "key": 0,
                "icon_path": icon["path"],
                "title": "Volume",
            }
        ],
        clear_existing=False,
    )

    action = _read_plus_xl_encoder_action(sample_profiles_plus_xl, "0,0")
    assert action["UUID"] == DEFAULT_ACTION_UUID


def test_write_page_rejects_unknown_encoder_layout(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: tmp_path / "plugins")
    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError, match=r"\$A1"):
        manager.write_page(
            profile_name="Plus XL",
            page_index=0,
            buttons=[
                {
                    "controller": "encoder",
                    "key": 0,
                    "title": "Nope",
                    "encoder_layout": "$Z9",
                }
            ],
            clear_existing=False,
        )


def test_write_page_rejects_encoder_layout_on_keypad(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    # With other action fields: should raise encoder-only error, not "do not combine".
    with pytest.raises(ProfileValidationError, match="encoder_layout is only valid"):
        manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[
                {
                    "key": 0,
                    "title": "Nope",
                    "encoder_layout": "$A1",
                    "action_type": "next_page",
                }
            ],
        )


def test_write_page_rejects_encoder_layout_on_keypad_no_other_fields(
    sample_profiles_v3: Path, tmp_path: Path
) -> None:
    """encoder_layout on a keypad button with no other action fields must raise the
    encoder-only error, not the generic 'Button needs either...' error."""
    manager = ProfileManager(
        profiles_dir=sample_profiles_v3,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )

    with pytest.raises(ProfileValidationError, match="encoder_layout is only valid"):
        manager.write_page(
            profile_name="Default Profile",
            directory_id="BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            buttons=[
                {
                    "key": 0,
                    "title": "Nope",
                    "encoder_layout": "$A1",
                }
            ],
        )


def test_write_page_auto_installs_mcp_plugin_for_layout_variant(
    sample_profiles_plus_xl: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from streamdeck_plugin import PLUGIN_DIR_NAME

    plugins_dir = tmp_path / "plugins"
    monkeypatch.setattr("profile_manager.get_plugins_dir", lambda: plugins_dir)

    manager = ProfileManager(
        profiles_dir=sample_profiles_plus_xl,
        scripts_dir=tmp_path / "scripts",
        generated_icons_dir=tmp_path / "icons",
    )
    icon = manager.create_icon(icon="mdi:volume-high", filename="vol")

    result = manager.write_page(
        profile_name="Plus XL",
        page_index=0,
        buttons=[
            {
                "controller": "encoder",
                "key": 0,
                "icon_path": icon["path"],
                "title": "V",
                "encoder_layout": "$B1",
            }
        ],
        clear_existing=False,
    )
    assert result["mcp_plugin_install"]["installed"] is True
    assert (plugins_dir / PLUGIN_DIR_NAME / "manifest.json").exists()
