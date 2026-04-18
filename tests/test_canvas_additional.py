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
        return self._families

    def get_families_as_child(self):
        return self._families_as_child


def _find_node_by_name(nodes, first, last):
    key = f"[[{last} {first}]"
    for n in nodes:
        text = n.get("text") or ""
        if f"[[{last} {first}]" in text or f"[[{last} {first} " in text:
            return n
    # fallback: match by first or last
    for n in nodes:
        text = n.get("text") or ""
        if first in text and last in text:
            return n
    return None


def test_spouse_and_sibling_positions(tmp_path):
    # Build parents for spouse
    p1 = DummyIndividual("@P1@", "ParentA", "Parent", gender="M")
    p2 = DummyIndividual("@P2@", "ParentB", "Parent", gender="F")

    # Spouse and sibling as children of p1+p2
    spouse = DummyIndividual("@S1@", "Spouse", "Smith", gender="F")
    sibling = DummyIndividual("@S2@", "Sibling", "Smith", gender="M")

    # Parents reference children
    p1._families = [{"partner": p2, "children": [spouse, sibling]}]
    p2._families = [{"partner": p1, "children": [spouse, sibling]}]

    # spouse and sibling point back to parents
    spouse._families_as_child = [
        {"father": p1.get_pointer(), "mother": p2.get_pointer()}
    ]
    sibling._families_as_child = [
        {"father": p1.get_pointer(), "mother": p2.get_pointer()}
    ]

    # Root person married to spouse
    root = DummyIndividual("@R@", "Root", "Rootson", gender="M")
    root._families = [{"partner": spouse, "children": []}]
    spouse._families.append({"partner": root, "children": []})

    individuals = [p1, p2, spouse, sibling, root]
    cg = CanvasGenerator(individuals, str(tmp_path))
    path = cg.generate_canvas(root.get_pointer(), canvas_filename="spouse_sib.canvas")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = data["nodes"]

    spouse_node = _find_node_by_name(nodes, "Spouse", "Smith")
    sibling_node = _find_node_by_name(nodes, "Sibling", "Smith")

    assert spouse_node is not None and sibling_node is not None
    # Expect same x coordinate (stacked vertically)
    assert spouse_node["x"] == sibling_node["x"]
    # Ensure vertical separation at least the image height
    assert abs(spouse_node["y"] - sibling_node["y"]) >= cg.IMAGE_HEIGHT


def test_multi_level_ancestors_positions(tmp_path):
    # Grandparents
    gp1 = DummyIndividual("@G1@", "Gpa", "Line", gender="M")
    gm1 = DummyIndividual("@G2@", "Gma", "Line", gender="F")

    # Parent
    parent = DummyIndividual("@P@", "Parent", "Line", gender="F")
    parent._families_as_child = [
        {"father": gp1.get_pointer(), "mother": gm1.get_pointer()}
    ]
    gp1._families = [{"partner": gm1, "children": [parent]}]
    gm1._families = [{"partner": gp1, "children": [parent]}]

    # Root is child of parent
    root = DummyIndividual("@R2@", "Root2", "Line", gender="M")
    root._families_as_child = [{"father": None, "mother": parent.get_pointer()}]
    parent._families = [{"partner": None, "children": [root]}]

    individuals = [gp1, gm1, parent, root]
    cg = CanvasGenerator(individuals, str(tmp_path))
    path = cg.generate_canvas(root.get_pointer(), canvas_filename="multi_anc.canvas")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = data["nodes"]

    root_node = _find_node_by_name(nodes, "Root2", "Line")
    parent_node = _find_node_by_name(nodes, "Parent", "Line")
    gp_node = _find_node_by_name(nodes, "Gpa", "Line")

    assert root_node and parent_node and gp_node
    # Ancestors should be to the right (higher x)
    assert parent_node["x"] > root_node["x"]
    assert gp_node["x"] > parent_node["x"]


def test_image_node_rendering(tmp_path):
    # Individual with image
    ind = DummyIndividual(
        "@IIMG@",
        "Im",
        "Age",
        gender="F",
        images=[{"file": "/media/pic.jpg", "title": "pic", "format": "jpg"}],
    )
    cg = CanvasGenerator([ind], str(tmp_path))
    path = cg.generate_canvas(ind.get_pointer(), canvas_filename="img.canvas")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = data["nodes"]
    node = _find_node_by_name(nodes, "Im", "Age")
    assert node is not None
    assert "![Image](/media/pic.jpg)" in node["text"]
    assert node["height"] == cg.IMAGE_HEIGHT
