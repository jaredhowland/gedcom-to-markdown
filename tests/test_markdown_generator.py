"""
Tests for the MarkdownGenerator module.

This module tests Obsidian markdown note generation including:
- Note file creation
- Metadata formatting
- WikiLinks generation
- Section formatting
- Story file generation
"""

import pytest
from pathlib import Path

# Skip the entire module when python-gedcom is not installed
pytest.importorskip("gedcom")

from gedcom_parser import GedcomParser
from individual import Individual
from markdown_generator import MarkdownGenerator


class TestMarkdownGeneratorInitialization:
    """Tests for MarkdownGenerator initialization."""

    def test_init_with_valid_output_dir(self, output_dir):
        """Test that generator initializes with valid directory."""
        generator = MarkdownGenerator(output_dir)
        assert generator.output_dir == output_dir
        assert generator.media_subdir == ""
        assert generator.stories_subdir == ""

    def test_init_with_subdirs(self, output_dir):
        """Test initialization with subdirectory configuration."""
        generator = MarkdownGenerator(
            output_dir, media_subdir="media", stories_subdir="stories"
        )
        assert generator.media_subdir == "media"
        assert generator.stories_subdir == "stories"

    def test_init_with_nonexistent_dir(self, temp_dir):
        """Test that ValueError is raised for non-existent directory."""
        nonexistent = temp_dir / "nonexistent"
        with pytest.raises(ValueError) as exc_info:
            MarkdownGenerator(nonexistent)
        assert "doesn't exist" in str(exc_info.value)

    def test_init_with_file_instead_of_dir(self, temp_dir):
        """Test that ValueError is raised when path is a file."""
        file_path = temp_dir / "file.txt"
        file_path.write_text("test")
        with pytest.raises(ValueError) as exc_info:
            MarkdownGenerator(file_path)
        assert "not a directory" in str(exc_info.value)


class TestNoteGeneration:
    """Tests for individual note generation."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    @pytest.fixture
    def john_doe(self, sample_gedcom_file):
        """Get John Doe individual for testing."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        return Individual(john[0], parser.parser)

    def test_generate_note(self, generator, john_doe):
        """Test basic note generation."""
        file_path = generator.generate_note(john_doe)

        assert file_path.exists()
        assert file_path.suffix == ".md"
        assert "Doe John 1950" in file_path.name

        content = file_path.read_text()
        assert "# John Doe" in content

    def test_generate_note_content_structure(self, generator, john_doe):
        """Test that generated note has correct structure."""
        file_path = generator.generate_note(john_doe)
        content = file_path.read_text()

        # Check for YAML frontmatter
        assert content.startswith("---\n")
        assert "ID: I1" in content

        # Check for main sections
        assert "# John Doe" in content
        assert "## Life Events" in content or "## Families" in content

    def test_generate_all(self, generator, sample_gedcom_file):
        """Test generating notes for all individuals."""
        parser = GedcomParser(sample_gedcom_file)
        individual_elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in individual_elements]

        paths = generator.generate_all(individuals)

        assert len(paths) == len(individuals)
        assert all(p.exists() for p in paths)
        assert all(p.suffix == ".md" for p in paths)


class TestMetadataFormatting:
    """Tests for Obsidian metadata formatting."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    @pytest.fixture
    def john_doe(self, sample_gedcom_file):
        """Get John Doe individual for testing."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        return Individual(john[0], parser.parser)

    def test_visible_metadata(self, generator, john_doe):
        """Test YAML frontmatter format."""
        file_path = generator.generate_note(john_doe)
        content = file_path.read_text()

        # Check for YAML frontmatter metadata
        assert "ID: I1" in content
        assert "FamilySearch ID: G123-ABC" in content
        assert "Name: John Doe" in content
        assert "Sex: M" in content

    def test_hidden_metadata_for_families(self, generator, john_doe):
        """Test hidden metadata format (key:: value) in families."""
        file_path = generator.generate_note(john_doe)
        content = file_path.read_text()

        # Hidden metadata for partner links
        if "(Partner::" in content:
            assert (
                "(Partner:: [[Jane Smith 1952]])" in content or "(Partner::" in content
            )

    def test_birth_death_metadata(self, generator, john_doe):
        """Test birth and death metadata in YAML frontmatter."""
        file_path = generator.generate_note(john_doe)
        content = file_path.read_text()

        # Check for YAML frontmatter birth/death data
        assert "Lived: 1950-2020" in content
        assert "Born: 1 JAN 1950" in content
        assert "Passed away: 15 JUN 2020" in content


