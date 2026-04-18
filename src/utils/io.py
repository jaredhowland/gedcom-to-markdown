"""I/O helpers: line ending normalization and ZIP extraction for GEDCOM files.

Functions provided:
- normalize_line_endings(raw_bytes) -> str
- extract_gedzip(zip_path, extract_dir) -> (gedcom_path, media_dir_or_None)

The extract_gedzip behavior mirrors previous main.extract_gedzip: extracts the
ZIP, finds first .ged file (case-insensitive), warns if none, and returns the
media_dir (extraction root) when media files are present.
"""

from __future__ import annotations

from pathlib import Path
import zipfile
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


def normalize_line_endings(raw: bytes) -> str:
    """Normalize CR-only/CRLF/LF to LF and decode as UTF-8.

    Returns the decoded string with '\n' line endings.
    """
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("utf-8", errors="ignore")

    # CR-only (old Mac) -> replace '\r' with '\n' when no '\n' present
    if "\r" in decoded and "\n" not in decoded:
        decoded = decoded.replace("\r", "\n")

    # Normalize CRLF to LF
    decoded = decoded.replace("\r\n", "\n")
    return decoded


def extract_gedzip(
    zip_path: str | Path, extract_dir: str | Path
) -> Tuple[Path, Optional[Path]]:
    """Extract GEDZIP to extract_dir and return (gedcom_file, media_dir_or_None).

    Raises FileNotFoundError if zip doesn't exist; ValueError if no GEDCOM file found.
    """
    zip_path = Path(zip_path)
    extract_dir = Path(extract_dir)

    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # find gedcom files (case-insensitive)
    ged_files = list(extract_dir.rglob("*.ged")) + list(extract_dir.rglob("*.GED"))
    if not ged_files:
        raise ValueError("No GEDCOM file found in ZIP archive")

    if len(ged_files) > 1:
        logger.warning("Multiple GEDCOM files found in ZIP; using first")

    gedcom_file = ged_files[0]

    # detect media files
    media_found = any(
        f.suffix.lower() in MEDIA_EXTS for f in extract_dir.rglob("*") if f.is_file()
    )
    media_dir = extract_dir if media_found else None
    return gedcom_file, media_dir
