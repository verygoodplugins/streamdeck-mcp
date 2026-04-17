"""Material Design Icons registry: resolve names → codepoints with fuzzy-match help on miss."""

from __future__ import annotations

import difflib
import json
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

_PACKAGE = "streamdeck_assets"
_FONT_FILENAME = "materialdesignicons-webfont.ttf"
_META_FILENAME = "mdi-meta.json"


class IconNotFoundError(ValueError):
    """Raised when an icon name cannot be resolved. Carries suggestions."""

    def __init__(self, name: str, suggestions: list[str]) -> None:
        if suggestions:
            hint = ", ".join(f"mdi:{s}" for s in suggestions)
            message = f"Icon 'mdi:{name}' not found. Did you mean: {hint}?"
        else:
            message = f"Icon 'mdi:{name}' not found and no close matches were found."
        super().__init__(message)
        self.name = name
        self.suggestions = suggestions


def _normalize_name(raw: str) -> str:
    """Strip an 'mdi:' prefix and lowercase. 'mdi-foo' also tolerated."""
    value = raw.strip().lower()
    for prefix in ("mdi:", "mdi-"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value


@lru_cache(maxsize=1)
def _meta() -> list[dict[str, Any]]:
    data = files(_PACKAGE).joinpath(_META_FILENAME).read_text(encoding="utf-8")
    return json.loads(data)


@lru_cache(maxsize=1)
def _index() -> dict[str, dict[str, Any]]:
    """name → entry, plus aliases pointing at the canonical entry."""
    out: dict[str, dict[str, Any]] = {}
    for entry in _meta():
        out[entry["name"]] = entry
        for alias in entry.get("aliases", ()) or ():
            out.setdefault(alias.lower(), entry)
    return out


@lru_cache(maxsize=1)
def _searchable_names() -> list[str]:
    return list(_index().keys())


def font_path() -> Path:
    """Return a filesystem path to the bundled MDI TTF.

    Works both from a source checkout and from an installed wheel by materializing
    the resource to a real path when the package lives inside a zip.
    """
    with as_file(files(_PACKAGE).joinpath(_FONT_FILENAME)) as p:
        return Path(p)


def resolve(name: str) -> tuple[str, str]:
    """Resolve an icon name to (canonical_name, glyph_char).

    Accepts 'mdi:cpu', 'mdi-cpu', 'cpu', or any registered alias.
    Raises IconNotFoundError with close-match suggestions on miss.
    """
    key = _normalize_name(name)
    entry = _index().get(key)
    if entry is None:
        suggestions = difflib.get_close_matches(key, _searchable_names(), n=5, cutoff=0.6)
        raise IconNotFoundError(key, suggestions)

    codepoint_hex = entry["cp"]
    glyph = chr(int(codepoint_hex, 16))
    return entry["name"], glyph


def search(query: str, limit: int = 10) -> list[str]:
    """Return canonical icon names matching the query by substring or fuzzy match."""
    key = _normalize_name(query)
    names = _searchable_names()
    substring = [n for n in names if key in n][:limit]
    if len(substring) >= limit:
        return substring
    fuzzy = difflib.get_close_matches(key, names, n=limit - len(substring), cutoff=0.5)
    seen = set(substring)
    merged = list(substring)
    for n in fuzzy:
        if n not in seen:
            merged.append(n)
            seen.add(n)
    return merged[:limit]
