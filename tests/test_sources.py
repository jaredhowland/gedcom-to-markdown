import pytest
from pathlib import Path

from gedcom_parser import GedcomParser
from individual import Individual
from markdown_generator import MarkdownGenerator


def _make_output_dir(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


class TestSourcesSection:
    def test_sources_happy_path_with_publ_and_title(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @S1@ SOUR
1 TITL Overland    Travels  Pioneer   Detail
1 PUBL http://history.example/pioneer?id=6262
0 @I1@ INDI
1 NAME John /Doe/
1 SOUR @S1@
0 TRLR
"""
        f = tmp_path / "sources.ged"
        f.write_text(gedcom, encoding='utf-8')

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        note = gen.generate_note(person)
        content = note.read_text()

        assert '## Sources' in content
        # Whitespace in title should be collapsed
        assert '1. [Overland Travels Pioneer Detail](http://history.example/pioneer?id=6262)' in content
        # Also an Index file should be created in sources/Index.md
        index = out / 'sources' / 'Index.md'
        assert index.exists()
        idx_content = index.read_text()
        assert '[Overland Travels Pioneer Detail](http://history.example/pioneer?id=6262)' in idx_content

    def test_sources_title_only_no_publ(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @S2@ SOUR
1 TITL Local Archive Record
0 @I1@ INDI
1 NAME Jane /Smith/
1 SOUR @S2@
0 TRLR
"""
        f = tmp_path / "sources2.ged"
        f.write_text(gedcom, encoding='utf-8')

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        note = gen.generate_note(person)
        content = note.read_text()

        assert '## Sources' in content
        assert '1. Local Archive Record' in content

    def test_sources_publ_but_no_title_uses_url_as_text(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @S3@ SOUR
1 PUBL https://example.org/doc/123
0 @I1@ INDI
1 NAME Alice /Doe/
1 SOUR @S3@
0 TRLR
"""
        f = tmp_path / "sources3.ged"
        f.write_text(gedcom, encoding='utf-8')

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        note = gen.generate_note(person)
        content = note.read_text()

        assert '## Sources' in content
        assert '1. [https://example.org/doc/123](https://example.org/doc/123)' in content
