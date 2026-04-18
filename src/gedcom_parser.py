"""
GEDCOM file parser module.

This module provides a clean interface to parse GEDCOM files and extract
individual and family data.
"""

from pathlib import Path
from typing import List
import logging

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement


logger = logging.getLogger(__name__)


class GedcomParser:
    """
    Parser for GEDCOM genealogy files.

    This class wraps the python-gedcom library and provides a clean interface
    for parsing GEDCOM files and extracting individual data.
    """

    def __init__(self, file_path: Path):
        """
        Initialize the GedcomParser with a GEDCOM file path and parse its contents.

        Parameters:
            file_path (Path): Path to the GEDCOM file to open and parse.

        Raises:
            FileNotFoundError: If the GEDCOM file does not exist.
            ValueError: If parsing the GEDCOM file fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"GEDCOM file not found: {file_path}")

        self.file_path = file_path

        # Normalize line endings using utils.io.normalize_line_endings
        from utils import io as io_utils

        # Read full file and normalize in-memory; if CR-only is detected we rewrite the file
        raw = self.file_path.read_bytes()
        normalized = io_utils.normalize_line_endings(raw)

        # Detect CR-only originally: raw contained '\r' but no '\n' or '\r\n'
        if b"\r" in raw and b"\n" not in raw:
            logger.warning(
                "Detected old Mac-style (CR-only) line endings in GEDCOM file. Converting to Unix-style (LF) line endings..."
            )
            # Write normalized content back to disk
            self.file_path.write_text(normalized, encoding="utf-8")
            logger.info("Line endings fixed successfully")

        # Initialize the underlying python-gedcom Parser and parse the file
        self.parser = Parser()
        try:
            # parse_file expects a path (string)
            self.parser.parse_file(str(self.file_path))
        except Exception as e:
            logger.exception("Failed to parse GEDCOM file: %s", e)
            raise ValueError(f"Failed to parse GEDCOM file: {e}")

    def get_individuals(self) -> List[IndividualElement]:
        """
        Return all IndividualElement objects extracted from the parsed GEDCOM file.

        Returns:
            List[IndividualElement]: A list of individuals found in the GEDCOM root elements.
        """
        individuals = []
        for element in self.parser.get_root_child_elements():
            if isinstance(element, IndividualElement):
                individuals.append(element)

        logger.info(f"Found {len(individuals)} individuals")
        return individuals

    def get_element_by_pointer(self, pointer: str):
        """
        Retrieve a GEDCOM element by its pointer/ID.

        Parameters:
            pointer (str): GEDCOM pointer string (e.g., '@I123@').

        Returns:
            The element with the given pointer, or `None` if not found.
        """
        return self.parser.get_element_dictionary().get(pointer)
