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
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Tuple, Optional

from gedcom_parser import GedcomParser
from individual import Individual
from markdown_generator import MarkdownGenerator
from index_generator import IndexGenerator
from canvas_generator import CanvasGenerator
from person_selector import select_root_person


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


def extract_gedzip(zip_path: Path, temp_dir: Path) -> Tuple[Path, Optional[Path]]:
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
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.JPG", "*.JPEG", "*.PNG", "*.GIF", "*.BMP"]:
        media_files.extend(temp_dir.rglob(ext))

    if media_files:
        # Set media_dir to the extraction root so all subdirectories are accessible
        media_dir = temp_dir
        # Get unique parent directories for logging
        unique_dirs = sorted(set(f.parent for f in media_files))
        logger.info(f"Found {len(media_files)} media files across {len(unique_dirs)} directories")
        logger.debug(f"Media directories: {[str(d.relative_to(temp_dir)) for d in unique_dirs]}")

    return gedcom_file, media_dir


def convert_gedcom_to_markdown(
    gedcom_file: Path,
    output_dir: Path,
    create_index: bool = True,
    media_dir: Optional[Path] = None,
    use_flat_structure: bool = False,
    create_canvas: bool = False,
    root_id: Optional[str] = None,
    download_media: bool = False,
    media_download_timeout: int = 15,
    media_download_retries: int = 2,
    media_download_max_bytes: Optional[int] = None,
    media_download_concurrency: int = 4,
    media_download_rate: Optional[float] = None,
    media_download_enable_concurrency: bool = False,
    media_download_per_host_concurrency: int = 2,
    media_download_delay: Optional[float] = None,
    media_download_random_std: float = 0.0,
    media_download_max_backoff: float = 60.0,
    max_individuals: Optional[int] = None,
    media_subdir_name: Optional[str] = None,
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
            people_subdir_name = ""
        else:
            people_dir = output_dir / "people"
            # Use provided media_subdir_name when available, otherwise default to 'media'
            resolved_media_subdir = media_subdir_name if media_subdir_name else "media"
            media_output_dir = output_dir / resolved_media_subdir
            stories_dir = output_dir / "stories"
            media_subdir_name = resolved_media_subdir
            stories_subdir_name = "stories"
            people_subdir_name = "people"

            # Create subdirectories
            people_dir.mkdir(parents=True, exist_ok=True)
            media_output_dir.mkdir(parents=True, exist_ok=True)
            stories_dir.mkdir(parents=True, exist_ok=True)

        # Parse GEDCOM file
        logger.info(f"Parsing GEDCOM file: {gedcom_file}")
        parser = GedcomParser(gedcom_file)

        # Get all individuals
        individual_elements = parser.get_individuals()
        logger.info(f"Found {len(individual_elements)} individuals")

        if not individual_elements:
            logger.warning("No individuals found in GEDCOM file")
            return 1

        # Wrap individuals in our data model
        individuals = [Individual(elem, parser.parser) for elem in individual_elements]

        # Optionally limit the number of individuals processed (useful for testing)
        if max_individuals is not None and max_individuals > 0:
            individuals = individuals[:int(max_individuals)]

        # Generate canvas if requested
        if create_canvas:
            logger.info("Canvas generation requested")
            root_person_id = select_root_person(individuals, root_id)

            if root_person_id:
                logger.info(f"Generating canvas with root person: {root_person_id}")
                canvas_gen = CanvasGenerator(individuals, str(output_dir))
                canvas_path = canvas_gen.generate_canvas(root_person_id)
                logger.info(f"Canvas created: {canvas_path}")
            else:
                logger.warning("No root person selected, skipping canvas generation")

        # Generate markdown notes
        logger.info(f"Generating markdown notes in: {people_dir}")
        generator = MarkdownGenerator(
            output_dir,
            people_subdir=people_subdir_name,
            media_subdir=media_subdir_name,
            stories_subdir=stories_subdir_name,
            stories_dir=stories_dir,
            use_subdirectories=not use_flat_structure,
            download_media=download_media,
            download_timeout=media_download_timeout,
            download_retries=media_download_retries,
            download_max_bytes=media_download_max_bytes,
            download_concurrency=media_download_concurrency,
            download_rate=media_download_rate,
            enable_concurrency=media_download_enable_concurrency,
            per_host_concurrency=media_download_per_host_concurrency,
            download_delay=media_download_delay,
            download_randomize_std=media_download_random_std,
            max_backoff=media_download_max_backoff,
        )
        created_files = generator.generate_all(individuals)
        logger.info(f"Created {len(created_files)} markdown files")

        # Copy media files if available
        if media_dir and media_dir.exists():
            logger.info(f"Copying media files to: {media_output_dir}")

            # Allowed media extensions (case-insensitive)
            allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

            copied_count = 0
            skipped_count = 0
            collision_count = 0

            # Recursively find all files in media_dir
            for media_file in media_dir.rglob('*'):
                # Skip directories, only process files
                if not media_file.is_file():
                    continue

                # Filter by extension (case-insensitive)
                if media_file.suffix.lower() not in allowed_extensions:
                    continue

                # Compute relative path to preserve directory structure
                relative_path = media_file.relative_to(media_dir)
                dest = media_output_dir / relative_path

                # Handle filename collisions
                if dest.exists():
                    # Generate unique filename with numeric suffix
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

                # Ensure parent directory exists
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Copy file preserving metadata
                try:
                    shutil.copy2(media_file, dest)
                    copied_count += 1
                except (IOError, OSError) as e:
                    logger.exception(f"Failed to copy {media_file}")
                    skipped_count += 1

            logger.info(
                f"Copied {copied_count} media files "
                f"({collision_count} collisions resolved, {skipped_count} skipped)"
            )

        # Generate index
        if create_index:
            logger.info("Generating index file")
            people_subdir_name = "" if use_flat_structure else "people"
            index_gen = IndexGenerator(
                output_dir,
                people_subdir=people_subdir_name,
                filename_map=generator.filename_map
            )
            index_path = index_gen.generate_index(individuals)
            logger.info(f"Created index file: {index_path}")

        if download_media:
            logger.info("Downloading external media as final step")
            generator._download_external_media(individuals, media_output_dir)

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
        description=(
            "Convert GEDCOM genealogy files to Obsidian markdown notes. "
            "Supports organizing output into people/, media/, stories/, and sources/ subdirectories, "
            "optional canvas generation, and optional external media downloading with "
            "per-host concurrency, rate limiting, and retry/backoff behavior. A /sources directory will be created "
            "to hold original GEDCOM source files when present."
        ),
        epilog="Example: python src/main.py --input family.zip --output vault/family",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Input / Output
    io_group = parser.add_argument_group("Input/Output options")
    io_group.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to input GEDCOM (.ged) or GEDZIP (.zip) file",
    )
    io_group.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        metavar="DIR",
        help="Output directory for generated notes",
    )
    io_group.add_argument(
        "-f", "--flat",
        action="store_true",
        help="Use flat structure (all files in output root). Creates no subdirectories.",
    )
    io_group.add_argument(
        "-n", "--no-index",
        action="store_true",
        help="Do not create an index file",
    )
    io_group.add_argument(
        "-m", "--max-individuals",
        type=int,
        default=None,
        help="Only process the first N individuals (useful for testing).",
    )
    io_group.add_argument(
        "--media-folder",
        type=str,
        default="media",
        help="Name of the media folder to use under the output directory (default: 'media'). Person pages will link to ../<media-folder>/... when using subdirectories.",
    )

    # Canvas options
    canvas_group = parser.add_argument_group("Canvas options")
    canvas_group.add_argument(
        "-ca", "--canvas",
        action="store_true",
        help="Create an Obsidian canvas file for family tree visualization",
    )
    canvas_group.add_argument(
        "-r", "--root",
        type=str,
        metavar="ID",
        help=(
            "Root person for canvas. Can be a selection number (e.g., 85) or GEDCOM ID (e.g., @I253884714@). "
            "If not provided, will prompt interactively."
        ),
    )

    # Logging / behavior
    log_group = parser.add_argument_group("Logging and behavior")
    log_group.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # Media download options
    media_group = parser.add_argument_group("Media download options")
    media_group.add_argument(
        "-dm", "--download-media",
        action="store_true",
        help="Download external media files referenced by URLs.",
    )
    media_group.add_argument(
        "-dt", "--media-download-timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds when downloading media.",
    )
    media_group.add_argument(
        "-dr", "--media-download-retries",
        type=int,
        default=2,
        help="Number of retries for transient download failures.",
    )
    media_group.add_argument(
        "-db", "--media-download-max-bytes",
        type=int,
        default=None,
        help="Maximum number of bytes to download per media file (None = unlimited).",
    )

    # Concurrency and rate limiting
    media_group.add_argument(
        "-c", "--media-download-concurrency",
        type=int,
        default=4,
        help="Total number of concurrent media download workers.",
    )
    media_group.add_argument(
        "-mr", "--media-download-rate",
        type=float,
        default=None,
        help="Global rate limit (requests/sec) across all download workers.",
    )

    # Per-host concurrency: positive flag to enable per-host limits (disabled by default)
    media_group.add_argument(
        "-pm", "--media-per-host-limits",
        dest="media_download_enable_concurrency",
        action="store_true",
        help=(
            "Enable per-host concurrency controls to avoid overwhelming a single host. "
            "When enabled, per-host semaphores limit concurrent requests to the same host. Default: disabled."
        ),
    )

    media_group.add_argument(
        "-ph", "--per-host-concurrency",
        dest="media_download_per_host_concurrency",
        type=int,
        default=2,
        help="Maximum concurrent downloads per host when per-host concurrency is enabled.",
    )
    media_group.add_argument(
        "-dd", "--media-download-delay",
        type=float,
        default=None,
        help="Fixed delay (seconds) to wait between sequential requests (per-worker).",
    )
    media_group.add_argument(
        "-ds", "--media-download-random-std",
        type=float,
        default=0.0,
        help="Gaussian jitter standard deviation (seconds) applied to --media-download-delay.",
    )
    media_group.add_argument(
        "-mb", "--media-download-max-backoff",
        type=float,
        default=60.0,
        help="Maximum backoff in seconds when progressively backing off after repeated 429s.",
    )

    # Convenience combined flag: set both global and per-host concurrency with one value (e.g. "4,2")
    media_group.add_argument(
        "-mc", "--media-concurrency",
        type=str,
        default=None,
        help=(
            "Convenience: set both global and per-host concurrency in the form GLOBAL,PER_HOST. "
            "Example: --media-concurrency 4,2 will set --media-download-concurrency=4 and --media-download-per-host-concurrency=2. "
            "Overrides individual flags if provided."
        ),
    )

    args = parser.parse_args()

    # Prevent conflicting concurrency flags: if --media-concurrency provided, individual concurrency flags must not be present
    argv = sys.argv[1:]
    media_conc_flags = {"--media-concurrency", "-mc"}
    individual_flags = {"--media-download-concurrency", "-c", "--per-host-concurrency", "-ph"}
    if any(f in argv for f in media_conc_flags) and any(f in argv for f in individual_flags):
        parser.error("Cannot combine --media-concurrency with --media-download-concurrency or --per-host-concurrency; provide either combined or individual settings.")

    # Convenience: parse --media-concurrency if provided
    if getattr(args, 'media_concurrency', None):
        try:
            parts = [p.strip() for p in args.media_concurrency.split(',') if p.strip()]
            if len(parts) >= 1:
                args.media_download_concurrency = int(parts[0])
            if len(parts) >= 2:
                args.media_download_per_host_concurrency = int(parts[1])
        except Exception:
            parser.error("--media-concurrency expects two integers separated by a comma, e.g. '4,2'")

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Validate inputs
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    # Create output directory if it doesn't exist
    args.output.mkdir(parents=True, exist_ok=True)

    # Check if input is a ZIP file
    is_zip = args.input.suffix.lower() in [".zip", ".gedzip"]
    temp_dir = None
    gedcom_file = args.input
    media_dir = None

    try:
        if is_zip:
            # Extract ZIP file to temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix="gedcom_"))
            gedcom_file, media_dir = extract_gedzip(args.input, temp_dir)

        # Convert
        exit_code = convert_gedcom_to_markdown(
            gedcom_file=gedcom_file,
            output_dir=args.output,
            create_index=not args.no_index,
            media_dir=media_dir,
            use_flat_structure=args.flat,
            create_canvas=args.canvas,
            root_id=args.root,
            download_media=args.download_media,
            media_download_timeout=args.media_download_timeout,
            media_download_retries=args.media_download_retries,
            media_download_max_bytes=args.media_download_max_bytes,
            media_download_concurrency=args.media_download_concurrency,
            media_download_rate=args.media_download_rate,
            media_download_enable_concurrency=args.media_download_enable_concurrency,
            media_download_per_host_concurrency=args.media_download_per_host_concurrency,
            media_download_delay=args.media_download_delay,
            media_download_random_std=args.media_download_random_std,
            media_download_max_backoff=args.media_download_max_backoff,
            max_individuals=args.max_individuals,
            media_subdir_name=args.media_folder,
        )

        return exit_code

    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            logger.debug(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    sys.exit(main())
