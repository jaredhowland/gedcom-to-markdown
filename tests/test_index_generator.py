"""
Tests for the IndexGenerator module.

This module tests index file generation including:
- Alphabetical sorting
- Grouping by last name initial
- WikiLink formatting
- Life span formatting
- Subdirectory path handling
"""

import pytest
from pathlib import Path

from gedcom_parser import GedcomParser
from individual import Individual
from index_generator import IndexGenerator


class TestIndexGeneratorInitialization:
    """Tests for IndexGenerator initialization."""

    def test_init_with_output_dir(self, output_dir):
        """Test basic initialization."""
        generator = IndexGenerator(output_dir)
        assert generator.output_dir == output_dir
        assert generator.people_subdir == ""

    def test_init_with_people_subdir(self, output_dir):
        """Test initialization with people subdirectory."""
        generator = IndexGenerator(output_dir, people_subdir="people")
        assert generator.people_subdir == "people"


class TestIndexGeneration:
    """Tests for index file generation."""

    @pytest.fixture
    def individuals(self, sample_gedcom_file):
        """Get individuals from sample GEDCOM."""
        parser = GedcomParser(sample_gedcom_file)
        elements = parser.get_individuals()
        return [Individual(elem, parser.parser) for elem in elements]

    def test_generate_index(self, output_dir, individuals):
        """Test basic index generation."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)

        assert index_path.exists()
        assert index_path.name == "Index.md"

        content = index_path.read_text()
        assert "# Family Tree Index" in content
        assert f"Total individuals: {len(individuals)}" in content

    def test_custom_index_filename(self, output_dir, individuals):
        """Test index generation with custom filename."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals, index_filename="MyIndex.md")

        assert index_path.exists()
        assert index_path.name == "MyIndex.md"

    def test_index_content_has_individuals(self, output_dir, individuals):
        """Test that all individuals are included in index."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        # Check for presence of individuals
        assert "John" in content or "Doe" in content
        assert "Jane" in content or "Smith" in content
        assert "Alice" in content


class TestAlphabeticalSorting:
    """Tests for alphabetical sorting by last name."""

    @pytest.fixture
    def mixed_individuals(self, temp_dir):
        """Create individuals with various last names."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Zoe /Anderson/
1 SEX F
0 @I2@ INDI
1 NAME Alice /Smith/
1 SEX F
0 @I3@ INDI
1 NAME Bob /Brown/
1 SEX M
0 @I4@ INDI
1 NAME Charlie /Anderson/
1 SEX M
0 TRLR
"""
        temp_file = temp_dir / "mixed.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        return [Individual(elem, parser.parser) for elem in elements]

    def test_sorting_by_last_name(self, output_dir, mixed_individuals):
        """Test that individuals are sorted by last name."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(mixed_individuals)
        content = index_path.read_text()

        # Find positions of last names in content
        anderson_pos = content.find("Anderson")
        brown_pos = content.find("Brown")
        smith_pos = content.find("Smith")

        # Anderson should come before Brown, Brown before Smith
        assert anderson_pos < brown_pos < smith_pos

    def test_sorting_by_first_name_within_last_name(
        self, output_dir, mixed_individuals
    ):
        """Test that individuals with same last name are sorted by first name."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(mixed_individuals)
        content = index_path.read_text()

        # Among Andersons, Charlie should come before Zoe
        lines = content.split("\n")
        anderson_lines = [line for line in lines if "Anderson" in line]

        # Should be ordered: Charlie, Zoe
        assert len(anderson_lines) >= 2
        charlie_idx = next(
            i for i, line in enumerate(anderson_lines) if "Charlie" in line
        )
        zoe_idx = next(i for i, line in enumerate(anderson_lines) if "Zoe" in line)
        assert charlie_idx < zoe_idx


class TestLetterGrouping:
    """Tests for grouping by last name initial."""

    @pytest.fixture
    def varied_individuals(self, temp_dir):
        """Create individuals with various last name initials."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Alice /Adams/
