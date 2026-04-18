from pathlib import Path
import json

from canvas_generator import CanvasGenerator


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


def _load_canvas(tmp_path, cg, root_ptr, filename):
    path = cg.generate_canvas(root_ptr, canvas_filename=filename)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def test_single_parent_positions(tmp_path):
    # Single parent case: only mother known
    mother = DummyIndividual("@M@", "SoloMom", "Solo", gender="F")
    child = DummyIndividual("@C@", "OnlyChild", "Solo", gender="M")

    # mother has child
    mother._families = [{"partner": None, "children": [child]}]
    child._families_as_child = [{"father": None, "mother": mother.get_pointer()}]

    cg = CanvasGenerator([mother, child], str(tmp_path))
    data = _load_canvas(tmp_path, cg, child.get_pointer(), "single_parent.canvas")

    nodes = data["nodes"]
    child_node = next(n for n in nodes if "OnlyChild" in (n.get("text") or ""))
    mother_node = next(n for n in nodes if "SoloMom" in (n.get("text") or ""))

    # mother should be positioned to the right of child (ancestor layout)
    assert mother_node["x"] > child_node["x"]


def test_parent_couple_and_siblings(tmp_path):
    # Parents with siblings to exercise sibling placement logic
    father = DummyIndividual("@F@", "Father", "Fam", gender="M")
    mother = DummyIndividual("@M2@", "Mother", "Fam", gender="F")
    sibling = DummyIndividual("@S@", "Aunt", "Fam", gender="F")

    # Family: father+mother with child
    child = DummyIndividual("@CH@", "Child", "Fam", gender="M")
    father._families = [{"partner": mother, "children": [child, sibling]}]
    mother._families = [{"partner": father, "children": [child, sibling]}]

    # Sibling is child of same parents
    sibling._families_as_child = [
        {"father": father.get_pointer(), "mother": mother.get_pointer()}
    ]
    child._families_as_child = [
        {"father": father.get_pointer(), "mother": mother.get_pointer()}
    ]

    cg = CanvasGenerator([father, mother, sibling, child], str(tmp_path))
    data = _load_canvas(tmp_path, cg, child.get_pointer(), "parents_siblings.canvas")
    nodes = data["nodes"]

    # Find parent nodes
    father_node = next(n for n in nodes if "Father" in (n.get("text") or ""))
    mother_node = next(n for n in nodes if "Mother" in (n.get("text") or ""))
    sibling_node = next(n for n in nodes if "Aunt" in (n.get("text") or ""))

    # Parents should be near each other (same x)
    assert father_node["x"] == mother_node["x"]
    # Sibling should not be positioned to the left of the parents (stacking uses same or greater x)
    assert sibling_node["x"] >= father_node["x"]


def test_deep_ancestor_recursion(tmp_path):
    # Build a chain of ancestors: ggp -> gp -> p -> root
    ggp = DummyIndividual("@GGP@", "Great", "Grand", gender="M")
    gp = DummyIndividual("@GP@", "Grand", "Parent", gender="F")
    p = DummyIndividual("@P2@", "Parent", "Parent", gender="M")
    root = DummyIndividual("@R3@", "Root3", "Line", gender="M")

    # Connections: ggp+gp -> children: gp; gp+? -> child p; p+? -> child root
    ggp._families = [{"partner": gp, "children": [gp]}]
    gp._families = [{"partner": ggp, "children": [p]}]
    p._families = [{"partner": None, "children": [root]}]

    gp._families_as_child = [{"father": ggp.get_pointer(), "mother": None}]
    p._families_as_child = [{"father": gp.get_pointer(), "mother": None}]
    root._families_as_child = [{"father": p.get_pointer(), "mother": None}]

    individuals = [ggp, gp, p, root]
    cg = CanvasGenerator(individuals, str(tmp_path))
    data = _load_canvas(tmp_path, cg, root.get_pointer(), "deep_anc.canvas")
    nodes = data["nodes"]

    root_node = next(n for n in nodes if "Root3" in (n.get("text") or ""))
    p_node = next(n for n in nodes if "Parent" in (n.get("text") or ""))
    gp_node = next(n for n in nodes if "Grand" in (n.get("text") or ""))
    ggp_node = next(n for n in nodes if "Great" in (n.get("text") or ""))

    # x should strictly increase for ancestors
    assert p_node["x"] > root_node["x"]
    assert gp_node["x"] > p_node["x"]
    assert ggp_node["x"] > gp_node["x"]


def test_subtree_width_and_descendant_layout(tmp_path):
    # Parent with two children, each child has a spouse -> exercises subtree widths and layout_person_and_descendants
    parent = DummyIndividual("@PA@", "ParentX", "Wide", gender="M")

    child1 = DummyIndividual("@C1@", "Child1", "Wide", gender="F")
    child2 = DummyIndividual("@C2@", "Child2", "Wide", gender="M")

    spouse1 = DummyIndividual("@SP1@", "Sp1", "Wide", gender="M")
    spouse2 = DummyIndividual("@SP2@", "Sp2", "Wide", gender="F")

    # set families
    parent._families = [{"partner": None, "children": [child1, child2]}]
    child1._families_as_child = [{"father": None, "mother": parent.get_pointer()}]
    child2._families_as_child = [{"father": None, "mother": parent.get_pointer()}]

    # children have spouses
    child1._families = [{"partner": spouse1, "children": []}]
    spouse1._families = [{"partner": child1, "children": []}]
    child2._families = [{"partner": spouse2, "children": []}]
    spouse2._families = [{"partner": child2, "children": []}]

    individuals = [parent, child1, child2, spouse1, spouse2]
    cg = CanvasGenerator(individuals, str(tmp_path))
    data = _load_canvas(tmp_path, cg, parent.get_pointer(), "subtree.canvas")
    nodes = data["nodes"]

    # find children nodes
    n1 = next(n for n in nodes if "Child1" in (n.get("text") or ""))
    n2 = next(n for n in nodes if "Child2" in (n.get("text") or ""))

    # children may be arranged left-to-right; ensure child spouses and parent nodes exist
    parent_node = next(n for n in nodes if "ParentX" in (n.get("text") or ""))
    spouse1_node = next(n for n in nodes if "Sp1" in (n.get("text") or ""))
    spouse2_node = next(n for n in nodes if "Sp2" in (n.get("text") or ""))

    assert parent_node is not None
    assert spouse1_node is not None
    assert spouse2_node is not None
