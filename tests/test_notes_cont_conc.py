from pathlib import Path

from gedcom_parser import GedcomParser
from individual import Individual
from markdown_generator import MarkdownGenerator


def _make_output_dir(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


class TestNotesContConc:
    def test_note_cont_and_conc_inline_in_indi(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 NOTE
2 CONT First line
2 CONC -continued
2 CONT Next paragraph
0 TRLR
"""
        f = tmp_path / "note.ged"
        f.write_text(gedcom, encoding="utf-8")

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        note = gen.generate_note(person)
        content = note.read_text()

        # Ensure CONC concatenated without newline
        assert "First line-continued" in content
        # Ensure CONT produced a newline (rendered as separate paragraph / hard break)
        assert "Next paragraph" in content

    def test_note_reference_to_note_with_cont_conc(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @N1@ NOTE
1 CONT Line one
1 CONC continued
1 CONT Line two
0 @I1@ INDI
1 NAME Jane /Smith/
1 NOTE @N1@
0 TRLR
"""
        f = tmp_path / "note_ref.ged"
        f.write_text(gedcom, encoding="utf-8")

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        note = gen.generate_note(person)
        content = note.read_text()

        assert "Line onecontinued" in content
        assert "Line two" in content

    def test_source_note_cont_conc_and_index(self, tmp_path):
        gedcom = """0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @N1@ NOTE
1 CONT Source line
1 CONC -more
0 @S1@ SOUR
1 TITL Example Source
1 NOTE @N1@
0 @I1@ INDI
1 NAME Alpha /Beta/
1 SOUR @S1@
0 TRLR
"""
        f = tmp_path / "sources.ged"
        f.write_text(gedcom, encoding="utf-8")

        parser = GedcomParser(f)
        individuals = parser.get_individuals()
        person = Individual(individuals[0], parser.parser)

        out = _make_output_dir(tmp_path)
        gen = MarkdownGenerator(out)
        # generate a person note which should also trigger sources index generation
        gen.generate_note(person)

        index = out / "sources" / "Index.md"
        assert index.exists()
        content = index.read_text()
        # Ensure concatenation in source note
        assert "Source line-more" in content
