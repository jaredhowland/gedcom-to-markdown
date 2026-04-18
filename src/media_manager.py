"""
MediaManager: centralizes media copying with deterministic collision resolution.

API:
- copy_media(source_dir: Path, dest_dir: Path) -> dict[str, str]
    Copies media files from source_dir to dest_dir preserving relative paths when possible.
    Resolves collisions by appending numeric suffixes to filename stem ("_1", "_2")
    in a deterministic fashion based on existing files in dest_dir.
    Returns mapping from source relative path (as str) -> destination filename (no path).
"""

from pathlib import Path
import shutil
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


def _is_media_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in ALLOWED_EXT


def _unique_dest(dest: Path) -> Path:
    """Given a desired dest Path, return a Path that does not exist by appending suffixes."""
    if not dest.exists():
        return dest
    counter = 1
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def copy_media(source_dir: Path, dest_dir: Path) -> dict:
    """
    Copy media files from source_dir into dest_dir.

    Preserves relative structure where possible (creates subdirectories under dest_dir
    matching the source relative path). If a file collision occurs (dest exists), a
    deterministic unique filename is chosen using a numeric suffix. Returns a mapping
    of source-relative-path -> dest filename (basename) so callers can map GEDCOM references.
    """
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)
    mapping = {}

    if not source_dir.exists():
        logger.debug("Source media directory does not exist: %s", source_dir)
        return mapping

    for src in sorted(source_dir.rglob("*")):
        if not _is_media_file(src):
            continue

        try:
            rel = src.relative_to(source_dir)
        except Exception:
            rel = src.name

        # Compute intended dest preserving structure
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        # If dest exists, pick a unique destination name in the same directory
        if dest.exists():
            new_dest = _unique_dest(dest)
            logger.warning("Collision detected: %s -> %s", dest.name, new_dest.name)
            dest = new_dest

        try:
            shutil.copy2(src, dest)
        except Exception:
            logger.exception("Failed to copy media file: %s", src)
            continue

        mapping[str(rel)] = dest.name

    logger.info("Copied %d media files", len(mapping))
    return mapping
