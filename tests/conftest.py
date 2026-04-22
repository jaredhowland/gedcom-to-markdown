"""
Shared pytest fixtures for GEDCOM to Markdown tests.

This module provides common test fixtures and sample GEDCOM data
that can be used across all test modules.
"""

import pytest
from pathlib import Path

try:
    import gedcom  # noqa: F401
    _GEDCOM_AVAILABLE = True
except ModuleNotFoundError:
    _GEDCOM_AVAILABLE = False


@pytest.fixture
def require_gedcom():
    """Skip the calling test when python-gedcom is not installed.

    Add this fixture to any test (or to other fixtures) that require the
    python-gedcom library.  Tests that do *not* need the library will keep
    running even when the library is absent, so utility tests, canvas-layout
    tests, etc. are unaffected by a missing dependency.
    """
    if not _GEDCOM_AVAILABLE:
        pytest.skip("python-gedcom is not installed")


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests (pytest tmp_path fixture)."""
    # Use built-in tmp_path to avoid manual cleanup and race conditions
    return tmp_path


@pytest.fixture
def sample_gedcom_content(require_gedcom):
    """
    Provide a minimal valid GEDCOM file content.

    This sample includes:
    - Two individuals with names, dates, and events
    - A family relationship
    - Notes and images
    """
    return """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
2 GIVN John
2 SURN Doe
1 _FSFTID G123-ABC
1 SEX M
1 BIRT
2 DATE 1 JAN 1950
2 PLAC New York, USA
1 DEAT
2 DATE 15 JUN 2020
2 PLAC Los Angeles, USA
1 OCCU Engineer
2 DATE 1975
1 NOTE @N1@
1 OBJE @O1@
1 FAMS @F1@
0 @I2@ INDI
1 NAME Jane /Smith/
2 GIVN Jane
2 SURN Smith
1 SEX F
1 BIRT
2 DATE 5 MAR 1952
2 PLAC Boston, USA
1 FAMS @F1@
0 @I3@ INDI
1 NAME Alice /Doe/
2 GIVN Alice
2 SURN Doe
1 SEX F
1 BIRT
2 DATE 10 JUL 1980
2 PLAC Chicago, USA
1 FAMC @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 MARR
2 DATE 20 JUN 1975
2 PLAC New York, USA
0 @N1@ NOTE This is a test note about John Doe.
1 CONT He was a great engineer.
0 @O1@ OBJE
1 FILE john_photo.jpg
1 TITL Photo of John
1 FORM jpeg
0 TRLR
"""


@pytest.fixture
def sample_gedcom_file(temp_dir, sample_gedcom_content):
    """Create a temporary GEDCOM file with sample content."""
    gedcom_path = temp_dir / "test.ged"
    gedcom_path.write_text(sample_gedcom_content, encoding="utf-8")
    return gedcom_path


@pytest.fixture
def sample_gedcom_cr_only(temp_dir, require_gedcom):
    """
    Create a GEDCOM file with CR-only line endings.

    This tests the line ending fix functionality.
    """
    content = "0 HEAD\r1 SOUR TestApp\r0 @I1@ INDI\r1 NAME Test /Person/\r0 TRLR\r"
    gedcom_path = temp_dir / "test_cr.ged"
    gedcom_path.write_bytes(content.encode("utf-8"))
    return gedcom_path


@pytest.fixture
def sample_gedcom_with_stories(require_gedcom):
    """
    Provide GEDCOM content with custom story tags (_STO).

    This tests the story extraction functionality used by MobileFamilyTree.
    """
    return """0 HEAD
1 SOUR MobileFamilyTree
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Robert /Johnson/
2 GIVN Robert
2 SURN Johnson
1 SEX M
1 BIRT
2 DATE 1920
1 _STO @S1@
0 @S1@ _STOR
1 TITL Life Story
1 DESC A remarkable life
1 _STS @STS1@
0 @STS1@ _STYS
1 TITL Early Years
1 TEXT Robert was born in a small town.
2 CONT He had a happy childhood.
1 OBJE @O1@
0 @O1@ OBJE
1 FILE childhood.jpg
1 TITL Childhood Photo
1 FORM jpeg
0 TRLR
"""


@pytest.fixture
def sample_gedcom_with_attributes(require_gedcom):
    """Provide GEDCOM content with physical attributes."""
    return """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Mary /Taylor/
2 GIVN Mary
2 SURN Taylor
1 SEX F
1 BIRT
2 DATE 1985
1 EYES Blue
1 HAIR Blonde
1 HEIG 170 cm
0 TRLR
"""


@pytest.fixture
def output_dir(temp_dir):
    """Create a temporary output directory for generated files."""
    out_dir = temp_dir / "output"
    out_dir.mkdir()
    return out_dir