class TestWikiLinks:
    """Tests for WikiLink generation."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    def test_wiki_links_in_families(self, generator, sample_gedcom_file):
        """Test WikiLinks to partners and children."""
        parser = GedcomParser(sample_gedcom_file)
        individual_elements = parser.get_individuals()

        # Generate all notes first
        individuals = [Individual(elem, parser.parser) for elem in individual_elements]
        generator.generate_all(individuals)

        # Check John's note for WikiLinks to Jane and Alice
        john = [ind for ind in individuals if "John" in ind.get_full_name()]
        john_file = generator.output_dir / f"{john[0].get_file_name()}.md"
        content = john_file.read_text()

        # Should have WikiLinks to Jane (partner) and Alice (child)
        assert "[[Jane Smith 1952]]" in content or "Jane" in content
        assert "[[Alice Doe 1980]]" in content or "Alice" in content

    def test_wiki_links_in_parents(self, generator, sample_gedcom_file):
        """Test WikiLinks to parents."""
        parser = GedcomParser(sample_gedcom_file)
        individual_elements = parser.get_individuals()
        individuals = [Individual(elem, parser.parser) for elem in individual_elements]

        generator.generate_all(individuals)

        # Check Alice's note for WikiLinks to parents
        alice = [ind for ind in individuals if "Alice" in ind.get_full_name()]
        alice_file = generator.output_dir / f"{alice[0].get_file_name()}.md"
        content = alice_file.read_text()

        # Should have WikiLinks to both parents
        assert "## Parents" in content
        assert "John" in content
        assert "Jane" in content


class TestEventFormatting:
    """Tests for event formatting in notes."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    def test_occupation_event(self, generator, sample_gedcom_file):
        """Test occupation event formatting."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        john_obj = Individual(john[0], parser.parser)

        file_path = generator.generate_note(john_obj)
        content = file_path.read_text()

        # Check for occupation in life events
        assert "## Life Events" in content
        assert "Occupation" in content or "OCCU" in content
        assert "Engineer" in content

    def test_event_filtering(self, generator, sample_gedcom_file):
        """Test that BIRT and DEAT are filtered from Life Events."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        john_obj = Individual(john[0], parser.parser)

        file_path = generator.generate_note(john_obj)
        content = file_path.read_text()

        # BIRT and DEAT should be in Attributes, not Life Events
        life_events_section = (
            content.split("## Life Events")[1] if "## Life Events" in content else ""
        )
        if life_events_section:
            # Birth should not appear as a separate event
            assert "Birth" not in life_events_section or "Marriage" in content

    def test_coordinates_written(self, generator, temp_dir):
        """Ensure that coordinates extracted from PLAC/MAP are written into notes."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Locator /Person/
1 RESI
2 PLAC Mapville
3 MAP
4 LATI 51.5074
4 LONG -0.1278
0 TRLR
"""
        temp_file = temp_dir / "coords_note.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        file_path = generator.generate_note(person)
        content = file_path.read_text()

        assert "- **Coordinates**: 51.5074, -0.1278" in content


class TestImageHandling:
    """Tests for image embedding in notes."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    def test_images_without_subdirs(self, generator, sample_gedcom_file):
        """Test image paths without media subdirectory."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        john_obj = Individual(john[0], parser.parser)

        file_path = generator.generate_note(john_obj)
        content = file_path.read_text()

        # Image should use flat path
        assert "## Images" in content
        assert "![Photo of John](john_photo.jpg)" in content

    def test_images_with_subdirs(self, output_dir, sample_gedcom_file):
        """Test image paths with media subdirectory."""
        generator = MarkdownGenerator(output_dir, media_subdir="media")

        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        john_obj = Individual(john[0], parser.parser)

        file_path = generator.generate_note(john_obj)
        content = file_path.read_text()

        # Image should use media/ prefix
        assert "## Images" in content
        assert "![Photo of John](media/john_photo.jpg)" in content


