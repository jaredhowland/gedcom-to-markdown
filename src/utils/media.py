"""Media copying utilities.

copy_media_preserve_structure(src_root, dest_root, exts=None)

Behavior:
- Preserves relative directory structure from src_root under dest_root
- Copies only files with extensions in 'exts' (case-insensitive)
- If destination exists and content identical, skip
- If destination exists and different, append numeric suffix before extension (e.g., photo-1.jpg)
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Iterable

DEFAULT_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


def copy_media_preserve_structure(
    src_root: str | Path, dest_root: str | Path, exts: Iterable[str] | None = None
) -> None:
    src_root = Path(src_root)
    dest_root = Path(dest_root)
    if exts is None:
        exts = DEFAULT_EXTS
    exts = {e.lower() for e in exts}

    if not src_root.exists():
        return

    for f in src_root.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in exts:
            continue
        rel = f.relative_to(src_root)
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            try:
                if dest.read_bytes() == f.read_bytes():
                    continue
            except Exception:
                pass
            stem = dest.stem
            suffix = dest.suffix
            parent = dest.parent
            i = 1
            new_dest = parent / f"{stem}-{i}{suffix}"
            while new_dest.exists():
                i += 1
                new_dest = parent / f"{stem}-{i}{suffix}"
            dest = new_dest

        shutil.copyfile(f, dest)
