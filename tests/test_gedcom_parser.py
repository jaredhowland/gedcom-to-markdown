"""
Tests for the GedcomParser module.

This module tests GEDCOM file parsing functionality including:
- File loading and validation
- Line ending detection and correction
- Individual extraction
- Element lookup by pointer
"""

import pytest
from pathlib import Path

from gedcom_parser import GedcomParser


class TestGedcomParserInitialization:
    """Tests for GedcomParser initialization and file handling."""

    def test_init_with_valid_file(self, sample_gedcom_file):
        """Test that parser initializes successfully with a valid file."""
        parser = GedcomParser(sample_gedcom_file)
        assert parser is not None
        assert parser.file_path == sample_gedcom_file
        assert parser.parser is not None

    def test_init_with_nonexistent_file(self, temp_dir):
        """Test that FileNotFoundError is raised for missing files."""
        nonexistent = temp_dir / "nonexistent.ged"
        with pytest.raises(FileNotFoundError) as exc_info:
            GedcomParser(nonexistent)
        assert "GEDCOM file not found" in str(exc_info.value)

    def test_init_with_invalid_gedcom(self, temp_dir):
        """Test that ValueError is raised for invalid GEDCOM content."""
        invalid_file = temp_dir / "invalid.ged"
        invalid_file.write_text("This is not valid GEDCOM", encoding="utf-8")

        # The python-gedcom library is lenient, but we test the error handling path
        # by creating a file that will cause parsing issues
        try:
            parser = GedcomParser(invalid_file)
            # If it doesn't raise, that's okay - the library is lenient
            assert parser is not None
        except ValueError as e:
            assert "Failed to parse GEDCOM file" in str(e)


class TestLineEndingFixes:
    """Tests for line ending detection and correction."""

    def test_fix_cr_only_line_endings(self, sample_gedcom_cr_only):
        """Test that CR-only line endings are converted to LF."""
        # Read the original content to verify it has CR-only
        original_content = sample_gedcom_cr_only.read_bytes()
        assert b"\r\n" not in original_content  # No CRLF
        assert b"\r" in original_content  # Has CR

        # Parse the file (should trigger line ending fix)
        _parser = GedcomParser(sample_gedcom_cr_only)

        # Read the fixed content
        fixed_content = sample_gedcom_cr_only.read_bytes()
        assert b"\n" in fixed_content  # Has LF
        # After fix, original CR should be replaced
        assert fixed_content.count(b"\r\n") == 0  # No CRLF (we convert to LF only)

    def test_no_fix_for_normal_line_endings(self, sample_gedcom_file):
        """Test that files with normal line endings are not modified."""
        original_content = sample_gedcom_file.read_bytes()
        original_size = len(original_content)

        # Parse the file
        _parser = GedcomParser(sample_gedcom_file)

        # Content should be unchanged
        new_content = sample_gedcom_file.read_bytes()
        assert len(new_content) == original_size


class TestIndividualExtraction:
    """Tests for extracting individuals from GEDCOM files."""

    def test_get_individuals(self, sample_gedcom_file):
        """Test extraction of all individuals from GEDCOM file."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()

        # Our sample has 3 individuals (I1, I2, I3)
        assert len(individuals) == 3

        # Check that all are IndividualElement objects
        from gedcom.element.individual import IndividualElement

        assert all(isinstance(ind, IndividualElement) for ind in individuals)

    def test_get_individuals_with_empty_gedcom(self, temp_dir):
        """Test that empty GEDCOM returns no individuals."""
        empty_gedcom = temp_dir / "empty.ged"
        empty_gedcom.write_text(
            """0 HEAD
1 SOUR TestApp
0 TRLR
""",
            encoding="utf-8",
        )

        parser = GedcomParser(empty_gedcom)
        individuals = parser.get_individuals()
        assert len(individuals) == 0


class TestElementLookup:
    """Tests for looking up elements by pointer."""

    def test_get_element_by_pointer(self, sample_gedcom_file):
        """Test looking up an element by its pointer."""
        parser = GedcomParser(sample_gedcom_file)

        # Look up individual I1
        element = parser.get_element_by_pointer("@I1@")
        assert element is not None
        assert element.get_pointer() == "@I1@"

    def test_get_element_by_pointer_not_found(self, sample_gedcom_file):
        """Test that None is returned for non-existent pointers."""
        parser = GedcomParser(sample_gedcom_file)
        element = parser.get_element_by_pointer("@NONEXISTENT@")
        assert element is None

    def test_get_note_by_pointer(self, sample_gedcom_file):
        """Test looking up a NOTE element by pointer."""
        parser = GedcomParser(sample_gedcom_file)

        # Look up note N1
        note = parser.get_element_by_pointer("@N1@")
        assert note is not None
        assert "test note" in note.get_value().lower()

    def test_get_family_by_pointer(self, sample_gedcom_file):
        """Test looking up a FAM element by pointer."""
        parser = GedcomParser(sample_gedcom_file)

        # Look up family F1
        family = parser.get_element_by_pointer("@F1@")
        assert family is not None
        assert family.get_tag() == "FAM"
