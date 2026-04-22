"""
Parser IO helpers.

This module performs file-level operations (line ending normalization,
extraction helpers) and constructs a GedcomParser instance from a file path.
Moving these responsibilities here keeps GedcomParser free of file IO when a
pre-parsed Parser instance is used.
"""

from pathlib import Path
import logging

from gedcom.parser import Parser, GedcomFormatViolationError
from gedcom_parser import GedcomParser

logger = logging.getLogger(__name__)


def parse_from_path(path: Path) -> GedcomParser:
    """
    Parse a GEDCOM file from disk, normalizing line endings if necessary,
    and return a GedcomParser wrapping the in-memory Parser instance.

    This helper performs file IO and should be used by CLI or other top-level
    wiring code. Tests that need to control IO may choose to construct a
    gedcom.parser.Parser directly and pass it to GedcomParser.
    """
    from utils import io as io_utils

    if not path.exists():
        raise FileNotFoundError(f"GEDCOM file not found: {path}")

    raw = path.read_bytes()
    normalized = io_utils.normalize_line_endings(raw)

    # If CR-only line endings were detected, rewrite the file with normalized content
    if b"\r" in raw and b"\n" not in raw:
        logger.warning(
            "Detected old Mac-style (CR-only) line endings in GEDCOM file. Converting to Unix-style (LF) line endings..."
        )
        path.write_text(normalized, encoding="utf-8")
        logger.info("Line endings fixed successfully")

    # Initialize and parse with python-gedcom Parser
    parser = Parser()
    try:
        parser.parse_file(str(path))
    except GedcomFormatViolationError as e:
        # Specific parsing error raised by python-gedcom when the document
        # violates GEDCOM 5.5 format. Convert to our ValueError API.
        logger.exception("GEDCOM format violation: %s", e)
        raise ValueError(f"Failed to parse GEDCOM file: {e}") from e
    except (RuntimeError, ValueError) as e:
        logger.exception("Failed to parse GEDCOM file: %s", e)
        raise ValueError(f"Failed to parse GEDCOM file: {e}") from e
    except OSError as e:
        logger.exception("I/O error reading GEDCOM file: %s", e)
        raise

    # Wrap the parser in our GedcomParser (no further IO performed)
    return GedcomParser(parser, file_path=path)
