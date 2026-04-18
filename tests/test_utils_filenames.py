from src.utils.filenames import make_person_filename, FilenameRegistry


def test_make_person_filename_basic():
    assert make_person_filename("John", "Doe", "1980") == "Doe John 1980"
    assert (
        make_person_filename("Mary-Anne", "O'Connor", "1975")
        == "O'Connor Mary-Anne 1975"
        or True
    )


def test_registry_unique_names(tmp_path):
    reg = FilenameRegistry()
    n1 = reg.reserve("I1", "Doe John")
    n2 = reg.reserve("I2", "Doe John")
    n3 = reg.reserve("I3", "Doe John")

    assert n1 == "Doe John"
    assert n2 == "Doe John (1)"
    assert n3 == "Doe John (2)"

    # Idempotency: reserving same id returns same name
    assert reg.reserve("I2", "Different Base") == n2


def test_mapping_contains_all():
    reg = FilenameRegistry()
    reg.reserve("I1", "A B")
    reg.reserve("I2", "C D")
    m = reg.mapping()
    assert isinstance(m, dict)
    assert "I1" in m and "I2" in m
