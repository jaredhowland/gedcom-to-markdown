"""
Simple IO manager to centralize file writes for generators.

Provides helpers to write text files and ensure parent directories exist.
Keep this intentionally small so callers can be refactored to produce
in-memory artifacts and delegate filesystem concerns here.
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def write_text_file(path: Path, content: str, encoding: str = "utf-8") -> Path:
    """Write text content to `path`, creating parent directories as needed.

    Returns the path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    logger.debug(f"Wrote text file: {path}")
    return path
