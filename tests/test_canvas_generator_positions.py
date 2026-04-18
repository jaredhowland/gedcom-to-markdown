from canvas_generator import CanvasGenerator


class StubIndividual:
    def __init__(self, pointer, gender):
        self._pointer = pointer
        self._gender = gender
        self.families = []
        self.families_as_child = []

    def get_pointer(self):
        return self._pointer

    def get_gender(self):
        return self._gender

    def get_names(self):
        return ("First", "Last")

    def get_families(self):
        return self.families

    def get_families_as_child(self):
        return self.families_as_child


def test_spouse_positioning(tmp_path):
    # Two individuals who are spouses
    root = StubIndividual("@I1@", "F")
    spouse = StubIndividual("@I2@", "M")

    # Make them each other's partners
    root.families = [{"partner": spouse}]
    spouse.families = [{"partner": root}]

    cg = CanvasGenerator([root, spouse], str(tmp_path))

    tree = cg._build_tree_structure(root.get_pointer())
    positions = cg._calculate_positions(tree)

    # Root should be at origin
    assert positions[root.get_pointer()] == (0, 0)

    # Spouse should be positioned vertically adjacent
    expected_spouse_y = cg.IMAGE_HEIGHT + cg.COUPLE_SPACING
    assert positions[spouse.get_pointer()] == (0, expected_spouse_y)