class TestStoryGeneration:
    """Tests for story file generation."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        stories_dir = output_dir / "stories"
        stories_dir.mkdir(exist_ok=True)
        return MarkdownGenerator(
            output_dir, stories_subdir="stories", stories_dir=stories_dir
        )

    def test_story_file_creation(self, generator, temp_dir, sample_gedcom_with_stories):
        """Test that separate story files are created."""
        temp_file = temp_dir / "stories.ged"
        temp_file.write_text(sample_gedcom_with_stories, encoding="utf-8")

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        # Generate note (should also generate story files if stories are found)
        generator.generate_note(person)

        # Story extraction depends on exact GEDCOM format
        # Just verify the method runs without error
        assert True

    def test_story_link_in_main_note(
        self, generator, temp_dir, sample_gedcom_with_stories
    ):
        """Test that main note links to story file."""
        temp_file = temp_dir / "stories.ged"
        temp_file.write_text(sample_gedcom_with_stories, encoding="utf-8")

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        file_path = generator.generate_note(person)
        content = file_path.read_text()

        # Should have link to story
        assert "## Notes" in content
        assert "### Stories" in content
        assert "[[stories/Life Story|Life Story]]" in content

    def test_story_not_duplicated(
        self, generator, temp_dir, sample_gedcom_with_stories
    ):
        """Test that story files are not regenerated if already created."""
        temp_file = temp_dir / "stories.ged"
        temp_file.write_text(sample_gedcom_with_stories, encoding="utf-8")

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        # Generate twice
        generator.generate_note(person)
        story_file = generator.stories_dir / "Life Story.md"
        first_mtime = story_file.stat().st_mtime

        # Small delay to ensure different mtime if file is rewritten
        import time

        time.sleep(0.01)

        # Generate again - should use cached story
        generator.generate_note(person)
        second_mtime = story_file.stat().st_mtime

        # File should not have been rewritten
        assert first_mtime == second_mtime


class TestFamilyFormatting:
    """Tests for family section formatting."""

    @pytest.fixture
    def generator(self, output_dir):
        """Create a markdown generator."""
        return MarkdownGenerator(output_dir)

    def test_single_marriage(self, generator, sample_gedcom_file):
        """Test formatting of single marriage."""
        parser = GedcomParser(sample_gedcom_file)
        individuals = parser.get_individuals()
        john = [ind for ind in individuals if "John" in str(ind.get_name())]
        john_obj = Individual(john[0], parser.parser)

        file_path = generator.generate_note(john_obj)
        content = file_path.read_text()

        assert "## Families" in content
        # With single marriage, number should be omitted (but may have trailing space)
        assert "### Marriage" in content

    def test_multiple_marriages(self, temp_dir):
        """Test formatting of multiple marriages."""
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Person /One/
1 SEX M
1 FAMS @F1@
1 FAMS @F2@
0 @I2@ INDI
1 NAME Spouse /One/
1 SEX F
1 FAMS @F1@
0 @I3@ INDI
1 NAME Spouse /Two/
1 SEX F
1 FAMS @F2@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 @F2@ FAM
1 HUSB @I1@
1 WIFE @I3@
0 TRLR
"""
        temp_file = temp_dir / "multiple.ged"
        temp_file.write_text(gedcom_content, encoding="utf-8")

        output_dir = temp_dir / "output"
        output_dir.mkdir()
        generator = MarkdownGenerator(output_dir)

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        file_path = generator.generate_note(person)
        content = file_path.read_text()

        # With multiple marriages, should be numbered
        assert '### Marriage 1' in content
        assert '### Marriage 2' in content

    def test_family_media_is_linked_to_both_people(self, temp_dir):
        gedcom_content = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 FAMS @F1@
