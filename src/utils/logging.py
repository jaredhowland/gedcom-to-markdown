"""Centralized logging helper for gedcom-to-markdown.

Provides a deterministic setup_logging(verbose: bool) function used by the CLI
and unit tests. Mirrors prior behavior used throughout the codebase.
"""

from __future__ import annotations

import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure root logging deterministically for CLI and tests.

    - root logger: WARNING (or DEBUG when verbose)
    - __main__ logger: INFO
    """
    root_logger = logging.getLogger()
    # Remove existing handlers to make tests deterministic
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    level = logging.DEBUG if verbose else logging.WARNING
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(handler)

    # main module logger should be INFO (or inherit if NOTSET)
    logging.getLogger("__main__").setLevel(logging.INFO)
