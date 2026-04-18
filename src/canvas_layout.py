"""
canvas_layout.py

Helper functions extracted from CanvasGenerator to make layout logic testable and
smaller. These are pure helpers that operate on the tree_structure dict used by
CanvasGenerator.

Do not change behavior in these helpers; they simply provide the logic in a
module that can be unit-tested independently and imported by CanvasGenerator.
"""

from typing import Dict, List, Set


def calculate_family_height(
    tree_structure: Dict[str, Dict],
    person_id: str,
    image_height: int,
    couple_spacing: int,
    visited: Set[str] | None = None,
) -> int:
    """
    Calculate total vertical height needed for a person and their spouse.

    This mirrors CanvasGenerator._calculate_family_height but is standalone.
    """
    if visited is None:
        visited = set()

    if person_id in visited or person_id not in tree_structure:
        return image_height

    visited.add(person_id)

    data = tree_structure[person_id]
    spouses = data.get("spouses", [])

    # Height for person
    height = image_height

    # Add spouse height if present
    if spouses:
        height += couple_spacing + image_height

    return height


def get_siblings(tree_structure: Dict[str, Dict], person_id: str) -> List[str]:
    """
    Get all siblings of a person (people who share the same parents).

    Returns list of sibling IDs.
    """
    if person_id not in tree_structure:
        return []

    person_data = tree_structure[person_id]
    parents = person_data.get("parents", [])

    if not parents:
        return []

    siblings = []
    for parent_id in parents:
        if parent_id in tree_structure:
            parent_data = tree_structure[parent_id]
            parent_children = parent_data.get("children", [])
            for child_id in parent_children:
                if child_id != person_id and child_id not in siblings:
                    siblings.append(child_id)

    return siblings


def calculate_subtree_widths(
    tree_structure: Dict[str, Dict],
    person_id: str,
    visited: set,
    node_width: int,
    horizontal_spacing: int,
) -> Dict[str, int]:
    """
    Calculate the width needed for each person's subtree (descendants).

    This is a pure helper extracted from CanvasGenerator._calculate_subtree_widths.
    """
    if person_id in visited or person_id not in tree_structure:
        return {}

    visited.add(person_id)
    widths: Dict[str, int] = {}

    data = tree_structure[person_id]
    children = data.get("children", [])

    if not children:
        # Leaf node: width is just this person + spacing
        widths[person_id] = node_width + horizontal_spacing
    else:
        # Calculate width needed for all children
        child_widths = 0
        for child_id in children:
            if child_id in tree_structure:
                child_subtree_widths = calculate_subtree_widths(
                    tree_structure, child_id, visited, node_width, horizontal_spacing
                )
                widths.update(child_subtree_widths)
                child_widths += child_subtree_widths.get(
                    child_id, node_width + horizontal_spacing
                )

        # This person's width is the max of:
        # 1. Their own width + spouse width
        # 2. Total width of their children
        spouses = data.get("spouses", [])
        own_width = (len(spouses) + 1) * (node_width + horizontal_spacing)
        widths[person_id] = max(own_width, child_widths)

    return widths
