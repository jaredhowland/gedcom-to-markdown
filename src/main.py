#!/usr/bin/env python3
"""
GEDCOM to Markdown converter.

This script converts GEDCOM genealogy files into Obsidian-compatible
markdown notes with WikiLinks.
"""

__version__ = "1.0.0"

import argparse
import logging
import sys
import zipfile
import shutil
from pathlib import Path
from typing import Tuple, Optional, Any

from parser_io import parse_from_path

# Backwards-compatible import for external callers/tests
from gedcom_parser import GedcomParser  # noqa: E402
from individual import Individual
from markdown_generator import MarkdownGenerator
from index_generator import IndexGenerator
from canvas_plugin import get_canvas_plugin


def setup_logging(verbose: bool = False):
    """
    Configure root logger formatting and level for the application.

    Sets the logging level to DEBUG when `verbose` is True, otherwise to INFO
    for the main module only and WARNING for other modules.
    Also applies a consistent message format and timestamp date format used
    across the application.

    Parameters:
        verbose (bool): When True, enable DEBUG-level logging for all modules;
        otherwise use INFO-level logging for main module only.
    """
    if verbose:
        # Show all logs from all modules
        level = logging.DEBUG
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Only show INFO from main module, WARNING+ from others
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Enable INFO logging for main module only
        logging.getLogger(__name__).setLevel(logging.INFO)


