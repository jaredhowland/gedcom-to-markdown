from canvas_layout import calculate_subtree_widths


def test_chain_widths():
    # A -> B -> C -> D (simple chain)
    tree = {
        "A": {"children": ["B"], "spouses": []},
        "B": {"children": ["C"], "spouses": []},
        "C": {"children": ["D"], "spouses": []},
        "D": {"children": [], "spouses": []},
    }

    node_width = 100
    horizontal_spacing = 20

    widths = calculate_subtree_widths(tree, "A", set(), node_width, horizontal_spacing)

    expected = node_width + horizontal_spacing

    # All nodes in the chain should have the same width
    assert widths["D"] == expected
    assert widths["C"] == expected
    assert widths["B"] == expected
    assert widths["A"] == expected


def test_branching_parent_width():
    # Parent with two children; parent's width should equal sum of child widths
    tree = {
        "P": {"children": ["C1", "C2"], "spouses": []},
        "C1": {"children": [], "spouses": []},
        "C2": {"children": [], "spouses": []},
    }

    node_width = 80
    horizontal_spacing = 10

    widths = calculate_subtree_widths(tree, "P", set(), node_width, horizontal_spacing)

    child_expected = node_width + horizontal_spacing

    assert widths["C1"] == child_expected
    assert widths["C2"] == child_expected

    # Parent width should be sum of children widths (since own_width is smaller)
    assert widths["P"] == child_expected * 2


def test_spouse_only_case():
    # Person has a spouse but no children. Only the person should be present in widths
    # and (because there are no children) the width should be the leaf width.
    tree = {
        "P": {"children": [], "spouses": ["S"]},
        "S": {"children": [], "spouses": ["P"]},
    }

    node_width = 60
    horizontal_spacing = 15

    widths = calculate_subtree_widths(tree, "P", set(), node_width, horizontal_spacing)

    # Spouses are not traversed as children; only the starting person should appear
    assert set(widths.keys()) == {"P"}

    expected = node_width + horizontal_spacing
    assert widths["P"] == expected
