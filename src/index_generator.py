"""
Index file generator for family tree notes.

This module generates an alphabetical index of all individuals in the
family tree.
"""

from pathlib import Path
from typing import List, Any, Optional
import logging
from utils import extract_year

# Avoid importing `individual` at module import time to keep this module test-friendly
# and to prevent hard dependency on python-gedcom during isolated unit tests.
from utils import FilenameRegistry  # canonical filename utility
from utils import sort as sort_utils


logger = logging.getLogger(__name__)


class IndexGenerator:
    """
    Generates an index file linking to all individual notes.

    The index is organized alphabetically by last name, then first name.
    """

    def __init__(
        self,
        output_dir: Path,
        people_subdir: str = "",
        filename_map: Optional[dict] = None,
        filename_registry: FilenameRegistry | None = None,
    ):
        """
        Create an IndexGenerator configured with the target output directory and an optional subdirectory for individual files.

        Parameters:
            output_dir (Path): Directory where the generated index file will be written.
            people_subdir (str): Optional subdirectory name to prepend to people file links (empty string means no subdirectory).
            filename_map (dict): Optional mapping from individual IDs to actual filenames (for handling duplicates).
            filename_registry (FilenameRegistry | None): Optional registry instance; if provided the registry's mapping() is used as filename map.
        """
        self.output_dir = output_dir
        self.people_subdir = people_subdir
        # If a filename_registry is provided, use its mapping. Otherwise fall back to provided filename_map.
        if filename_registry is not None:
            self.filename_map = filename_registry.mapping()
        else:
            self.filename_map = filename_map or {}

    def generate_index(
        self, individuals: List[Any], index_filename: str = "Index.md"
    ) -> Path:
        """
        Generate an alphabetical Markdown index of individuals grouped by last-name initial.

        Writes a Markdown file at self.output_dir / index_filename containing a header with the total count, section headers "## {LETTER}" for each last-name initial (uses "#" for individuals without a last name), and one wiki-style link per individual (prefixed by the instance's people_subdir when set). Each entry includes an optional life-span "(birth-death)" when birth or death information is available.

        Parameters:
            individuals (List[Individual]): Individuals to include in the index.
            index_filename (str): Name of the index file to create (default: 'Index.md').

        Returns:
            Path: Path to the created index file.
        """
        index_path = self.output_dir / index_filename

        logger.info(f"Generating index file: {index_filename}")

        # Sort individuals by last name, then first name
        # Use centralized sort utility for stable ordering across modules
        sorted_individuals = sort_utils.sort_individuals(individuals)

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# Family Tree Index\n\n")
            f.write(f"Total individuals: {len(individuals)}\n\n")

            # Group by last name initial
            current_letter = ""

            for individual in sorted_individuals:
                _, last = individual.get_names()

                # Write letter header if changed
                if last:
                    letter = last[0].upper()
                else:
                    letter = "#"  # For individuals without last name

                if letter != current_letter:
                    current_letter = letter
                    f.write(f"\n## {current_letter}\n\n")

                # Write individual link with life span
                # Use mapped filename if available, otherwise use base filename
                individual_id = individual.get_id()
                if individual_id in self.filename_map:
                    filename = self.filename_map[individual_id]
                else:
                    filename = individual.get_file_name()

                birth_info = individual.get_birth_info() or {}
                death_info = individual.get_death_info() or {}

                # Format life span
                birth_year = birth_info.get("year", "")
                death_date = death_info.get("date", "")
                if birth_year or death_date:
                    death_year = ""
                    if death_date:
                        death_year = extract_year(death_date)
                    life_span = f" ({birth_year}-{death_year})"
                else:
                    life_span = ""

                # Create WikiLink with path prefix if using subdirectories
                if self.people_subdir:
                    wiki_link = f"[[{self.people_subdir}/{filename}|{individual.get_full_name()}]]"
                else:
                    wiki_link = f"[[{filename}]]"

                f.write(f"- {wiki_link}{life_span}\n")

        logger.info(f"Index generated with {len(individuals)} individuals")
        return index_path
