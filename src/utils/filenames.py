"""Filename helpers for generating person note filenames.

Provides make_person_filename(first, last, year) that returns a stable
base filename (without extension) following the project's convention:
- "Last First Year" when available
- Omits year if missing
- Falls back to an identifier string when names are empty

Also provides simple sanitization to remove characters that are invalid
in filenames and to collapse runs of whitespace.
"""

from __future__ import annotations

import re
from typing import Optional


# Characters not allowed in many filesystems or problematic in Obsidian/WikiLinks
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def _sanitize(text: str) -> str:
    if not text:
        return ""
    # Strip surrounding whitespace, remove invalid filename chars, collapse internal whitespace
    t = text.strip()
    t = _INVALID_CHARS.sub("", t)
    t = _WHITESPACE.sub(" ", t)
    return t


def make_person_filename(
    first: Optional[str],
    last: Optional[str],
    year: Optional[str],
    fallback_id: Optional[str] = None,
) -> str:
    """Construct a base filename (no extension) for a person.

    Args:
        first: Given name (may be empty)
        last: Family name (may be empty)
        year: Birth year string (may be empty)
        fallback_id: If both names are empty, use this (e.g., GEDCOM id without @)

    Returns:
        Filename string without file extension.
    """
    f = _sanitize(first or "")
    l = _sanitize(last or "")
    y = _sanitize(year or "")

    parts = []
    if l:
        parts.append(l)
    if f:
        parts.append(f)
    if y:
        parts.append(y)

    if parts:
        return " ".join(parts)

    # Fallback to provided id-like string or a generic 'person'
    if fallback_id:
        return _sanitize(fallback_id)
    return "person"


class FilenameRegistry:
    """Registry to assign deterministic unique filenames for individuals.

    Usage:
        reg = FilenameRegistry()
        unique = reg.reserve(individual_id, base_name)
        # subsequent calls with same individual_id return the same unique name

    The registry ensures names are unique by appending " (1)", " (2)",
    etc., when a base_name is already in use.
    """

    def __init__(self):
        self._id_to_name: dict[str, str] = {}
        self._used_names: set[str] = set()

    def reserve(self, individual_id: str, base_name: str) -> str:
        """Reserve and return a unique name for the given individual id.

        If the individual_id already has a name reserved, that name is
        returned (idempotent). Otherwise a unique name is chosen from base_name
        by appending " (n)" when necessary.
        """
        if individual_id in self._id_to_name:
            return self._id_to_name[individual_id]

        unique = base_name
        counter = 1
        while unique in self._used_names:
            unique = f"{base_name} ({counter})"
            counter += 1

        self._used_names.add(unique)
        self._id_to_name[individual_id] = unique
        return unique

    def get(self, individual_id: str) -> str | None:
        return self._id_to_name.get(individual_id)

    def mapping(self) -> dict:
        return dict(self._id_to_name)
