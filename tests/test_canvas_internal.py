from canvas_generator import CanvasGenerator


class DummyIndividual:
    def __init__(self, pointer, first, last, gender="M"):
        self._pointer = pointer
        self._first = first
        self._last = last
        self._gender = gender

    def get_pointer(self):
        return self._pointer

    def get_gender(self):
        return self._gender

    def get_names(self):
        return (self._first, self._last)


def test_calculate_subtree_widths_direct():
    # A -> B, C; C -> D
    a = DummyIndividual("@A@", "A", "Alpha")
    b = DummyIndividual("@B@", "B", "Beta")
    c = DummyIndividual("@C@", "C", "Gamma")
    d = DummyIndividual("@D@", "D", "Delta")

    tree = {
        a.get_pointer(): {
            "individual": a,
            "children": [b.get_pointer()],
            "spouses": [],
        },
        b.get_pointer(): {
            "individual": b,
            "children": [c.get_pointer()],
            "spouses": [],
        },
        c.get_pointer(): {
            "individual": c,
            "children": [d.get_pointer()],
            "spouses": [],
        },
        d.get_pointer(): {"individual": d, "children": [], "spouses": []},
    }

    cg = CanvasGenerator([], ".")
    # Set spacing attributes used internally by layout helpers
    cg.HORIZONTAL_SPACING = 20
    cg.VERTICAL_SPACING = 200
    widths = cg._calculate_subtree_widths(tree, a.get_pointer(), set())

    # Ensure widths computed for all nodes
    assert a.get_pointer() in widths
    assert b.get_pointer() in widths
    assert c.get_pointer() in widths
    assert d.get_pointer() in widths
    # Values should be integers
    for v in widths.values():
        assert isinstance(v, int)


def test_layout_ancestors_positions():
    # Create child and parents; positions initially have child
    child = DummyIndividual("@CH@", "Child", "One")
    father = DummyIndividual("@F@", "Father", "One")
    mother = DummyIndividual("@M@", "Mother", "One")

    tree = {
        child.get_pointer(): {
            "individual": child,
            "parents": [father.get_pointer(), mother.get_pointer()],
            "spouses": [],
            "children": [],
        },
        father.get_pointer(): {
            "individual": father,
            "parents": [],
            "spouses": [],
            "children": [],
        },
        mother.get_pointer(): {
            "individual": mother,
            "parents": [],
            "spouses": [],
            "children": [],
        },
    }

    cg = CanvasGenerator([child, father, mother], ".")
    # Ensure spacing attributes exist
    cg.HORIZONTAL_SPACING = 20
    cg.VERTICAL_SPACING = 200
    positions = {child.get_pointer(): (0, 0)}
    processed = set([child.get_pointer()])
    # supply subtree_widths (not used heavily here)
    subtree_widths = {child.get_pointer(): cg.NODE_WIDTH}

    cg._layout_ancestors(
        child.get_pointer(), tree, positions, processed, subtree_widths
    )

    # Parents should now be positioned
    assert father.get_pointer() in positions
    assert mother.get_pointer() in positions


def test_layout_person_and_descendants_positions():
    # Person with spouse and two children
    person = DummyIndividual("@P@", "Person", "X")
    spouse = DummyIndividual("@SP@", "Spouse", "X")
    c1 = DummyIndividual("@C1@", "C1", "X")
    c2 = DummyIndividual("@C2@", "C2", "X")

    tree = {
        person.get_pointer(): {
            "individual": person,
            "spouses": [spouse.get_pointer()],
            "children": [c1.get_pointer(), c2.get_pointer()],
        },
        spouse.get_pointer(): {
            "individual": spouse,
            "spouses": [person.get_pointer()],
            "children": [],
        },
        c1.get_pointer(): {"individual": c1, "spouses": [], "children": []},
        c2.get_pointer(): {"individual": c2, "spouses": [], "children": []},
    }

    cg = CanvasGenerator([person, spouse, c1, c2], ".")
    # Ensure spacing attributes exist
    cg.HORIZONTAL_SPACING = 20
    cg.VERTICAL_SPACING = 200
    positions = {}
    processed = set()
    subtree_widths = {
        person.get_pointer(): cg.NODE_WIDTH * 3,
        c1.get_pointer(): cg.NODE_WIDTH,
        c2.get_pointer(): cg.NODE_WIDTH,
    }

    cg._layout_person_and_descendants(
        person.get_pointer(),
        tree,
        positions,
        processed,
        subtree_widths,
        x_offset=0,
        y_pos=0,
    )

    # Person, spouse, and children should be in positions
    assert person.get_pointer() in positions
    assert spouse.get_pointer() in positions
    assert c1.get_pointer() in positions
    assert c2.get_pointer() in positions


def test_calculate_ancestor_widths_direct():
    # ancestor widths for chain A <- B <- C
    a = DummyIndividual("@A2@", "A2", "AA")
    b = DummyIndividual("@B2@", "B2", "BB")
    c = DummyIndividual("@C2@", "C2", "CC")

    tree = {
        c.get_pointer(): {"individual": c, "parents": [b.get_pointer()]},
        b.get_pointer(): {"individual": b, "parents": [a.get_pointer()]},
        a.get_pointer(): {"individual": a, "parents": []},
    }

    cg = CanvasGenerator([], ".")
    cg.HORIZONTAL_SPACING = 20
    widths = cg._calculate_ancestor_widths(tree, c.get_pointer(), set())

    assert a.get_pointer() in widths
    assert b.get_pointer() in widths
    assert c.get_pointer() in widths
    for v in widths.values():
        assert isinstance(v, int)
