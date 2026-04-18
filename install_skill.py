#!/usr/bin/env python3
"""Install the bundled streamdeck-designer skill into ~/.claude/skills/.

The skill teaches Claude how to use the streamdeck-mcp tools to author complete,
themed Stream Deck layouts. Once installed, Claude Code auto-loads it when the
user's request matches its description (themed decks, service integrations,
per-hardware layouts).

Usage:
    uv run python -m install_skill [--force]
    streamdeck-mcp-install-skill [--force]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_NAME = "streamdeck-designer"
BUNDLED_SKILL_DIR = Path(__file__).parent / "streamdeck_assets" / "skill" / SKILL_NAME
SKILLS_ROOT = Path.home() / ".claude" / "skills"


def install(force: bool = False) -> dict[str, str | bool]:
    """Copy the bundled skill to ~/.claude/skills/streamdeck-designer/.

    Returns a dict describing the action taken.
    """
    if not BUNDLED_SKILL_DIR.is_dir():
        return {
            "installed": False,
            "error": f"bundled skill not found at {BUNDLED_SKILL_DIR}",
        }

    target = SKILLS_ROOT / SKILL_NAME
    if target.exists() and not force:
        return {
            "installed": False,
            "path": str(target),
            "message": (
                f"{SKILL_NAME} already installed at {target}. "
                "Pass --force (or force=True) to overwrite."
            ),
        }

    overwrote = False
    if target.exists():
        overwrote = True
        shutil.rmtree(target)

    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BUNDLED_SKILL_DIR, target)

    message = f"Installed {SKILL_NAME} to {target}."
    if overwrote:
        message = (
            f"Overwrote existing {SKILL_NAME} at {target} with the bundled "
            "version — any local edits to that directory are gone."
        )
    message += " Restart Claude Code (or start a new session) for the skill to load."

    return {
        "installed": True,
        "path": str(target),
        "overwrote": overwrote,
        "message": message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite an existing installation. DESTRUCTIVE: removes the "
            "target directory and replaces it with the bundled skill. Any "
            "local edits you made under ~/.claude/skills/streamdeck-designer/ "
            "will be lost."
        ),
    )
    args = parser.parse_args()

    result = install(force=args.force)
    if "error" in result:
        print(f"error: {result['error']}", file=sys.stderr)
        return 1
    print(result["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