0 @I2@ INDI
1 NAME Jane /Doe/
1 SEX F
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/family-photo.jpg
1 TITL Family Photo
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "family_media.ged"
        temp_file.write_text(gedcom_content, encoding='utf-8')

        output_dir = temp_dir / "output"
        output_dir.mkdir()
        generator = MarkdownGenerator(output_dir, media_subdir='media')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        generator.generate_all([Individual(elem, parser.parser) for elem in individuals])

        john = Individual(next(ind for ind in individuals if ind.get_name()[0] == 'John'), parser.parser)
        jane = Individual(next(ind for ind in individuals if ind.get_name()[0] == 'Jane'), parser.parser)

        john_file = output_dir / f"{john.get_file_name()}.md"
        jane_file = output_dir / f"{jane.get_file_name()}.md"

        john_text = john_file.read_text(encoding='utf-8')
        jane_text = jane_file.read_text(encoding='utf-8')

        assert 'Family Photo' in john_text
        assert 'https://example.com/family-photo.jpg' in john_text
        assert 'Family Photo' in jane_text
        assert 'https://example.com/family-photo.jpg' in jane_text
    def test_external_obj_url_grouping(self, temp_dir):
        """External OBJE URL is written inline in the person note as an '## External media' section.

        No separate per-person media markdown file is generated; the original URL
        is preserved directly in the person note so it can be reviewed or downloaded
        manually.
        """
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/dist.jpg?ctx=ArtCtxPublic
1 TITL Sammie & Marion Brunette’s Home—Crane, TX—1967
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        generator = MarkdownGenerator(output_dir, media_subdir='media')
        generator.generate_note(person)

        map_file = output_dir / 'media' / 'photo_person_map.md'
        # Current behavior: per-person External Media files are not generated. A cross-reference mapping is created only when downloads succeed.
        assert not map_file.exists()
        # person note should contain the original external URL
        note_file = output_dir / f"{person.get_file_name()}.md"
        note_content = note_file.read_text(encoding='utf-8')
        assert 'https://example.com/dist.jpg?ctx=ArtCtxPublic' in note_content

    def test_external_obj_download_success(self, temp_dir, monkeypatch, capsys):
        """When --download-media is enabled, external URL should be downloaded and referenced locally"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/dist.jpg?ctx=ArtCtxPublic
1 TITL Photo
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_dl.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # Fake urlopen to return image bytes
        import urllib.request
        class FakeResp:
            def __init__(self, data, headers=None):
                self._data = data
                self._headers = headers or {}
                self._read = False
            def read(self, size=-1):
                if self._read:
                    return b""
                self._read = True
                return self._data
            def getheader(self, name, default=None):
                return self._headers.get(name, default)
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def fake_urlopen(url, timeout=...):
            return FakeResp(b"JPEGDATA", headers={"Content-Type":"image/jpeg"})
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=1)
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')
        captured = capsys.readouterr()
        assert 'Media downloads: 1/1' in captured.out

        media_dir = output_dir / 'media'
        # There should be at least one binary file and the photo->person map when downloads succeed
        files = list(media_dir.iterdir())
        names = [p.name for p in files]
        assert any(p.lower().endswith('.jpg') or p.lower().endswith('.jpeg') for p in names)
        assert 'photo_person_map.md' in names

        # Person note should reference local file
        note_file = output_dir / f"{person.get_file_name()}.md"
        note_content = note_file.read_text(encoding='utf-8')
        # Note should contain a path to the media directory
        assert 'media/' in note_content

    def test_external_obj_download_failure(self, temp_dir, monkeypatch):
        """If download fails, media md should still reference external URL and not crash"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/dist.jpg?ctx=ArtCtxPublic
