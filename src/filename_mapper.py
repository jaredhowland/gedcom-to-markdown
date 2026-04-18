"""
Filename mapper facade.

Provide a canonical import point for filename generation and registry.
This thin wrapper re-exports utilities from utils.filenames so other modules
can import from `filename_mapper` as the single source of truth.
"""

from utils.filenames import make_person_filename, FilenameRegistry

__all__ = ["make_person_filename", "FilenameRegistry"]
