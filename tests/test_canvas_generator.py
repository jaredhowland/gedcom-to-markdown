from pathlib import Path
import json

from src.canvas_generator import CanvasGenerator


class DummyIndividual:
    def __init__(
        self,
        pointer,
        first,
        last,
        gender="M",
        events=None,
        families=None,
        families_as_child=None,
        images=None,
    ):
        self._pointer = pointer
        self._first = first
        self._last = last
        self._gender = gender
        self._events = events or []
        self._families = families or []
        self._families_as_child = families_as_child or []
        self._images = images or []

    def get_pointer(self):
        return self._pointer

    def get_gender(self):
        return self._gender

    def get_names(self):
        return (self._first, self._last)

    def get_events(self):
        return self._events

    def get_images(self):
        return self._images

    def get_families(self):
        # Return a list of family dicts: {'partner': Individual, 'children': [Individual], ...}
        return self._families

    def get_families_as_child(self):
        # Return a list of family dicts: {'father': pointer, 'mother': pointer}
        return self._families_as_child


def make_family():
    # Parent A and B and a child
    parent_a = DummyIndividual("@I1@", "Alice", "Anderson", gender="F")
    parent_b = DummyIndividual("@I2@", "Bob", "Anderson", gender="M")
    child = DummyIndividual(
        "@I3@",
        "Charlie",
        "Anderson",
        gender="M",
        events=[{"type": "BIRT", "date": "1 JAN 2000"}],
    )

    # parent_a has family with partner parent_b and child
    parent_a._families = [
        {
            "partner": parent_b,
            "children": [child],
            "marriage_date": "1 JAN 1995",
            "marriage_place": "Town",
        }
    ]
    # parent_b mirror
    parent_b._families = [
        {
            "partner": parent_a,
            "children": [child],
            "marriage_date": "1 JAN 1995",
            "marriage_place": "Town",
        }
    ]

    # Child has families_as_child pointing to parents
    child._families_as_child = [
        {"father": parent_b.get_pointer(), "mother": parent_a.get_pointer()}
    ]

    return parent_a, parent_b, child


def test_generate_canvas_basic(tmp_path):
    parent_a, parent_b, child = make_family()
    individuals = [parent_a, parent_b, child]

    cg = CanvasGenerator(individuals, str(tmp_path))
    canvas_file = tmp_path / "family.canvas"

    path = cg.generate_canvas(parent_a.get_pointer(), canvas_filename="family.canvas")
    assert Path(path).exists()

    # Validate JSON structure
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert "nodes" in data and "edges" in data
    assert len(data["nodes"]) >= 3
    # Ensure wiki links include family filenames (Last First Year for child)
    child_filename = "Anderson Charlie 2000"
    found = any(child_filename in node.get("text", "") for node in data["nodes"])
    assert found


def test_generate_canvas_with_disconnected(tmp_path):
    parent_a, parent_b, child = make_family()
    disconnected = DummyIndividual("@I4@", "Dana", "Doe", gender="F")

    individuals = [parent_a, parent_b, child, disconnected]
    cg = CanvasGenerator(individuals, str(tmp_path))
    path = cg.generate_canvas(parent_a.get_pointer(), canvas_filename="family2.canvas")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Expect at least one disconnected node created for Dana
    assert any(
        "Dana" in (n.get("text") or "") or "Doe" in (n.get("text") or "")
        for n in data["nodes"]
    )
