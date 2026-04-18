from canvas_layout import (
    calculate_family_height,
    get_siblings,
    calculate_subtree_widths,
)


def test_calculate_family_height_and_siblings_and_subtree():
    # Setup a small tree structure
    tree = {
        "parent": {"spouses": [], "children": ["c1", "c2"], "parents": []},
        "c1": {"spouses": [], "children": [], "parents": ["parent"]},
        "c2": {"spouses": [], "children": [], "parents": ["parent"]},
    }

    # Family height: no spouse -> image_height
    assert (
        calculate_family_height(tree, "c1", image_height=100, couple_spacing=20) == 100
    )

    # Parent has no spouse, but children exist -> own_width vs child widths tested below

    # Siblings of c1 should include c2
    siblings = get_siblings(tree, "c1")
    assert "c2" in siblings and "c1" not in siblings

    # Subtree widths: parent has two leaf children
    widths = calculate_subtree_widths(
        tree, "parent", set(), node_width=100, horizontal_spacing=10
    )
    # children widths should be node_width + spacing
    assert widths["c1"] == 110
    assert widths["c2"] == 110
    # parent's width should be sum of child widths (220) or own width (110) -> expect 220
    assert widths["parent"] == 220
