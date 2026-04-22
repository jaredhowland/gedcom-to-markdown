"""Date helper utilities for gedcom-to-markdown.

Provides small, well-tested helpers for extracting years and dates from
GEDCOM-style freeform text. Keep implementations conservative: return the
first 4-digit year found or empty string when none present.
"""

import re


def extract_year(text: str | None) -> str:
    """Return the first 4-digit year found in text, or empty string if none.

    Handles None input gracefully.
    """
    if not text:
        return ""
    m = re.search(r"\b(\d{4})\b", text)
    return m.group(1) if m else ""
