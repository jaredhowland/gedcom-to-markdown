"""
Programmatic API for the converter.

Expose a simple `convert` function that returns a structured result and
delegates to the main conversion routine. This keeps a stable import
point for other tooling or tests.
"""

from pathlib import Path
from typing import Optional, Dict, Any


def convert(
    gedcom_file: Path,
    output_dir: Path,
    create_index: bool = True,
    media_dir: Optional[Path] = None,
    use_flat_structure: bool = False,
    create_canvas: bool = False,
    root_id: Optional[str] = None,
    plugin_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run conversion and return a structured result.

    Returns:
        dict containing keys: exit_code (int)
    """
    # Import the core conversion function from the module named 'main' which
    # lives on sys.path via pytest.ini (src on PYTHONPATH). This mirrors how
    # the codebase has historically been imported by tests and callers.
    try:
        from main import convert_gedcom_to_markdown as _convert
    except Exception:
        # Fallback to src.main if import as 'main' doesn't resolve
        from src.main import convert_gedcom_to_markdown as _convert

    exit_code = _convert(
        gedcom_file=gedcom_file,
        output_dir=output_dir,
        create_index=create_index,
        media_dir=media_dir,
        use_flat_structure=use_flat_structure,
        create_canvas=create_canvas,
        root_id=root_id,
        plugin_name=plugin_name,
    )

    return {"exit_code": exit_code}
