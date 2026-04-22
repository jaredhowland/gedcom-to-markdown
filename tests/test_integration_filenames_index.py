from pathlib import Path
from utils.filenames import FilenameRegistry
from markdown_generator import MarkdownGenerator
from index_generator import IndexGenerator


class DummyIndividual:
    def __init__(self, id_, first, last, full_name, birth_year=""):
        self._id = id_
        self._first = first
        self._last = last
        self._full = full_name
        self._birth_year = birth_year

    def get_id(self):
        return self._id

    def get_names(self):
        return (self._first, self._last)

    def get_full_name(self):
        return self._full

    def get_birth_info(self):
        return {"year": self._birth_year}

    def get_death_info(self):
        return {"date": ""}

    def get_file_name(self):
        # Base filename used by registry (mimics make_person_filename)
        parts = []
        if self._last:
            parts.append(self._last)
        if self._first:
            parts.append(self._first)
        if self._birth_year:
            parts.append(self._birth_year)
        return " ".join(parts) or self._id

    # Provide minimal methods expected by MarkdownGenerator; return empty values
    def get_gender(self):
        return "U"

    def get_attributes(self):
        return {}

    def get_events(self):
        return []

    def get_families(self):
        return []

    def get_parents(self):
        return []

    def get_children(self):
        return []

    def get_images(self):
        return []

    def get_notes(self):
        return []

    def get_sources(self):
        return []


def test_markdown_and_index_integration(tmp_path):
    out = tmp_path
    reg = FilenameRegistry()

    # Two individuals with same base name should get unique reserved names
    ind1 = DummyIndividual("I1", "John", "Doe", "John Doe", "1950")
    ind2 = DummyIndividual("I2", "John", "Doe", "John Doe", "1950")

    mg = MarkdownGenerator(out, filename_registry=reg)
    f1 = mg.generate_note(ind1)
    f2 = mg.generate_note(ind2)

    mapping = reg.mapping()

    # Files should be created with names from the registry
    assert (out / (mapping["I1"] + ".md")).exists()
    assert (out / (mapping["I2"] + ".md")).exists()

    # Generate index using the same registry so links match filenames
    ig = IndexGenerator(out, filename_registry=reg)
    index_path = ig.generate_index([ind1, ind2])
    content = index_path.read_text()

    assert f"[[{mapping['I1']}" in content
    assert f"[[{mapping['I2']}" in content
