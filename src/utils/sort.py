"""Sorting helpers for individuals.

Provides a canonical sort used across the project: sort by last name (case-insensitive),
then by first name (case-insensitive). Accepts any object implementing get_names() -> (first,last)
and returns a new sorted list.
"""

from __future__ import annotations

from typing import Iterable, List, Any


def sort_individuals(individuals: Iterable[Any]) -> List[Any]:
    """Return individuals sorted by last name, then first name (both case-insensitive).

    Individuals are expected to implement get_names() -> (first, last).
    """
    return sorted(
        list(individuals),
        key=lambda i: (
            (i.get_names()[1] or "").lower(),
            (i.get_names()[0] or "").lower(),
        ),
    )
