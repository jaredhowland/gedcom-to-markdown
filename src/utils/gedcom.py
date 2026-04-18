"""GEDCOM-specific helper utilities.

Centralize helper that resolves NOTE CONT/CONC continuations and pointer
references so other modules can import a single implementation.
"""

from __future__ import annotations

from typing import Optional


def resolve_gedcom_text(parser, value: Optional[str], element=None) -> str:
    """Resolve a GEDCOM text value including CONT/CONC continuations.

    Behaves identically to previous implementation in individual.py:
    - If value is a pointer ("@N1@"), resolve target element and apply
      CONC/CONT rules from its child elements.
    - If inline value, apply CONC/CONT from the provided element.

    Returns an empty string for falsy inputs or when referenced element is
    missing.
    """
    # Accept empty string but allow inline CONT/CONC processing via `element`.
    # Use None->"" normalization but do not return early for empty strings.
    if value is None:
        value = ""

    # Pointer/reference to another element (e.g., NOTE record)
    if value.startswith("@") and value.endswith("@"):
        target = parser.get_element_dictionary().get(value)
        if not target:
            return ""
        text = target.get_value() or ""
        for sub in target.get_child_elements():
            tag = sub.get_tag()
            val = sub.get_value() or ""
            if tag == "CONC":
                if val:
                    text += val
            elif tag == "CONT":
                text += "\n" + val
        return text

    # Inline text with possible CONT/CONC children.
    text = value or ""
    if element is not None:
        for sub in element.get_child_elements():
            tag = sub.get_tag()
            val = sub.get_value() or ""
            if tag == "CONC":
                if val:
                    text += val
            elif tag == "CONT":
                text += "\n" + val
    return text
