"""
GEDCOM file parser module.

This module provides a clean interface to parse GEDCOM files and extract
individual and family data.
"""

from pathlib import Path
from typing import List, Optional, Union
import logging

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement


logger = logging.getLogger(__name__)


class GedcomParser:
    """
    Parser for GEDCOM genealogy files.

    This class wraps the python-gedcom library and provides a clean interface
    for parsing GEDCOM files and extracting individual data.

    The constructor accepts either a pre-configured `gedcom.parser.Parser`
    instance (preferred for tests and external wiring) or a Path to a GEDCOM
    file (backwards-compatible). When given a Parser instance, no file IO is
    performed by this class.
    """

    def __init__(self, source: Union[Parser, Path], file_path: Optional[Path] = None):
        """
        Initialize the GedcomParser.

        Parameters:
            source (Parser | Path): Either an instantiated python-gedcom Parser
                (with parse_file already called) or a Path to a GEDCOM file.
            file_path (Optional[Path]): When `source` is a Parser instance,
                the original file Path may be passed here for metadata purposes.

        Raises:
            FileNotFoundError: If a Path is provided and the file does not exist.
            ValueError: If parsing the GEDCOM file fails.
            TypeError: If `source` is neither a Parser nor a Path.
        """
        # If a Parser instance is provided, use it directly (no IO)
        if isinstance(source, Parser):
            self.parser = source
            self.file_path = file_path
            return

        # If a Path is provided, delegate file IO to parser_io.parse_from_path
        if isinstance(source, Path):
            from parser_io import parse_from_path

            # parse_from_path returns a GedcomParser, reuse its internal parser
            ged_parser = parse_from_path(source)
            self.parser = ged_parser.parser
            self.file_path = ged_parser.file_path
            return

        raise TypeError(
            "GedcomParser expects a gedcom.parser.Parser or a pathlib.Path to a GEDCOM file."
        )

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
