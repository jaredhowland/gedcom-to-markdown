"""
GEDCOM file parser module.

This module provides a clean interface to parse GEDCOM files and extract
individual and family data.
"""

from pathlib import Path
from typing import List
import logging

try:
    from gedcom.parser import Parser
    from gedcom.element.individual import IndividualElement
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'python-gedcom'. Install with: pip install python-gedcom"
    ) from e


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

        # Check and fix line endings if needed
        self._fix_line_endings_if_needed()

        self.parser = Parser()

        try:
            logger.info(f"Parsing GEDCOM file: {file_path}")
            self.parser.parse_file(str(file_path))
        except Exception as e:
            raise ValueError(f"Failed to parse GEDCOM file: {e}") from e

    def _fix_line_endings_if_needed(self):
        """
        Convert CR-only (old Mac) line endings in the GEDCOM file to LF if detected.
        
        If the file is found to use CR-only line endings, this method replaces CR with LF in-place on disk and logs a warning before the change and an informational message after successful rewriting.
        """
        # Read first chunk to check line endings
        with open(self.file_path, "rb") as f:
            sample = f.read(8192)  # Read first 8KB

        # Count different line ending types
        has_crlf = b"\r\n" in sample
        has_lf = b"\n" in sample
        has_cr = b"\r" in sample

        # If we have CR but no LF, this is a CR-only file
        if has_cr and not has_lf and not has_crlf:
            logger.warning(
                "Detected old Mac-style (CR-only) line endings in GEDCOM file. "
                "Converting to Unix-style (LF) line endings..."
            )

            # Read entire file and fix line endings
            with open(self.file_path, "rb") as f:
                content = f.read()

            # Replace CR with LF
            fixed_content = content.replace(b"\r", b"\n")

            # Write back to file
            with open(self.file_path, "wb") as f:
                f.write(fixed_content)

            logger.info("Line endings fixed successfully")

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