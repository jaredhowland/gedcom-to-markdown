"""Example Canvas Plugin

A tiny plugin that creates a minimal Obsidian Canvas JSON file. This
package is provided as an example of how to publish a canvas plugin that
can be discovered by the main project via entry points.
"""

import os
import json


class ExampleCanvasPlugin:
    """Minimal example plugin for Obsidian Canvas generation."""

    def __init__(self, individuals, output_dir):
        self.individuals = individuals
        self.output_dir = output_dir

    def generate_canvas(self, root_person_id, canvas_filename="Family Tree.canvas"):
        """Create a minimal, valid JSON canvas file and return its path.

        This intentionally keeps the canvas content tiny — real plugins would
        generate richer node/edge structures.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, canvas_filename)
        canvas = {
            "type": "canvas",
            "meta": {"root": root_person_id},
            "nodes": [],
            "edges": [],
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(canvas, fh)
        except Exception:
            # Best-effort: don't fail the converter if writing the demo file fails
            pass
        return path
