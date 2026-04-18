"""
Canvas generator for creating Obsidian Canvas family trees.

This module generates JSON Canvas files that visualize family relationships
from GEDCOM data in a generational tree layout compatible with Obsidian.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import List, Dict, Tuple, Optional, Any
from collections import deque
from individual import Individual
from canvas_layout import calculate_subtree_widths
from utils import extract_year


logger = logging.getLogger(__name__)


class CanvasGenerator:
    """Generates Obsidian Canvas files for family tree visualization."""

    # Layout constants
    NODE_WIDTH = 250
    NODE_BASE_HEIGHT = 60  # Base height for nodes without images
    GENERATION_SPACING = 680  # Horizontal spacing between generations (left-to-right)
    HORIZONTAL_SPACING = 20  # Horizontal spacing between nodes
    VERTICAL_SPACING = 200  # Vertical spacing between generations
    SIBLING_SPACING = 305  # Vertical spacing between siblings when stacked
    COUPLE_SPACING = 190  # Vertical spacing between spouses when stacked
    IMAGE_HEIGHT = 350  # Height for nodes with images (increased to show image + name)
    TREE_SPACING = 400  # Space between disconnected trees

    def __init__(self, individuals: List[Any], output_dir: str):
        """
        Initialize the canvas generator.

        Args:
            individuals: List of all individuals from GEDCOM
            output_dir: Directory where canvas file will be saved
        """
        self.individuals = individuals
        self.output_dir = output_dir

        # Create lookup dictionary for fast access
        self.individual_map: Dict[str, Any] = {
            ind.get_pointer(): ind for ind in individuals
        }

        # Canvas data structures
        self.nodes: List[Dict] = []
        self.edges: List[Dict] = []

        logger.info(f"Initialized CanvasGenerator with {len(individuals)} individuals")

    def generate_canvas(
        self, root_person_id: str, canvas_filename: str = "Family Tree.canvas"
    ) -> str:
        """
        Generate canvas file with family tree visualization.

        Args:
            root_person_id: GEDCOM pointer of the root person
            canvas_filename: Name of the output canvas file

        Returns:
            Path to the generated canvas file
        """
        logger.info(f"Generating canvas with root person: {root_person_id}")
        logger.info(f"Total individuals in GEDCOM: {len(self.individuals)}")

        # Build family tree structure starting from root
        tree_structure = self._build_tree_structure(root_person_id)
        logger.info(
            f"Main tree contains {len(tree_structure)} people connected to root"
        )

        # Calculate node positions using generational layout
        positioned_nodes = self._calculate_positions(tree_structure)

        # Create canvas nodes and edges
        self._create_canvas_elements(positioned_nodes, tree_structure)

        # Find and add disconnected family trees
        self._add_disconnected_trees(tree_structure)

        # Write canvas file
        canvas_path = os.path.join(self.output_dir, canvas_filename)
        self._write_canvas_file(canvas_path)

        logger.info(
            f"Canvas generated with {len(self.nodes)} nodes and {len(self.edges)} edges"
        )
        logger.info(
            f"Total people represented: {len(self.nodes)}/{len(self.individuals)}"
        )
        return canvas_path

    def _build_tree_structure(self, root_id: str) -> Dict[str, Dict]:
        """
        Build tree structure starting from root person using BFS.

        Returns a dict mapping person_id -> {
            'individual': Individual,
            'generation': int,
            'spouses': List[str],
            'children': List[str],
            'parents': List[str]
        }
        """
        structure = {}
        visited = set()
        queue = deque([(root_id, 0)])  # (person_id, generation)

        while queue:
            person_id, generation = queue.popleft()

            if person_id in visited or person_id not in self.individual_map:
                continue

            visited.add(person_id)
            individual = self.individual_map[person_id]

            # Initialize structure for this person
            structure[person_id] = {
                "individual": individual,
                "generation": generation,
                "spouses": [],
                "children": [],
                "parents": [],
            }

            # Get families where this person is a child (to find parents)
            families_as_child = getattr(
                individual, "get_families_as_child", lambda: []
            )()
            for family in families_as_child:
                # Add parents
                if family.get("father"):
                    father_id = family["father"]
                    structure[person_id]["parents"].append(father_id)
                    if father_id not in visited:
                        queue.append((father_id, generation - 1))

                if family.get("mother"):
                    mother_id = family["mother"]
                    structure[person_id]["parents"].append(mother_id)
                    if mother_id not in visited:
                        queue.append((mother_id, generation - 1))

            # Get families where this person is a spouse (to find spouses and children)
            families = getattr(individual, "get_families", lambda: [])()
            for family in families:
                # Add spouse
                partner = family.get("partner")
                if partner:
                    spouse_id = getattr(partner, "get_pointer", lambda: None)()
                    if spouse_id and spouse_id not in structure[person_id]["spouses"]:
                        structure[person_id]["spouses"].append(spouse_id)
                        if spouse_id not in visited:
                            queue.append((spouse_id, generation))

                # Add children
                children = family.get("children", [])
                for child in children:
                    child_id = getattr(child, "get_pointer", lambda: None)()
                    if child_id and child_id not in structure[person_id]["children"]:
                        structure[person_id]["children"].append(child_id)
                        if child_id not in visited:
                            queue.append((child_id, generation + 1))

        logger.info(
            f"Built tree structure with {len(structure)} people from root {root_id}"
        )
        return structure

    def _calculate_positions(
        self, tree_structure: Dict[str, Dict]
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate positions using left-to-right timeline layout.

        Layout strategy:
        - X-axis: Generational flow (children left, parents right)
        - Y-axis: Vertical stacking of siblings
        - Start with root person at (0, 0)
        - Place descendants to the LEFT
        - Place ancestors to the RIGHT
        - Stack siblings VERTICALLY with minimal spacing

        Returns dict mapping person_id -> (x, y)
        """
        positions = {}

        if not tree_structure:
            return positions

        # Find root person (generation 0)
        root_id = None
        for person_id, data in tree_structure.items():
            if data["generation"] == 0:
                root_id = person_id
                break

        if not root_id:
            logger.error("No root person found at generation 0")
            return positions

        logger.info(f"Root person: {root_id} at generation 0")

        # Start root person at origin
        positions[root_id] = (0, 0)
        processed = {root_id}

        # Shared dict to track next available y position at each x coordinate
        # This prevents overlaps when multiple family branches use the same x
        shared_min_y_at_x = {}

        # Determine direction based on gender
        # Male: grow upward (negative y), Female: grow downward (positive y)
        root_individual = tree_structure[root_id]["individual"]
        root_gender = root_individual.get_gender()
        root_direction = "up" if root_gender == "M" else "down"
        logger.info(f"Root person gender: {root_gender}, direction: {root_direction}")

        # Place spouse vertically adjacent
        root_data = tree_structure[root_id]
        spouses = root_data.get("spouses", [])
        if spouses:
            spouse_id = spouses[0]
            if spouse_id in tree_structure:
                spouse_y = self.IMAGE_HEIGHT + self.COUPLE_SPACING
                positions[spouse_id] = (0, int(spouse_y))
                processed.add(spouse_id)

                # Determine spouse direction based on gender
                spouse_individual = tree_structure[spouse_id]["individual"]
                spouse_gender = spouse_individual.get_gender()
                spouse_direction = "up" if spouse_gender == "M" else "down"

                # Position spouse's siblings and their families
                self._position_spouse_siblings(
                    spouse_id,
                    0,
                    int(spouse_y),
                    tree_structure,
                    positions,
                    processed,
                    spouse_direction,
                )
                # Position spouse's ancestors (parents, grandparents, etc.) to the RIGHT
                self._layout_ancestors_right(
                    spouse_id,
                    tree_structure,
                    positions,
                    processed,
                    spouse_direction,
                    shared_min_y_at_x,
                )

        # Layout descendants (children) to the LEFT
        self._layout_descendants_left(root_id, tree_structure, positions, processed)

        # Layout ancestors (parents) to the RIGHT
        self._layout_ancestors_right(
            root_id,
            tree_structure,
            positions,
            processed,
            root_direction,
            shared_min_y_at_x,
        )

        # Position any remaining unprocessed people
        unprocessed = set(tree_structure.keys()) - processed
        if unprocessed:
            logger.info(f"Positioning {len(unprocessed)} remaining unconnected people")
            # Place them far to the right as a separate tree
            max_x = max(x for x, y in positions.values()) if positions else 0
            current_y = 0
            for person_id in unprocessed:
                positions[person_id] = (int(max_x + self.TREE_SPACING), int(current_y))
                current_y += self.IMAGE_HEIGHT + self.SIBLING_SPACING
                processed.add(person_id)

        logger.info(f"Positioned {len(positions)} out of {len(tree_structure)} people")

        return positions

    def _layout_descendants_left(
        self,
        root_id: str,
        tree_structure: Dict[str, Dict],
        positions: Dict[str, Tuple[int, int]],
        processed: set,
    ):
        """
        Layout descendants to the left of root person with vertical sibling stacking.

        Each child is positioned to the left of their parent.
        Siblings are stacked vertically.
        """
        if root_id not in tree_structure or root_id not in positions:
            return

        root_data = tree_structure[root_id]
        children = root_data.get("children", [])

        if not children:
            return

        # Get root position
        root_x, root_y = positions[root_id]

        # Check if root has spouse - need to center children between root and spouse
        spouses = root_data.get("spouses", [])
        if spouses and spouses[0] in positions:
            spouse_x, spouse_y = positions[spouses[0]]
            parent_center_y = (root_y + spouse_y) / 2
        else:
            parent_center_y = root_y

        # Calculate total vertical height needed for all children
        total_children_height = 0
        child_heights = {}

        for child_id in children:
            if child_id not in tree_structure:
                continue
            # Each child needs space for themselves + their spouse
            child_height = self._calculate_family_height(
                child_id, tree_structure, set()
            )
            child_heights[child_id] = child_height
            total_children_height += child_height

        # Add spacing between siblings
        if len(children) > 1:
            total_children_height += (len(children) - 1) * self.SIBLING_SPACING

        # Position children starting from top, centered on parent
        child_x = root_x - self.GENERATION_SPACING
        start_y = parent_center_y - (total_children_height / 2)
        current_y = start_y

        for child_id in children:
            if child_id in processed or child_id not in tree_structure:
                continue

            positions[child_id] = (int(child_x), int(current_y))
            processed.add(child_id)

            # Position child's spouse below them
            child_data = tree_structure[child_id]
            child_spouses = child_data.get("spouses", [])
            if child_spouses:
                spouse_id = child_spouses[0]
                if spouse_id in tree_structure and spouse_id not in processed:
                    spouse_y = current_y + self.IMAGE_HEIGHT + self.COUPLE_SPACING
                    positions[spouse_id] = (int(child_x), int(spouse_y))
                    processed.add(spouse_id)

                    # Determine spouse direction based on gender
                    spouse_individual = tree_structure[spouse_id]["individual"]
                    spouse_gender = spouse_individual.get_gender()
                    spouse_direction = "up" if spouse_gender == "M" else "down"

                    # Position spouse's siblings and their families
                    self._position_spouse_siblings(
                        spouse_id,
                        child_x,
                        int(spouse_y),
                        tree_structure,
                        positions,
                        processed,
                        spouse_direction,
                    )
                    # Position spouse's ancestors (parents, grandparents, etc.)
                    # Note: we don't pass shared_min_y_at_x here because this is from _layout_descendants_left
                    # which doesn't have access to it. This could cause overlaps for deep trees.
                    self._layout_ancestors_right(
                        spouse_id,
                        tree_structure,
                        positions,
                        processed,
                        spouse_direction,
                    )

            # Recursively layout this child's descendants (further left)
            self._layout_descendants_left(
                child_id, tree_structure, positions, processed
            )

            # Move down for next sibling
            current_y += (
                child_heights.get(child_id, self.IMAGE_HEIGHT) + self.SIBLING_SPACING
            )

    def _layout_ancestors_right(
        self,
        root_id: str,
        tree_structure: Dict[str, Dict],
        positions: Dict[str, Tuple[int, int]],
        processed: set,
        direction: str = "down",
        min_y_at_x: Optional[Dict[Tuple[int, str], float]] = None,
    ):
        """
        Layout ancestors to the right of root person with vertical sibling stacking.

        Parents are positioned to the right.
        Parent couples are stacked vertically.

        Args:
            direction: 'up' to grow upward (negative y), 'down' to grow downward (positive y)
            min_y_at_x: Shared dict tracking next available y at each x position
        """
        if root_id not in tree_structure or root_id not in positions:
            return

        # Initialize if not provided
        if min_y_at_x is None:
            min_y_at_x = {}

        # Process only this person's parents (not spouse's)
        # Spouse's parents will be processed in their own call with their own direction
        person_id = root_id
        if person_id not in positions:
            return

        person_data = tree_structure[person_id]
        person_name = person_data["individual"].get_names()
        logger.info(f"Processing ancestors for {person_name}, direction={direction}")
        parents = person_data.get("parents", [])

        if not parents:
            return

        person_x, person_y = positions[person_id]
        parent_x = person_x + self.GENERATION_SPACING

        # Position parent couple
        if len(parents) == 2:
            father_id, mother_id = parents[0], parents[1]

            # Check if we need to avoid overlap at this x-position
            # Use (x, direction) as key to track upward and downward growth separately
            key = (parent_x, direction)
            if key in min_y_at_x:
                # Position relative to existing people at this x-coordinate going this direction
                parent_y = min_y_at_x[key]
                logger.info(
                    f"Using min_y_at_x for x={parent_x}, dir={direction}: y={parent_y}"
                )
            else:
                # Center parent couple on their child
                parent_y = person_y
                logger.info(
                    f"Centering parents on child at y={person_y}, direction={direction}"
                )

            if father_id in tree_structure and father_id not in processed:
                positions[father_id] = (int(parent_x), int(parent_y))
                processed.add(father_id)
                father_name = tree_structure[father_id]["individual"].get_names()
                logger.info(
                    f"Positioned father {father_name} at ({parent_x}, {parent_y})"
                )

            mother_y = parent_y  # Default if mother doesn't exist
            if mother_id in tree_structure and mother_id not in processed:
                if direction == "up":
                    mother_y = parent_y - self.IMAGE_HEIGHT - self.COUPLE_SPACING
                else:
                    mother_y = parent_y + self.IMAGE_HEIGHT + self.COUPLE_SPACING

                # Check if we need to avoid overlap at this position
                key = (parent_x, direction)
                if key in min_y_at_x:
                    if direction == "up":
                        # For upward growth, ensure mother is above the min_y
                        if mother_y > min_y_at_x[key]:
                            mother_y = (
                                min_y_at_x[key]
                                - self.IMAGE_HEIGHT
                                - self.COUPLE_SPACING
                            )
                            logger.info(
                                f"Adjusted mother position to avoid overlap: y={mother_y}"
                            )
                    else:
                        # For downward growth, ensure mother is below the min_y
                        if mother_y < min_y_at_x[key]:
                            mother_y = (
                                min_y_at_x[key]
                                + self.IMAGE_HEIGHT
                                + self.COUPLE_SPACING
                            )
                            logger.info(
                                f"Adjusted mother position to avoid overlap: y={mother_y}"
                            )

                positions[mother_id] = (int(parent_x), int(mother_y))
                processed.add(mother_id)

                # Update min_y_at_x to include the mother's position
                if direction == "up":
                    min_y_at_x[key] = (
                        mother_y - self.SIBLING_SPACING - self.IMAGE_HEIGHT
                    )
                    logger.info(
                        f"Updated min_y_at_x[{key}] = {min_y_at_x[key]} after positioning mother"
                    )
                else:
                    min_y_at_x[key] = (
                        mother_y + self.IMAGE_HEIGHT + self.SIBLING_SPACING
                    )
                    logger.info(
                        f"Updated min_y_at_x[{key}] = {min_y_at_x[key]} after positioning mother"
                    )

            # Position siblings of both parents at same x-position, stacked vertically
            if direction == "up":
                current_sibling_y = (
                    min(parent_y, mother_y) - self.SIBLING_SPACING - self.IMAGE_HEIGHT
                )
            else:
                current_sibling_y = (
                    max(parent_y, mother_y) + self.IMAGE_HEIGHT + self.SIBLING_SPACING
                )

            # Father's siblings
            father_siblings = self._get_siblings(father_id, tree_structure)
            for sibling_id in father_siblings:
                if sibling_id in tree_structure and sibling_id not in processed:
                    positions[sibling_id] = (int(parent_x), int(current_sibling_y))
                    processed.add(sibling_id)
                    sibling_name = tree_structure[sibling_id]["individual"].get_names()
                    logger.info(
                        f"Positioned father sibling {sibling_name} at ({parent_x}, {current_sibling_y})"
                    )

                    # Position sibling's spouse
                    sibling_data = tree_structure[sibling_id]
                    sibling_spouses = sibling_data.get("spouses", [])
                    if sibling_spouses:
                        spouse_id = sibling_spouses[0]
                        if spouse_id in tree_structure and spouse_id not in processed:
                            if direction == "up":
                                spouse_y = (
                                    current_sibling_y
                                    - self.IMAGE_HEIGHT
                                    - self.COUPLE_SPACING
                                )
                            else:
                                spouse_y = (
                                    current_sibling_y
                                    + self.IMAGE_HEIGHT
                                    + self.COUPLE_SPACING
                                )
                            positions[spouse_id] = (int(parent_x), int(spouse_y))
                            processed.add(spouse_id)
                            # Position spouse's siblings and their families
                            self._position_spouse_siblings(
                                spouse_id,
                                parent_x,
                                int(spouse_y),
                                tree_structure,
                                positions,
                                processed,
                                direction,
                            )
                            if direction == "up":
                                current_sibling_y = (
                                    min(current_sibling_y, spouse_y)
                                    - self.SIBLING_SPACING
                                    - self.IMAGE_HEIGHT
                                )
                            else:
                                current_sibling_y = (
                                    max(current_sibling_y, spouse_y)
                                    + self.IMAGE_HEIGHT
                                    + self.SIBLING_SPACING
                                )
                        else:
                            if direction == "up":
                                current_sibling_y -= (
                                    self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                )
                            else:
                                current_sibling_y += (
                                    self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                )
                    else:
                        if direction == "up":
                            current_sibling_y -= (
                                self.IMAGE_HEIGHT + self.SIBLING_SPACING
                            )
                        else:
                            current_sibling_y += (
                                self.IMAGE_HEIGHT + self.SIBLING_SPACING
                            )

                    # Position sibling's children (cousins) to the left
                    self._layout_descendants_left(
                        sibling_id, tree_structure, positions, processed
                    )

            # Mother's siblings (who aren't already father's siblings)
            mother_siblings = self._get_siblings(mother_id, tree_structure)
            for sibling_id in mother_siblings:
                if (
                    sibling_id not in father_siblings
                    and sibling_id in tree_structure
                    and sibling_id not in processed
                ):
                    positions[sibling_id] = (int(parent_x), int(current_sibling_y))
                    processed.add(sibling_id)

                    # Position sibling's spouse
                    sibling_data = tree_structure[sibling_id]
                    sibling_spouses = sibling_data.get("spouses", [])
                    if sibling_spouses:
                        spouse_id = sibling_spouses[0]
                        if spouse_id in tree_structure and spouse_id not in processed:
                            if direction == "up":
                                spouse_y = (
                                    current_sibling_y
                                    - self.IMAGE_HEIGHT
                                    - self.COUPLE_SPACING
                                )
                            else:
                                spouse_y = (
                                    current_sibling_y
                                    + self.IMAGE_HEIGHT
                                    + self.COUPLE_SPACING
                                )
                            positions[spouse_id] = (int(parent_x), int(spouse_y))
                            processed.add(spouse_id)
                            # Position spouse's siblings and their families
                            self._position_spouse_siblings(
                                spouse_id,
                                parent_x,
                                int(spouse_y),
                                tree_structure,
                                positions,
                                processed,
                                direction,
                            )
                            if direction == "up":
                                current_sibling_y = (
                                    min(current_sibling_y, spouse_y)
                                    - self.SIBLING_SPACING
                                    - self.IMAGE_HEIGHT
                                )
                            else:
                                current_sibling_y = (
                                    max(current_sibling_y, spouse_y)
                                    + self.IMAGE_HEIGHT
                                    + self.SIBLING_SPACING
                                )
                        else:
                            if direction == "up":
                                current_sibling_y -= (
                                    self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                )
                            else:
                                current_sibling_y += (
                                    self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                )
                    else:
                        if direction == "up":
                            current_sibling_y -= (
                                self.IMAGE_HEIGHT + self.SIBLING_SPACING
                            )
                        else:
                            current_sibling_y += (
                                self.IMAGE_HEIGHT + self.SIBLING_SPACING
                            )

                    # Position sibling's children (cousins) to the left
                    self._layout_descendants_left(
                        sibling_id, tree_structure, positions, processed
                    )

            # Update the minimum y for this x-position for next iteration
            key = (parent_x, direction)
            min_y_at_x[key] = current_sibling_y

            # Recursively position their ancestors (further right)
            # Process both parents' ancestors (maintain same direction)
            if father_id in tree_structure:
                self._layout_ancestors_right(
                    father_id,
                    tree_structure,
                    positions,
                    processed,
                    direction,
                    min_y_at_x,
                )
            if mother_id in tree_structure:
                self._layout_ancestors_right(
                    mother_id,
                    tree_structure,
                    positions,
                    processed,
                    direction,
                    min_y_at_x,
                )

        elif len(parents) == 1:
            parent_id = parents[0]
            if parent_id in tree_structure and parent_id not in processed:
                parent_name = tree_structure[parent_id]["individual"].get_names()

                # Check if we need to avoid overlap at this position
                key = (parent_x, direction)
                parent_y = person_y
                if key in min_y_at_x:
                    if direction == "up":
                        # For upward growth, ensure parent is above the min_y
                        if parent_y > min_y_at_x[key]:
                            parent_y = (
                                min_y_at_x[key]
                                - self.IMAGE_HEIGHT
                                - self.SIBLING_SPACING
                            )
                            logger.info(
                                f"Adjusted single parent position to avoid overlap: y={parent_y}"
                            )
                    else:
                        # For downward growth, ensure parent is below the min_y
                        if parent_y < min_y_at_x[key]:
                            parent_y = (
                                min_y_at_x[key]
                                + self.IMAGE_HEIGHT
                                + self.SIBLING_SPACING
                            )
                            logger.info(
                                f"Adjusted single parent position to avoid overlap: y={parent_y}"
                            )

                logger.info(
                    f"Single parent case: positioning {parent_name} at ({parent_x}, {parent_y})"
                )
                positions[parent_id] = (int(parent_x), int(parent_y))
                processed.add(parent_id)

                # Update min_y_at_x to include this parent's position
                if direction == "up":
                    min_y_at_x[key] = (
                        parent_y - self.IMAGE_HEIGHT - self.SIBLING_SPACING
                    )
                else:
                    min_y_at_x[key] = (
                        parent_y + self.IMAGE_HEIGHT + self.SIBLING_SPACING
                    )

                self._layout_ancestors_right(
                    parent_id,
                    tree_structure,
                    positions,
                    processed,
                    direction,
                    min_y_at_x,
                )

    def _calculate_family_height(
        self, person_id: str, tree_structure: Dict[str, Dict], visited: set
    ) -> int:
        """
        Calculate total vertical height needed for a person and their spouse.

        Returns the height in pixels needed to display this person + spouse.
        """
        if person_id in visited or person_id not in tree_structure:
            return self.IMAGE_HEIGHT

        visited.add(person_id)

        data = tree_structure[person_id]
        spouses = data.get("spouses", [])

        # Height for person
        height = self.IMAGE_HEIGHT

        # Add spouse height if present
        if spouses:
            height += self.COUPLE_SPACING + self.IMAGE_HEIGHT

        return height

    def _get_siblings(self, person_id: str, tree_structure: Dict[str, Dict]) -> list:
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

        # Find all children of the same parents
        siblings = []

        # Get children from parents
        for parent_id in parents:
            if parent_id in tree_structure:
                parent_data = tree_structure[parent_id]
                parent_children = parent_data.get("children", [])
                for child_id in parent_children:
                    if child_id != person_id and child_id not in siblings:
                        siblings.append(child_id)

        return siblings

    def _position_spouse_siblings(
        self,
        spouse_id: str,
        spouse_x: int,
        spouse_y: int,
        tree_structure: Dict[str, Dict],
        positions: Dict[str, Tuple[int, int]],
        processed: set,
        direction: str = "down",
    ):
        """
        Position the siblings of a spouse and their families.

        This ensures extended families (e.g., wife's siblings and their families) are included.

        Args:
            direction: 'up' to grow upward (negative y), 'down' to grow downward (positive y)
        """
        if spouse_id not in tree_structure:
            return

        # Initialize current_y to position elements relative to the spouse
        if direction == "up":
            current_y = spouse_y - self.IMAGE_HEIGHT - self.SIBLING_SPACING
        else:
            current_y = spouse_y + self.IMAGE_HEIGHT + self.SIBLING_SPACING

        # First, position the spouse's spouse's siblings if they exist
        # (bidirectional spouse relationship)
        spouse_data = tree_structure[spouse_id]
        spouse_spouses = spouse_data.get("spouses", [])
        if spouse_spouses:
            for partner_id in spouse_spouses:
                if partner_id in tree_structure and partner_id not in processed:
                    # Position the partner relative to the spouse
                    if direction == "up":
                        partner_y = spouse_y - self.IMAGE_HEIGHT - self.COUPLE_SPACING
                    else:
                        partner_y = spouse_y + self.IMAGE_HEIGHT + self.COUPLE_SPACING
                    positions[partner_id] = (int(spouse_x), int(partner_y))
                    processed.add(partner_id)

                    if direction == "up":
                        current_y = partner_y - self.SIBLING_SPACING - self.IMAGE_HEIGHT
                    else:
                        current_y = partner_y + self.IMAGE_HEIGHT + self.SIBLING_SPACING

                    # Position the partner's siblings (spouse's in-laws)
                    partner_siblings = self._get_siblings(partner_id, tree_structure)
                    for sib_id in partner_siblings:
                        if sib_id in tree_structure and sib_id not in processed:
                            positions[sib_id] = (int(spouse_x), int(current_y))
                            processed.add(sib_id)

                            # Position this in-law sibling's spouse
                            sib_data = tree_structure[sib_id]
                            sib_spouses = sib_data.get("spouses", [])
                            if (
                                sib_spouses
                                and sib_spouses[0] in tree_structure
                                and sib_spouses[0] not in processed
                            ):
                                if direction == "up":
                                    sib_spouse_y = (
                                        current_y
                                        - self.IMAGE_HEIGHT
                                        - self.COUPLE_SPACING
                                    )
                                else:
                                    sib_spouse_y = (
                                        current_y
                                        + self.IMAGE_HEIGHT
                                        + self.COUPLE_SPACING
                                    )
                                positions[sib_spouses[0]] = (
                                    int(spouse_x),
                                    int(sib_spouse_y),
                                )
                                processed.add(sib_spouses[0])

                                if direction == "up":
                                    current_y = (
                                        sib_spouse_y
                                        - self.SIBLING_SPACING
                                        - self.IMAGE_HEIGHT
                                    )
                                else:
                                    current_y = (
                                        sib_spouse_y
                                        + self.IMAGE_HEIGHT
                                        + self.SIBLING_SPACING
                                    )
                            else:
                                if direction == "up":
                                    current_y -= (
                                        self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                    )
                                else:
                                    current_y += (
                                        self.IMAGE_HEIGHT + self.SIBLING_SPACING
                                    )

                            # Position their children
                            self._layout_descendants_left(
                                sib_id, tree_structure, positions, processed
                            )

        # Get spouse's siblings
        spouse_siblings = self._get_siblings(spouse_id, tree_structure)

        for sibling_id in spouse_siblings:
            if sibling_id in tree_structure and sibling_id not in processed:
                positions[sibling_id] = (int(spouse_x), int(current_y))
                processed.add(sibling_id)

                # Position this sibling's spouse
                sibling_data = tree_structure[sibling_id]
                sibling_spouses = sibling_data.get("spouses", [])
                if sibling_spouses:
                    sibling_spouse_id = sibling_spouses[0]
                    if (
                        sibling_spouse_id in tree_structure
                        and sibling_spouse_id not in processed
                    ):
                        if direction == "up":
                            sibling_spouse_y = (
                                current_y - self.IMAGE_HEIGHT - self.COUPLE_SPACING
                            )
                        else:
                            sibling_spouse_y = (
                                current_y + self.IMAGE_HEIGHT + self.COUPLE_SPACING
                            )
                        positions[sibling_spouse_id] = (
                            int(spouse_x),
                            int(sibling_spouse_y),
                        )
                        processed.add(sibling_spouse_id)

                        if direction == "up":
                            current_y = (
                                sibling_spouse_y
                                - self.SIBLING_SPACING
                                - self.IMAGE_HEIGHT
                            )
                        else:
                            current_y = (
                                sibling_spouse_y
                                + self.IMAGE_HEIGHT
                                + self.SIBLING_SPACING
                            )
                    else:
                        if direction == "up":
                            current_y -= self.IMAGE_HEIGHT + self.SIBLING_SPACING
                        else:
                            current_y += self.IMAGE_HEIGHT + self.SIBLING_SPACING
                else:
                    if direction == "up":
                        current_y -= self.IMAGE_HEIGHT + self.SIBLING_SPACING
                    else:
                        current_y += self.IMAGE_HEIGHT + self.SIBLING_SPACING

                # Position this sibling's children (to the left)
                self._layout_descendants_left(
                    sibling_id, tree_structure, positions, processed
                )

    def _calculate_subtree_widths(
        self, tree_structure: Dict[str, Dict], person_id: str, visited: set
    ) -> Dict[str, int]:
        """
        Wrapper that delegates subtree width calculation to canvas_layout.calculate_subtree_widths.
        """
        # Delegate to pure helper, passing instance constants
        return calculate_subtree_widths(
            tree_structure,
            person_id,
            visited,
            getattr(self, "NODE_WIDTH", 250),
            getattr(self, "HORIZONTAL_SPACING", 20),
        )

    def _calculate_ancestor_widths(
        self, tree_structure: Dict[str, Dict], person_id: str, visited: set
    ) -> Dict[str, int]:
        """
        Calculate the width needed for ancestors (going up the tree).

        Similar to _calculate_subtree_widths but follows parent relationships.
        """
        if person_id in visited or person_id not in tree_structure:
            return {}

        visited.add(person_id)
        widths = {}

        data = tree_structure[person_id]
        parents = data.get("parents", [])

        if not parents:
            # No parents: width is just this person + spacing
            widths[person_id] = self.NODE_WIDTH + self.HORIZONTAL_SPACING
        else:
            # Calculate width needed for all parents
            parent_widths = 0
            for parent_id in parents:
                if parent_id in tree_structure:
                    parent_ancestor_widths = self._calculate_ancestor_widths(
                        tree_structure, parent_id, visited
                    )
                    widths.update(parent_ancestor_widths)
                    parent_widths += parent_ancestor_widths.get(
                        parent_id, self.NODE_WIDTH + self.HORIZONTAL_SPACING
                    )

            # This person's width is the max of their own width and parents' width
            widths[person_id] = max(
                self.NODE_WIDTH + self.HORIZONTAL_SPACING, parent_widths
            )

        return widths

    def _layout_ancestors(
        self,
        root_person_id: str,
        tree_structure: Dict[str, Dict],
        positions: Dict[str, Tuple[int, int]],
        processed: set,
        subtree_widths: Dict[str, int],
    ):
        """
        Layout ancestors above their children.

        Positions each parent couple directly above their child, creating
        a compact tree structure rather than spreading all parents horizontally.

        Args:
            root_person_id: ID of the root person (already positioned)
            tree_structure: Full tree structure
            positions: Dict to store calculated positions
            processed: Set of already-processed person IDs
            subtree_widths: Pre-calculated widths for all people
        """
        # Process all currently positioned people and add their parents
        # We need to iterate multiple times to handle all ancestor generations
        max_iterations = 10  # Safety limit

        for iteration in range(max_iterations):
            # Find all people who are positioned but whose parents aren't yet
            people_to_process = []
            for person_id in list(positions.keys()):
                if person_id not in tree_structure:
                    continue

                data = tree_structure[person_id]
                parents = data.get("parents", [])

                # Check if this person has unpositioned parents
                has_unpositioned_parents = False
                for parent_id in parents:
                    if parent_id in tree_structure and parent_id not in processed:
                        has_unpositioned_parents = True
                        break

                if has_unpositioned_parents:
                    people_to_process.append(person_id)

            if not people_to_process:
                break  # No more parents to position

            # Position parents for each person
            for person_id in people_to_process:
                if person_id not in positions:
                    continue

                child_x, child_y = positions[person_id]
                data = tree_structure[person_id]
                parents = data.get("parents", [])

                if not parents:
                    continue

                # Calculate Y position for parents (one generation above)
                parent_y = child_y - (self.VERTICAL_SPACING + self.IMAGE_HEIGHT)

                if len(parents) == 2:
                    # Both parents: center the couple above the child
                    father_id, mother_id = parents[0], parents[1]

                    # Calculate couple width
                    couple_width = 2 * self.NODE_WIDTH + self.HORIZONTAL_SPACING

                    # Center couple above child
                    couple_start_x = child_x - (couple_width - self.NODE_WIDTH) // 2

                    # Position father
                    if father_id in tree_structure and father_id not in processed:
                        positions[father_id] = (int(couple_start_x), int(parent_y))
                        processed.add(father_id)

                    # Position mother next to father
                    mother_x = (
                        couple_start_x + self.NODE_WIDTH + self.HORIZONTAL_SPACING
                    )
                    if mother_id in tree_structure and mother_id not in processed:
                        positions[mother_id] = (int(mother_x), int(parent_y))
                        processed.add(mother_id)

                elif len(parents) == 1:
                    # Single parent: center above child
                    parent_id = parents[0]
                    if parent_id in tree_structure and parent_id not in processed:
                        positions[parent_id] = (int(child_x), int(parent_y))
                        processed.add(parent_id)

    def _layout_person_and_descendants(
        self,
        person_id: str,
        tree_structure: Dict[str, Dict],
        positions: Dict[str, Tuple[int, int]],
        processed: set,
        subtree_widths: Dict[str, int],
        x_offset: int,
        y_pos: int,
    ):
        """
        Recursively layout a person, their spouse, and descendants.

        Args:
            person_id: ID of person to layout
            tree_structure: Full tree structure
            positions: Dict to store calculated positions
            processed: Set of already-processed person IDs
            subtree_widths: Pre-calculated subtree widths
            x_offset: Left edge x-coordinate for this person's subtree
            y_pos: Y-coordinate for this person
        """
        if person_id not in tree_structure:
            return

        if person_id in processed:
            logger.debug(f"Skipping already processed person: {person_id}")
            return

        processed.add(person_id)
        data = tree_structure[person_id]
        logger.debug(f"Positioning {person_id} at y={y_pos}")

        # Get spouse(s)
        spouses = data.get("spouses", [])

        # Calculate width for this person + spouses
        num_people = len(spouses) + 1
        people_width = (
            num_people * self.NODE_WIDTH + (num_people - 1) * self.HORIZONTAL_SPACING
        )

        # Get subtree width
        total_width = subtree_widths.get(person_id, people_width)

        # Center this person (and spouses) within their subtree width
        people_start_x = x_offset + (total_width - people_width) // 2

        # Position this person
        positions[person_id] = (int(people_start_x), int(y_pos))

        # Position spouse(s) to the right
        current_x = people_start_x + self.NODE_WIDTH + self.HORIZONTAL_SPACING
        for spouse_id in spouses:
            if spouse_id not in processed and spouse_id in tree_structure:
                positions[spouse_id] = (int(current_x), int(y_pos))
                processed.add(spouse_id)
                current_x += self.NODE_WIDTH + self.HORIZONTAL_SPACING

        # Layout children below
        children = data.get("children", [])
        if children:
            # Calculate y position for children
            child_y = y_pos + self.VERTICAL_SPACING + self.IMAGE_HEIGHT

            # Position children left-to-right, centered under parents
            child_x_offset = x_offset

            for child_id in children:
                if child_id in tree_structure and child_id not in processed:
                    child_width = subtree_widths.get(
                        child_id, self.NODE_WIDTH + self.HORIZONTAL_SPACING
                    )

                    self._layout_person_and_descendants(
                        child_id,
                        tree_structure,
                        positions,
                        processed,
                        subtree_widths,
                        child_x_offset,
                        child_y,
                    )

                    child_x_offset += child_width

    def _create_canvas_elements(
        self, positions: Dict[str, Tuple[int, int]], tree_structure: Dict[str, Dict]
    ):
        """
        Create canvas nodes and edges from positioned tree structure.
        """
        node_ids = {}  # Map person_id -> canvas node_id

        # Create nodes
        for person_id, (x, y) in positions.items():
            individual = tree_structure[person_id]["individual"]
            node_id = self._create_node(individual, x, y)
            node_ids[person_id] = node_id

        # Create edges
        for person_id, data in tree_structure.items():
            from_node_id = node_ids.get(person_id)
            if not from_node_id:
                continue

            # Create parent-child edges
            for child_id in data["children"]:
                to_node_id = node_ids.get(child_id)
                if to_node_id:
                    self._create_edge(
                        from_node_id, to_node_id, "Child", "left", "right"
                    )

            # Create spouse edges
            for spouse_id in data["spouses"]:
                to_node_id = node_ids.get(spouse_id)
                if to_node_id:
                    # Only create edge once (from lower ID to higher ID to avoid duplicates)
                    if person_id < spouse_id:
                        self._create_edge(
                            from_node_id,
                            to_node_id,
                            "Spouse",
                            "bottom",
                            "top",
                            bidirectional=True,
                        )

    def _add_disconnected_trees(self, main_tree: Dict[str, Dict]):
        """
        Find individuals not in main tree and create separate tree groups.
        """
        connected_ids = set(main_tree.keys())
        disconnected_ids = set(self.individual_map.keys()) - connected_ids

        if not disconnected_ids:
            logger.info("No disconnected family trees found")
            return

        logger.info(f"Found {len(disconnected_ids)} people in disconnected trees")

        # Find separate tree roots (people with no parents in the disconnected set)
        tree_roots = []

        for person_id in disconnected_ids:
            individual = self.individual_map[person_id]
            families_as_child = getattr(
                individual, "get_families_as_child", lambda: []
            )()

            has_parent_in_disconnected = False
            for family in families_as_child:
                father_id = family.get("father")
                mother_id = family.get("mother")
                if (father_id and father_id in disconnected_ids) or (
                    mother_id and mother_id in disconnected_ids
                ):
                    has_parent_in_disconnected = True
                    break

            if not has_parent_in_disconnected:
                tree_roots.append(person_id)

        logger.info(f"Found {len(tree_roots)} disconnected tree roots")

        # Calculate offset for disconnected trees
        # Place them to the right of the main tree
        if self.nodes:
            max_x = max(node["x"] + node["width"] for node in self.nodes)
            offset_x = max_x + self.TREE_SPACING
        else:
            offset_x = 0

        # Build and position each disconnected tree
        for root_id in tree_roots:
            if root_id not in disconnected_ids:
                continue  # Already processed

            # Build tree structure for this root
            tree_structure = self._build_tree_structure(root_id)
            logger.info(
                f"  Disconnected tree from {root_id}: {len(tree_structure)} people"
            )

            # Update disconnected_ids to track what we've processed
            disconnected_ids -= set(tree_structure.keys())

            # Calculate positions
            positions = self._calculate_positions(tree_structure)

            # Offset positions
            offset_positions = {
                pid: (x + offset_x, y) for pid, (x, y) in positions.items()
            }

            # Create nodes and edges
            self._create_canvas_elements(offset_positions, tree_structure)

            # Update offset for next tree
            if offset_positions:
                max_x_in_tree = max(
                    x + self.NODE_WIDTH for x, y in offset_positions.values()
                )
                offset_x = max_x_in_tree + self.TREE_SPACING

    def _create_node(self, individual: Individual, x: int, y: int) -> str:
        """
        Create a canvas node for an individual.

        Returns the node ID.
        """
        node_id = str(uuid.uuid4().hex[:16])
        first_name, last_name = individual.get_names()

        # Get filename (same logic as in markdown generator)
        birth_year = ""
        events = getattr(individual, "get_events", lambda: [])()
        for event in events:
            if (event.get("type") == "BIRT") and event.get("date"):
                birth_year = extract_year(event.get("date", ""))
                if birth_year:
                    break

        # Build filename for WikiLink
        filename_parts = []
        if last_name:
            filename_parts.append(last_name)
        if first_name:
            filename_parts.append(first_name)
        if birth_year:
            filename_parts.append(birth_year)
        filename = " ".join(filename_parts)

        # Get images
        images = getattr(individual, "get_images", lambda: [])()
        has_image = len(images) > 0

        # Build node text content
        text_parts = []

        # Add image if available (use first image)
        if has_image:
            # images is a list of dicts with 'file', 'title', 'format' keys
            image_file = images[0].get("file", "")
            if image_file:
                text_parts.append(f"![Image]({image_file})")

        # Add WikiLink to person's markdown file
        text_parts.append(f"[[{filename}]]")

        node_text = "\n".join(text_parts)

        # Calculate height based on content
        height = self.IMAGE_HEIGHT if has_image else self.NODE_BASE_HEIGHT

        node = {
            "id": node_id,
            "type": "text",
            "text": node_text,
            "x": x,
            "y": y,
            "width": self.NODE_WIDTH,
            "height": height,
        }

        self.nodes.append(node)
        return node_id

    def _create_edge(
        self,
        from_node: str,
        to_node: str,
        label: str = "",
        from_side: str = "bottom",
        to_side: str = "top",
        bidirectional: bool = False,
    ):
        """
        Create a canvas edge between two nodes.

        Args:
            from_node: Source node ID
            to_node: Target node ID
            label: Edge label (optional)
            from_side: Which side of source node to connect from
            to_side: Which side of target node to connect to
            bidirectional: If True, adds arrow on fromEnd to make it bidirectional
        """
        edge_id = str(uuid.uuid4().hex[:16])

        edge = {
            "id": edge_id,
            "fromNode": from_node,
            "fromSide": from_side,
            "toNode": to_node,
            "toSide": to_side,
        }

        # Add label only if provided
        if label:
            edge["label"] = label

        # Add bidirectional arrow if requested
        if bidirectional:
            edge["fromEnd"] = "arrow"

        self.edges.append(edge)

    def _write_canvas_file(self, canvas_path: str):
        """
        Write canvas data to JSON file.
        """
        canvas_data = {"nodes": self.nodes, "edges": self.edges}

        with open(canvas_path, "w", encoding="utf-8") as f:
            json.dump(canvas_data, f, indent="\t")

        logger.info(f"Canvas file written to: {canvas_path}")
