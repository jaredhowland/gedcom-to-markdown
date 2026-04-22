"""Centralized compiled regular expressions and small helpers.

Move commonly used regexes here so other modules import constants rather
than duplicating patterns and compilation logic.
"""

from __future__ import annotations

import re
from typing import Optional


# Common compiled regexes
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')
WHITESPACE_RE = re.compile(r"\s+")
HTML_TAG_RE = re.compile(r"<[^>]*>", re.DOTALL)
NAME_RE = re.compile(r"\s*/?\s*([A-Za-z0-9]+)")


def sanitize_filename(text: Optional[str]) -> str:
    """Sanitize a text value for use as a filename (no extension).

    Removes invalid filesystem characters, collapses runs of whitespace,
    and trims surrounding whitespace.
    """
    if not text:
        return ""
    t = text.strip()
    t = INVALID_FILENAME_CHARS.sub("", t)
    t = WHITESPACE_RE.sub(" ", t)
    return t
