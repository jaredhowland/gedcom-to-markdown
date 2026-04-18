"""Utility helpers package for gedcom-to-markdown.

Re-export commonly used helper modules and symbols for convenient imports.
Examples:
    from utils import date, gedcom, text
    from utils import extract_year, resolve_gedcom_text
"""

# Re-export submodules
from . import text, date, gedcom, filenames, regex, io, sort, media, logging

# Convenience imports for commonly-used helpers
from .date import extract_year
from .gedcom import resolve_gedcom_text
from .text import (
    collapse_single_line,
    collapse_preserve_lines,
    escape_markdown,
    repair_broken_html_tags,
    write_multiline_note_block,
)
from .filenames import make_person_filename, FilenameRegistry
from .regex import sanitize_filename
from .io import normalize_line_endings, extract_gedzip
from .sort import sort_individuals
from .media import copy_media_preserve_structure
from .logging import setup_logging

__all__ = [
    "text",
    "date",
    "gedcom",
    "filenames",
    "regex",
    "io",
    "sort",
    "media",
    "logging",
    "extract_year",
    "resolve_gedcom_text",
    "collapse_single_line",
    "collapse_preserve_lines",
    "escape_markdown",
    "repair_broken_html_tags",
    "write_multiline_note_block",
    "make_person_filename",
    "FilenameRegistry",
    "sanitize_filename",
    "normalize_line_endings",
    "extract_gedzip",
    "sort_individuals",
    "copy_media_preserve_structure",
    "setup_logging",
]
