"""
Tests for the Stream Deck desktop profile manager.
"""

import json
import shlex
from pathlib import Path
from unittest.mock import patch

import pytest

from profile_manager import PageNotFoundError, ProfileManager, ProfileValidationError


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