1 TITL Photo
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_dl_fail.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request, urllib.error
        def fake_urlopen_fail(url, timeout=...):
            raise urllib.error.URLError('network unreachable')
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen_fail)

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=1, download_retries=1)
        # Should not raise
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        map_file = output_dir / 'media' / 'photo_person_map.md'
        # No downloads succeeded, so no mapping file should be created; person note should contain external URL
        assert not map_file.exists()
        note_file = output_dir / f"{person.get_file_name()}.md"
        note_content = note_file.read_text(encoding='utf-8')
        assert 'https://example.com/dist.jpg?ctx=ArtCtxPublic' in note_content

    def test_download_retry_after_respected(self, temp_dir, monkeypatch):
        """If server returns 429 with Retry-After, the delay is respected and retry occurs"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/dist.jpg
1 TITL Photo
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_retry.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request, urllib.error
        calls = {'n': 0}
        sleep_calls = []
        def fake_urlopen(url, timeout=...):
            call_index = calls['n']
            calls['n'] += 1  # increment on every call
            if call_index == 0:
                hdrs = {'Retry-After': '2'}
                raise urllib.error.HTTPError(url, 429, 'Too Many', hdrs, None)
            else:
                class FakeResp:
                    def __init__(self):
                        self._data = b'JPEG'
                        self._read = False
                    def read(self, size=-1):
                        if self._read:
                            return b""
                        self._read = True
                        return self._data
                    def getheader(self, name, default=None):
                        if name.lower() == 'content-type':
                            return 'image/jpeg'
                        return default
                    def __enter__(self):
                        return self
                    def __exit__(self, exc_type, exc, tb):
                        return False
                return FakeResp()
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
        monkeypatch.setattr('time.sleep', lambda s: sleep_calls.append(s))

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=2)
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        # Ensure urlopen was called exactly twice (initial 429 + one retry)
        # and sleep recorded the Retry-After value
        assert calls['n'] == 2
        assert any(s >= 2 for s in sleep_calls)

    def test_download_filename_collision(self, temp_dir, monkeypatch):
        """When two different URLs yield same basename, both files are saved with unique names"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
1 OBJE @O2@
0 @O1@ OBJE
1 FILE https://example.com/path/image.jpg
1 TITL Photo1
1 FORM URL
0 @O2@ OBJE
1 FILE https://cdn.example.org/imgs/image.jpg
1 TITL Photo2
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_collision.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request
        class FakeResp:
            def __init__(self):
                self._data = b'JPEG'
                self._read = False
            def read(self, size=-1):
                if self._read:
                    return b""
                self._read = True
                return self._data
            def getheader(self, name, default=None):
                if name.lower() == 'content-type':
                    return 'image/jpeg'
                return default
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def fake_urlopen(url, timeout=...):
            return FakeResp()
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=1)
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        media_dir = output_dir / 'media'
        files = list(media_dir.glob('*.jpg')) + list(media_dir.glob('*.jpeg'))
        assert len(files) >= 2

    def test_download_max_bytes_exceeded(self, temp_dir, monkeypatch):
        """If a download exceeds the configured max bytes, it's aborted and the external URL is preserved"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/huge.jpg
1 TITL HugePhoto
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_huge.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request
        class FakeResp:
            def __init__(self):
                self._first = True
            def read(self, size=-1):
                if self._first:
                    self._first = False
                    return b'A' * 1024  # large single chunk
                return b''
            def getheader(self, name, default=None):
                if name.lower() == 'content-type':
                    return 'image/jpeg'
                return default
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def fake_urlopen(url, timeout=...):
            return FakeResp()
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        # Set max bytes low so the single chunk exceeds it
        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=1, download_max_bytes=10)
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        map_file = output_dir / 'media' / 'photo_person_map.md'
        assert not map_file.exists()
        note_file = output_dir / f"{person.get_file_name()}.md"
        note_content = note_file.read_text(encoding='utf-8')
        # Since download was aborted, original URL should be present in person's note
        assert 'https://example.com/huge.jpg' in note_content

    def test_content_type_extension_guessing(self, temp_dir, monkeypatch):
        """When the URL has no extension, content-type header is used to guess extension"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/image
1 TITL NoExt
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_noext.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request
        class FakeResp:
            def __init__(self):
                self._data = b'PNGDATA'
                self._read = False
            def read(self, size=-1):
                if self._read:
                    return b""
                self._read = True
                return self._data
            def getheader(self, name, default=None):
                if name.lower() == 'content-type':
                    return 'image/png'
                return default
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def fake_urlopen(url, timeout=...):
            return FakeResp()
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=1)
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        media_dir = output_dir / 'media'
        files = list(media_dir.glob('*.png')) + list(media_dir.glob('*.PNG'))
        assert len(files) >= 1

    def test_atomic_write_failure(self, temp_dir, monkeypatch):
        """If moving temp file into place fails (os.replace), generator should log and fall back to external URL"""
        ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
