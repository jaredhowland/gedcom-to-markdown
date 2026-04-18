from pathlib import Path
from utils.filenames import FilenameRegistry
from index_generator import IndexGenerator


class DummyIndividual:
    def __init__(self, id_, first, last, full_name):
        self._id = id_
        self._first = first
        self._last = last
        self._full = full_name

    def get_id(self):
        return self._id

    def get_names(self):
        return (self._first, self._last)

    def get_full_name(self):
        return self._full

    def get_birth_info(self):
        return {"year": ""}

    def get_death_info(self):
        return {"date": ""}

    def get_file_name(self):
        # Return base name (would normally be produced by make_person_filename)
        return f"{self._last} {self._first}"


def test_index_generator_uses_registry_mapping(tmp_path):
    out = tmp_path
    reg = FilenameRegistry()
    reg.reserve("I1", "Mapped Name")
    # Create a dummy individual with id I1
    ind = DummyIndividual("I1", "John", "Doe", "John Doe")

    gen = IndexGenerator(out, filename_registry=reg)
    index_path = gen.generate_index([ind])

    content = index_path.read_text()
    # Expect the wiki link to use the mapped filename (without extension)
    assert "[[Mapped Name" in content