0 @I2@ INDI
1 NAME Bob /Brown/
0 @I3@ INDI
1 NAME Charlie /Carter/
0 @I4@ INDI
1 NAME David /Davis/
0 TRLR
"""
        temp_file = temp_dir / "varied.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        return [Individual(elem, parser.parser) for elem in elements]

    def test_letter_headers(self, output_dir, varied_individuals):
        """Test that letter headers are created for each initial."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(varied_individuals)
        content = index_path.read_text()

        # Should have headers for A, B, C, D
        assert "## A" in content
        assert "## B" in content
        assert "## C" in content
        assert "## D" in content

    def test_individuals_under_correct_letter(self, output_dir, varied_individuals):
        """Test that individuals appear under correct letter header."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(varied_individuals)
        content = index_path.read_text()

        # Split by letter headers
        sections = content.split("## ")

        # Find section A and verify Adams is in it
        a_section = next(s for s in sections if s.startswith("A\n"))
        assert "Adams" in a_section

        # Find section B and verify Brown is in it
        b_section = next(s for s in sections if s.startswith("B\n"))
        assert "Brown" in b_section

    def test_no_last_name_handling(self, temp_dir, output_dir):
        """Test handling of individuals without last names."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Madonna //
0 TRLR
"""
        temp_file = temp_dir / "no_last.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in elements]

        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        # Should have # header for individuals without last name
        assert "## #" in content


class TestWikiLinkFormatting:
    """Tests for WikiLink formatting in index."""

    @pytest.fixture
    def individuals_with_dates(self, sample_gedcom_file):
        """Get individuals with birth/death dates."""
        parser = GedcomParser(sample_gedcom_file)
        elements = parser.get_individuals()
        return [Individual(elem, parser.parser) for elem in elements]

    def test_wiki_links_without_subdirs(self, output_dir, individuals_with_dates):
        """Test WikiLink format without subdirectories."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals_with_dates)
        content = index_path.read_text()

        # Should have simple WikiLinks
        assert "[[Doe John 1950]]" in content or "[[" in content

    def test_wiki_links_with_subdirs(self, output_dir, individuals_with_dates):
        """Test WikiLink format with people subdirectory."""
        generator = IndexGenerator(output_dir, people_subdir="people")
        index_path = generator.generate_index(individuals_with_dates)
        content = index_path.read_text()

        # Should have WikiLinks with people/ prefix
        assert "[[people/Doe John 1950" in content or "[[people/" in content


class TestLifeSpanFormatting:
    """Tests for life span formatting."""

    @pytest.fixture
    def individuals_with_dates(self, sample_gedcom_file):
        """Get individuals with birth/death dates."""
        parser = GedcomParser(sample_gedcom_file)
        elements = parser.get_individuals()
        return [Individual(elem, parser.parser) for elem in elements]

    def test_life_span_with_both_dates(self, output_dir, individuals_with_dates):
        """Test life span when both birth and death dates are available."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals_with_dates)
        content = index_path.read_text()

        # Death date "15 JUN 2020" should extract year "2020"
        assert "(1950-2020)" in content

    def test_life_span_with_only_birth(self, temp_dir, output_dir):
        """Test life span with only birth date."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Living /Person/
1 BIRT
2 DATE 1990
0 TRLR
"""
        temp_file = temp_dir / "living.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in elements]

        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        # Should show (1990-)
        assert "(1990-)" in content

    def test_no_life_span_without_dates(self, temp_dir, output_dir):
        """Test that no life span is shown when dates are missing."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Unknown /Person/
0 TRLR
"""
        temp_file = temp_dir / "no_dates.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in elements]

        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        # Should not have parentheses for life span
        lines = [line for line in content.split("\n") if "Unknown" in line]
        assert len(lines) > 0
        # Line should end with WikiLink, not life span
        assert not lines[0].strip().endswith(")")

    def test_death_year_extraction_from_day_first_format(self, temp_dir, output_dir):
        """Test that death year is correctly extracted when date starts with day."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Test /Person/
1 BIRT
2 DATE 1950
1 DEAT
2 DATE 15 JUN 2020
0 TRLR
"""
        temp_file = temp_dir / "day_first.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in elements]

        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        # Should show (1950-2020), not (1950-15 J)
        assert "(1950-2020)" in content
        assert "15 J" not in content


class TestIndexStatistics:
    """Tests for index statistics and metadata."""

    def test_total_count(self, output_dir, sample_gedcom_file):
        """Test that total individual count is displayed."""
        parser = GedcomParser(sample_gedcom_file)
        elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in elements]

        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index(individuals)
        content = index_path.read_text()

        assert f"Total individuals: {len(individuals)}" in content

    def test_empty_index(self, output_dir):
        """Test index generation with no individuals."""
        generator = IndexGenerator(output_dir)
        index_path = generator.generate_index([])
        content = index_path.read_text()

        assert "Total individuals: 0" in content
        assert "# Family Tree Index" in content