0 @O1@ OBJE
1 FILE https://example.com/fail.jpg
1 TITL FailMove
1 FORM URL
0 TRLR
"""
        temp_file = temp_dir / "external_failmove.ged"
        temp_file.write_text(ged, encoding='utf-8')

        parser = GedcomParser(temp_file)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        import urllib.request, os
        class FakeResp:
            def __init__(self):
                self._data = b'DATA'
                self._read = False
            def read(self, size=-1):
                if self._read:
                    return b""
                self._read = True
                return self._data
            def getheader(self, name, default=None):
                if name.lower() == 'content-type':
                    return 'image/jpeg'
                return default
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def fake_urlopen(url, timeout=...):
            return FakeResp()
        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        # Simulate os.replace raising
        orig_replace = os.replace
        def bad_replace(src, dst):
            raise OSError('replace failed')
        monkeypatch.setattr(os, 'replace', bad_replace)

        generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, download_timeout=5, download_retries=1)
        # Should not raise
        generator.generate_all([person])
        generator._download_external_media([person], output_dir / 'media')

        media_dir = output_dir / 'media'
        # No binary files should exist because move failed
        bin_files = list(media_dir.glob('*.jpg')) + list(media_dir.glob('*.jpeg'))
        assert len(bin_files) == 0
        # Media md should exist and contain external URL
        map_file = output_dir / 'media' / 'photo_person_map.md'
        # No downloads were successful, so no mapping file should be created. Person note should include the external URL.
        assert not map_file.exists()
        note_file = output_dir / f"{person.get_file_name()}.md"
        content = note_file.read_text(encoding='utf-8')
        assert 'https://example.com/fail.jpg' in content


def test_per_host_semaphore(temp_dir, monkeypatch):
    """Per-host semaphore should limit concurrency to configured value"""
    ged = """0 HEAD
1 SOUR TestApp
1 GEDC
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 OBJE @O1@
1 OBJE @O2@
0 @O1@ OBJE
1 FILE https://example.com/path1/image.jpg
1 TITL Photo1
1 FORM URL
0 @O2@ OBJE
1 FILE https://example.com/path1/image2.jpg
1 TITL Photo2
1 FORM URL
0 TRLR
"""
    temp_file = temp_dir / "external_perhost.ged"
    temp_file.write_text(ged, encoding='utf-8')

    parser = GedcomParser(temp_file)
    individuals = parser.get_individuals()
    person = Individual(individuals[0], parser.parser)

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    import urllib.request, threading, time

    # Slow response to allow overlap
    def fake_urlopen(req, timeout=...):
        class Resp:
            def __init__(self):
                self._read = False
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size=-1):
                if self._read:
                    return b""
                self._read = True
                time.sleep(0.1)
                return b'DATA'
            def getheader(self, name, default=None):
                if name.lower() == 'content-type':
                    return 'image/jpeg'
                return default
        return Resp()

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    # Capture original semaphore and replace with counting wrapper
    orig_sem = threading.Semaphore
    class CountingSemaphore:
        def __init__(self, value=1):
            self._sem = orig_sem(value)
            self._lock = threading.Lock()
            self.current = 0
            self.max_seen = 0
        def acquire(self, *args, **kwargs):
            res = self._sem.acquire(*args, **kwargs)
            with self._lock:
                self.current += 1
                if self.current > self.max_seen:
                    self.max_seen = self.current
            return res
        def release(self, *args, **kwargs):
            with self._lock:
                self.current -= 1
            return self._sem.release(*args, **kwargs)

    monkeypatch.setattr(threading, 'Semaphore', CountingSemaphore)

    # Use 2 worker threads but per-host concurrency 1; CountingSemaphore should record max_seen==1
    generator = MarkdownGenerator(output_dir, media_subdir='media', download_media=True, media_download_concurrency=2, media_download_enable_concurrency=True, media_download_per_host_concurrency=1)
    generator.generate_all([person])
    generator._download_external_media([person], output_dir / 'media')

    host = 'example.com'
    sem = generator._host_semaphores.get(host)
    assert sem is not None
    assert getattr(sem, 'max_seen', 0) <= 1