def extract_gedzip(zip_path: Path, temp_dir: Path) -> Tuple[Path, Any]:
    """
    Extracts a ZIP/GEDZIP archive and locates the GEDCOM file and an optional
    media directory.

    Searches the extracted contents for the first `.ged` file and for image
    files (jpg, jpeg, png, gif, bmp) to identify a media directory.

    Returns:
        A tuple `(gedcom_file_path, media_directory_path)` where
        `gedcom_file_path` is the path to the found GEDCOM file and
        `media_directory_path` is the path to the directory containing media
        files or `None` if no media files were found.

    Raises:
        ValueError: If no GEDCOM (`.ged`) file is found in the archive.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Extracting ZIP archive: {zip_path}")

    # Extract the ZIP file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    logger.info(f"Extracted to: {temp_dir}")

    # Find the GEDCOM file (should have .ged extension)
    gedcom_files = list(temp_dir.glob("**/*.ged"))

    if not gedcom_files:
        raise ValueError("No GEDCOM (.ged) file found in the ZIP archive")

    if len(gedcom_files) > 1:
        logger.warning(
            f"Found {len(gedcom_files)} GEDCOM files, using first: {gedcom_files[0]}"
        )

    gedcom_file = gedcom_files[0]
    logger.info(f"Found GEDCOM file: {gedcom_file.name}")

    # Find media files across the entire extracted tree
    media_dir = None
    media_files = []
    for ext in [
        "*.jpg",
        "*.jpeg",
        "*.png",
        "*.gif",
        "*.bmp",
        "*.JPG",
        "*.JPEG",
        "*.PNG",
        "*.GIF",
        "*.BMP",
    ]:
        media_files.extend(temp_dir.rglob(ext))

    if media_files:
        # Set media_dir to the extraction root so all subdirectories are accessible
        media_dir = temp_dir
        # Get unique parent directories for logging
        unique_dirs = sorted(set(f.parent for f in media_files))
        logger.info(
            f"Found {len(media_files)} media files across {len(unique_dirs)} directories"
        )
        logger.debug(
            f"Media directories: {[str(d.relative_to(temp_dir)) for d in unique_dirs]}"
        )

    return gedcom_file, media_dir


def convert_gedcom_to_markdown(
    gedcom_file: Path,
    output_dir: Path,
    create_index: bool = True,
    media_dir: Optional[Path] = None,
    use_flat_structure: bool = False,
    create_canvas: bool = False,
    root_id: Optional[str] = None,
    plugin_name: Optional[str] = None,
) -> int:
    """
    Convert a GEDCOM file into Obsidian-compatible Markdown notes organized on disk.

    Parameters:
        gedcom_file (Path): Path to the input GEDCOM file.
        output_dir (Path): Directory where generated markdown, media, and
            story files will be written.
        create_index (bool): Whether to generate an index file linking the
            generated person notes.
        media_dir (Optional[Path]): Optional source directory of media files
            to copy into the output media directory.
        use_flat_structure (bool): If True, write all outputs directly into
            `output_dir`; if False, create subdirectories (`people/`,
            `media/`, `stories/`).
        create_canvas (bool): Whether to generate an Obsidian canvas file for
            family tree visualization.
        root_id (Optional[str]): Root person identifier for canvas generation.
            Can be a selection number (e.g., '85') or GEDCOM ID (e.g.,
            '@I253884714@' or 'I253884714'). If not provided and create_canvas
            is True, will prompt interactively.

    Returns:
        int: 0 on success, 1 on failure.
    """
    logger = logging.getLogger(__name__)

    try:
        # Determine directory structure
        if use_flat_structure:
            people_dir = output_dir
            media_output_dir = output_dir
            stories_dir = output_dir
            media_subdir_name = ""
            stories_subdir_name = ""
        else:
            people_dir = output_dir / "people"
            media_output_dir = output_dir / "media"
            stories_dir = output_dir / "stories"
            media_subdir_name = "media"
            stories_subdir_name = "stories"

            # Create subdirectories
            people_dir.mkdir(parents=True, exist_ok=True)
            media_output_dir.mkdir(parents=True, exist_ok=True)
            stories_dir.mkdir(parents=True, exist_ok=True)

        # Parse GEDCOM file
        logger.info(f"Parsing GEDCOM file: {gedcom_file}")
        # Use parse_from_path to keep file-level IO centralized
        parser = parse_from_path(gedcom_file)

        # Get all individuals
        individual_elements = parser.get_individuals()
        logger.info(f"Found {len(individual_elements)} individuals")

        if not individual_elements:
            logger.warning("No individuals found in GEDCOM file")
            return 1

        # Wrap individuals in our data model
        individuals = [Individual(elem, parser.parser) for elem in individual_elements]

        # Generate canvas if requested
        if create_canvas:
            logger.info("Canvas generation requested")
            # Interactive selector removed in refactor; accept explicit root_id only.
            if root_id:
                # Normalize GEDCOM ID if necessary
                root_person_id = root_id if root_id.startswith("@") else f"@{root_id}@"
                logger.info(f"Generating canvas with root person: {root_person_id}")
                # Allow selecting a registered plugin by name; default resolves to bundled CanvasGenerator
                plugin_cls = (
                    get_canvas_plugin(plugin_name)
                    if plugin_name
                    else get_canvas_plugin()
                )
                canvas_gen = plugin_cls(individuals, str(output_dir))
                canvas_path = canvas_gen.generate_canvas(root_person_id)
                logger.info(f"Canvas created: {canvas_path}")
            else:
                logger.warning(
                    "Interactive person selector removed; skipping canvas generation without explicit root_id"
                )

        # Generate markdown notes
        logger.info(f"Generating markdown notes in: {people_dir}")
        generator = MarkdownGenerator(
            people_dir,
            media_subdir=media_subdir_name,
            stories_subdir=stories_subdir_name,
            stories_dir=stories_dir,
            use_subdirectories=not use_flat_structure,
        )
        created_files = generator.generate_all(individuals)
        logger.info(f"Created {len(created_files)} markdown files")

        # Copy media files if available
        if media_dir and media_dir.exists():
            logger.info(f"Copying media files to: {media_output_dir}")
            try:
                from media_manager import copy_media

                media_map = copy_media(media_dir, media_output_dir)
                logger.info(f"Copied {len(media_map)} media files")
            except Exception:
                logger.exception(
                    "Media copying failed using MediaManager; falling back to ad-hoc copy"
                )
                # Fallback to previous ad-hoc behavior
                copied_count = 0
                skipped_count = 0
                collision_count = 0

                allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
                for media_file in media_dir.rglob("*"):
                    if not media_file.is_file():
                        continue
                    if media_file.suffix.lower() not in allowed_extensions:
                        continue
                    relative_path = media_file.relative_to(media_dir)
                    dest = media_output_dir / relative_path
                    if dest.exists():
                        original_dest = dest
                        counter = 1
                        stem = dest.stem
                        suffix = dest.suffix
                        while dest.exists():
                            dest = dest.parent / f"{stem}_{counter}{suffix}"
                            counter += 1
                        logger.warning(
                            f"Collision detected: {original_dest.name} -> {dest.name}"
                        )
                        collision_count += 1
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(media_file, dest)
                        copied_count += 1
                    except (IOError, OSError):
                        logger.exception(f"Failed to copy {media_file}")
                        skipped_count += 1
                logger.info(
                    f"Copied {copied_count} media files ({collision_count} collisions resolved, {skipped_count} skipped)"
                )

        # Generate index
        logger.debug(f"create_index flag value: {create_index!r}")
        logger.info(f"Effective create_index={create_index!r}")
        if create_index:
            logger.info("Generating index file")
            people_subdir_name = "" if use_flat_structure else "people"
            index_gen = IndexGenerator(
                output_dir,
                people_subdir=people_subdir_name,
                filename_map=generator.filename_map,
            )
            index_path = index_gen.generate_index(individuals)
            logger.info(f"Created index file: {index_path}")
        logger.info("Conversion completed successfully")
        return 0

    except FileNotFoundError:
        logger.exception("File not found")
        return 1
    except ValueError:
        logger.exception("Invalid input")
        return 1
    except Exception:
        logger.exception("Unexpected error")
        return 1

    finally:
        # Ensure that when create_index is False, no Index.md remains in the
        # output directory subtree. This also acts as a safeguard against any
        # code path that may have created an index despite the caller's flag.
        try:
            if not create_index:
                for idx in Path(output_dir).rglob("*"):
                    try:
                        if idx.is_file() and idx.name.lower() == "index.md":
                            logger.debug(f"(Cleanup) Removing stray Index.md: {idx}")
                            idx.unlink()
                    except Exception:
                        logger.exception(
                            f"(Cleanup) Failed to remove stray Index.md: {idx}"
                        )
        except Exception:
            logger.exception("(Cleanup) Failed to scan for stray Index.md files")
        # Log any remaining index files for debugging
        try:
            remaining = [
                str(p)
                for p in Path(output_dir).rglob("*")
                if p.is_file() and p.name.lower() == "index.md"
            ]
            if remaining:
                logger.info(
                    f"(Cleanup) Remaining index files after cleanup: {remaining}"
                )
            else:
                logger.info("(Cleanup) No index files remain after cleanup")
        except Exception:
            logger.exception("(Cleanup) Failed to list remaining index files")


def main():
    """
    Run the command-line interface to convert a GEDCOM or GEDZIP archive
    into Obsidian-compatible Markdown notes.

    Parses CLI arguments, prepares input and output paths (extracting
    archives to a temporary directory when needed), invokes the conversion
    process, and cleans up any temporary files.

    Returns:
        int: Exit code where `0` indicates success and `1` indicates failure.
    """
    parser = argparse.ArgumentParser(
        description="Convert GEDCOM genealogy files to Obsidian markdown notes",
        epilog="Example: python src/main.py --input family.zip --output vault/family",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to input GEDCOM (.ged) or GEDZIP (.zip) file",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        metavar="DIR",
        help="Output directory for generated notes",
    )

    parser.add_argument(
        "--flat",
        action="store_true",
        help="Use flat structure (all files in output root). Default creates subdirectories: people/, media/, stories/",
    )

    parser.add_argument(
        "--no-index", action="store_true", help="Do not create an index file"
    )

    parser.add_argument(
        "--canvas",
        action="store_true",
        help="Create an Obsidian canvas file for family tree visualization",
    )

    parser.add_argument(
        "--canvas-plugin",
        type=str,
        default="default",
        help="Canvas plugin name to use (entrypoint name or 'default')",
    )

    parser.add_argument(
        "--list-canvas-plugins",
        action="store_true",
        help="List available canvas plugins (discovered via entry points) and exit",
    )

    parser.add_argument(
        "--root",
        type=str,
        metavar="ID",
        help="Root person for canvas. Can be a selection number (e.g., 85) or GEDCOM ID (e.g., @I253884714@). If not provided, will prompt interactively.",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # If requested, list available canvas plugins and exit
    if getattr(args, "list_canvas_plugins", False):
        try:
            from canvas_plugin import list_plugins

            plugins = list_plugins()
            if not plugins:
                print("No canvas plugins registered")
            else:
                print("Available canvas plugins:")
                for name, cls in plugins.items():
                    module = getattr(cls, "__module__", "")
                    clsname = getattr(cls, "__name__", str(cls))
                    print(f"- {name}: {module}.{clsname}")
            return 0
        except Exception:
            logger.exception("Failed to list canvas plugins")
            return 1

    # Validate inputs
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    # Create output directory if it doesn't exist
    args.output.mkdir(parents=True, exist_ok=True)

    # Check if input is a ZIP file
    is_zip = args.input.suffix.lower() in [".zip", ".gedzip"]
    gedcom_file = args.input
    media_dir = None

    # If input is a ZIP, extract to a TemporaryDirectory that is auto-cleaned
    if is_zip:
        import tempfile as _tempfile

        with _tempfile.TemporaryDirectory(prefix="gedcom_") as _tmpdir:
            tmp_path = Path(_tmpdir)
            gedcom_file, media_dir = extract_gedzip(args.input, tmp_path)

            # Convert while tempdir is active
            exit_code = convert_gedcom_to_markdown(
                gedcom_file=gedcom_file,
                output_dir=args.output,
                create_index=not args.no_index,
                media_dir=media_dir,
                use_flat_structure=args.flat,
                create_canvas=args.canvas,
                root_id=args.root,
                plugin_name=args.canvas_plugin,
            )
            return exit_code

    # Non-zip: convert directly
    exit_code = convert_gedcom_to_markdown(
        gedcom_file=gedcom_file,
        output_dir=args.output,
        create_index=not args.no_index,
        media_dir=media_dir,
        use_flat_structure=args.flat,
        create_canvas=args.canvas,
        root_id=args.root,
        plugin_name=args.canvas_plugin,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
