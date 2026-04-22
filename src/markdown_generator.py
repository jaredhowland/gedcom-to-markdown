"""
Markdown note generator for Obsidian.

This module generates Obsidian-compatible markdown notes for individuals
in the family tree.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import urllib.request
import urllib.error
import socket
import hashlib
import mimetypes
import time
import urllib.parse
import os
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
import threading
import concurrent.futures
import random

import logging
import re

from individual import Individual
from utils import resolve_gedcom_text
from utils import (
    collapse_single_line,
    collapse_preserve_lines,
    escape_markdown,
    repair_broken_html_tags,
    write_multiline_note_block,
)
from utils import FilenameRegistry  # canonical filename utility
import io
from io_manager import write_text_file


logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """
    Generates Obsidian markdown notes for individuals.

    This class handles formatting individual data into Obsidian-compatible
    markdown with WikiLinks and metadata.
    """

    def __init__(
        self,
        output_dir: Path,
        people_subdir: str = "",
        media_subdir: str = "",
        stories_subdir: str = "",
        stories_dir: Optional[Path] = None,
        use_subdirectories: bool = False,
        download_media: bool = False,
        download_timeout: int = 15,
        download_retries: int = 2,
        download_max_bytes: Optional[int] = None,
        download_concurrency: int = 4,
        download_rate: Optional[float] = None,
        enable_concurrency: bool = True,
        per_host_concurrency: int = 2,
        download_delay: Optional[float] = None,
        download_randomize_std: float = 0.0,
        max_backoff: float = 60.0,
        filename_registry: "FilenameRegistry | None" = None,
        **kwargs,
    ):
        """
        Configure the MarkdownGenerator with paths and optional subdirectories for media and story files.

        Parameters:
            output_dir (Path): Directory where markdown notes will be written; must exist and be a directory.
            media_subdir (str): Optional subdirectory name (relative) to prefix media/image paths in notes.
            stories_subdir (str): Optional subdirectory name (relative) to use when constructing wiki links to generated story notes.
            stories_dir (Optional[Path]): Optional directory where story markdown files will be created; defaults to `output_dir` when not provided.
            use_subdirectories (bool): Whether the output structure uses subdirectories (people/, stories/, media/). When True, WikiLinks and image paths will include appropriate subdirectory prefixes.
            filename_registry (FilenameRegistry | None): Optional registry instance to assign deterministic unique filenames across multiple generators; created when not provided.

        Raises:
            ValueError: If `output_dir` does not exist or is not a directory.
        """
        if not output_dir.exists():
            raise ValueError(f"Output directory doesn't exist: {output_dir}")
        if not output_dir.is_dir():
            raise ValueError(f"Output path is not a directory: {output_dir}")

        self.output_dir = output_dir
        self.people_subdir = people_subdir
        self.media_subdir = media_subdir
        self.stories_subdir = stories_subdir
        self.stories_dir = stories_dir if stories_dir else output_dir
        self.use_subdirectories = use_subdirectories
        self.generated_stories = {}  # Track generated story files
        self.generated_media = {}  # Track generated media files (external URL pages)
        self.generated_media_data = {}  # Track media note contents for rewrite after downloads
        self.filename_map = {}  # Map from individual ID to actual filename used
        # Support legacy keyword names passed by tests or other callers
        # Map older media_* names to internal download_* equivalents
        legacy_map = {
            'media_download_concurrency': ('download_concurrency', int),
            'media_download_rate': ('download_rate', float),
            'media_download_enable_concurrency': ('enable_concurrency', bool),
            'media_download_per_host_concurrency': ('per_host_concurrency', int),
            'media_download_delay': ('download_delay', float),
            'media_download_random_std': ('download_randomize_std', float),
            'media_download_max_backoff': ('max_backoff', float),
            'media_download_timeout': ('download_timeout', int),
            'media_download_retries': ('download_retries', int),
            'media_download_max_bytes': ('download_max_bytes', int),
            'media_download_enable': ('download_media', bool),
        }
        for old_key, (new_key, cast) in legacy_map.items():
            if old_key in kwargs:
                try:
                    val = kwargs.pop(old_key)
                    # Special-case boolean flags that may come as strings
                    if cast is bool and isinstance(val, str):
                        val = val.lower() in ('1', 'true', 'yes')
                    setattr(self, new_key, cast(val) if val is not None else None)
                except Exception:
                    # Ignore conversion errors and leave defaults
                    pass

        # Download settings
        # If legacy mapping assigned attributes above, use them; otherwise use parameters
        self.download_media = getattr(self, 'download_media', download_media)
        self.download_timeout = getattr(self, 'download_timeout', download_timeout)
        self.download_retries = getattr(self, 'download_retries', download_retries)
        # Maximum bytes to download for any single media file (None for unlimited)
        self.download_max_bytes = getattr(self, 'download_max_bytes', download_max_bytes)
        # Concurrency and rate limiting for downloads
        self.download_concurrency = max(1, int(getattr(self, 'download_concurrency', download_concurrency))) if download_concurrency else 1
        self.download_rate = getattr(self, 'download_rate', float(download_rate) if download_rate else None)
        # Concurrency enable/disable and per-host concurrency
        self.enable_concurrency = getattr(self, 'enable_concurrency', bool(enable_concurrency))
        self.per_host_concurrency = max(1, int(getattr(self, 'per_host_concurrency', per_host_concurrency)))
        # Fixed delay between sequential requests (seconds); optional Gaussian randomization
        self.download_delay = getattr(self, 'download_delay', float(download_delay) if download_delay is not None else None)
        self.download_randomize_std = getattr(self, 'download_randomize_std', float(download_randomize_std) if download_randomize_std else 0.0)
        # Maximum backoff cap
        self.max_backoff = getattr(self, 'max_backoff', float(max_backoff))
        # Download cache and sync primitives
        self._downloaded_cache: Dict[str, Optional[str]] = {}
        self._cache_lock = threading.Lock()
        self._last_request_time = 0.0
        self._rate_lock = threading.Lock()
        # Per-host semaphores and next-allowed timestamps
        self._host_semaphores: Dict[str, threading.Semaphore] = {}
        self._host_next_allowed: Dict[str, float] = {}
        self._host_lock = threading.Lock()
        self._reserved_download_filenames = set()
        self._reserved_download_lock = threading.Lock()
        # Use provided registry or create a new one for deterministic naming
        self.filename_registry = filename_registry or FilenameRegistry()
        self._sources_index_generated = False  # Ensure global sources index is created only once

    def _coordinate_values(
        self, data: dict, lat_key: str = "lat", long_key: str = "long"
    ) -> List[str]:
        """Return non-empty coordinate values from a mapping in latitude/longitude order."""
        coords = []
        lat_val = data.get(lat_key)
        long_val = data.get(long_key)
        if lat_val:
            coords.append(lat_val)
        if long_val:
            coords.append(long_val)
        return coords

    def _get_unique_filename(self, base_name: str, individual_id: str) -> str:
        """
        Use the FilenameRegistry to reserve and return a deterministic unique name.
        """
        unique_name = self.filename_registry.reserve(individual_id, base_name)
        # Keep compatibility mapping
        self.filename_map[individual_id] = unique_name
        return unique_name

    def generate_note(self, individual: Any) -> Path:
        """
        Create a markdown file for the given individual containing YAML frontmatter, header, events, families, parents, children, images, and notes sections.

        Parameters:
            individual (Individual): The individual for whom to generate the note.

        Returns:
            Path: Path to the created markdown file.
        """
        base_name = individual.get_file_name()
        unique_name = self._get_unique_filename(base_name, individual.get_id())
        filename = unique_name + ".md"
        # Determine person directory: if people_subdir configured, write into that subdir under output_dir
        person_dir = self.output_dir / self.people_subdir if getattr(self, 'people_subdir', '') else self.output_dir
        person_dir.mkdir(parents=True, exist_ok=True)
        file_path = person_dir / filename

        logger.info(f"Generating note: {filename}")

        # Build content in-memory using a StringIO buffer, then delegate writing to io_manager
        buf = io.StringIO()
        # Write all sections into the buffer
        self._write_frontmatter(buf, individual)
        self._write_header(buf, individual)
        self._write_events(buf, individual)
        self._write_families(buf, individual)
        self._write_parents(buf, individual)
        self._write_children(buf, individual)
        self._write_images(buf, individual)
        self._write_notes(buf, individual)
        # Write Sources section (if any)
        self._write_sources(buf, individual)

        # Flush buffer content to disk via central IO manager
        content = buf.getvalue()
        write_text_file(file_path, content)

        # Generate global sources index once if not already generated. This preserves the behavior
        # expected by callers that invoke generate_note() directly (unit tests), while avoiding
        # O(N^2) behavior when multiple notes are generated via generate_all().
        if not getattr(self, "_sources_index_generated", False):
            parser = getattr(individual, "gedcom", None)
            if parser:
                try:
                    self._generate_sources_index(parser)
                except (OSError, AttributeError, ValueError):
                    logger.exception("Failed to generate sources index")
                    # Prevent repeated expensive retries on persistent failures (e.g., IO/permissions)
                    self._sources_index_generated = True

        return file_path

    def _write_frontmatter(self, f, individual: Any):
        """
        Write YAML frontmatter containing individual attributes.

        Parameters:
            f (IO[str]): Open text file or writable stream to receive YAML frontmatter.
            individual (Individual): Person whose attributes are written to frontmatter.
        """
        f.write("---\n")

        birth = individual.get_birth_info()
        death = individual.get_death_info()
        fs_id = getattr(individual, "get_fs_id", lambda: "")()

        f.write(f"ID: {individual.get_id()}\n")
        if fs_id:
            f.write(f"FamilySearch ID: {fs_id}\n")
        f.write(f"Name: {individual.get_full_name()}\n")

        # Lived years
        birth_year = birth.get("year", "")
        death_year = death.get("year", "")
        if birth_year or death_year:
            lived = f"{birth_year}-{death_year}"
            f.write(f"Lived: {lived}\n")

        f.write(f"Sex: {individual.get_gender()}\n")

        # Birth details
        birth_date = birth.get("date", "")
        birth_place = birth.get("place", "")
        if birth_date:
            f.write(f"Born: {birth_date}\n")
        if birth_place:
            f.write(f"Place of birth: {birth_place}\n")
        # Birth coordinates should be emitted even if place is empty
        birth_coords = self._coordinate_values(birth)
        if birth_coords:
            f.write(f"Birth coordinates: {', '.join(birth_coords)}\n")

        # Death details
        death_date = death.get("date", "")
        death_place = death.get("place", "")
        if death_date:
            f.write(f"Passed away: {death_date}\n")
        if death_place:
            f.write(f"Place of death: {death_place}\n")
        # Death coordinates should be emitted even if place is empty
        death_coords = self._coordinate_values(death)
        if death_coords:
            f.write(f"Death coordinates: {', '.join(death_coords)}\n")

        # Physical attributes
        attrs = individual.get_attributes()
        for key, value in attrs.items():
            if value:
                f.write(f"{key.capitalize()}: {value}\n")

        f.write("---\n\n")

    def _write_header(self, f, individual: Individual):
        """
        Write the main markdown header containing the individual's full name.

        Parameters:
            f (IO[str]): Open text file or writable stream to receive markdown content.
            individual (Individual): Person whose full name is written as the top-level header.
        """
        f.write(f"# {individual.get_full_name()}\n\n")

    def _write_events(self, f, individual: Individual):
        """
        Write the "Life Events" section for an individual into the open file.

        Writes a "Life Events" header and a subsection for each event other than birth or death. For each event, emits Date, Place, and Details lines when those values are present. Maps common GEDCOM-like event codes to readable names (e.g., 'MARR' -> Marriage, 'OCCU' -> Occupation, 'EDUC' -> Education, 'RESI' -> Residence, 'BURI' -> Burial). If the individual has no other events, nothing is written.

        Parameters:
            f: A writable text file object positioned where the section should be written.
            individual (Individual): An object providing event data via get_events(), where each event is a dict containing at least 'type', 'date', 'place', and 'details'.
        """
        events = getattr(individual, "get_events", lambda: [])()

        # Filter out birth and death (already in attributes)
        other_events = [e for e in events if e.get("type") not in ["BIRT", "DEAT"]]

        if not other_events:
            return

        f.write("## Life Events\n")

        event_names = {
            "MARR": "Marriage",
            "OCCU": "Occupation",
            "EDUC": "Education",
            "RESI": "Residence",
            "BURI": "Burial",
        }

        for event in other_events:
            etag = event.get("type", "")
            event_type = event_names.get(etag, etag)
            f.write(f"### {event_type}\n")

            date = event.get("date", "")
            if date:
                f.write(f"- **Date**: {date}\n")

            # Always compute coordinates, emit regardless of whether place is present
            coords = self._coordinate_values(event)
            place = event.get("place", "")
            if place:
                f.write(f"- **Place**: {place}\n")
            if coords:
                f.write(f"- **Coordinates**: {', '.join(coords)}\n")
            details = event.get("details", "")
            if details:
                f.write(f"- **Details**: {details}\n")

            f.write("\n")

        f.write("\n")

    def _write_families(self, f, individual: Individual):
        """
        Write the "Families" section for an individual into the provided file handle.

        Emits a "## Families" header and, for each family, a "Marriage" subsection (numbered when the individual has multiple families). For each family the function writes bullet points for Partner (as a wiki link, if partner is present), Marriage date, Marriage place (if present), and lists each Child as bullet points (as wiki links). Adds spacing after each family and a trailing blank line after the section. If the individual has no families, nothing is written.

        Parameters:
            f (io.TextIO): Open text file handle to write the section into.
            individual (Individual): The individual whose family records will be written.
        """
        families = individual.get_families()

        if not families:
            return

        f.write("## Families\n")

        for i, family in enumerate(families, 1):
            # Always write the Marriage header
            f.write(f"### Marriage{f' {i}' if len(families) > 1 else ''} \n")

            # Only write partner bullet if partner exists
            if family["partner"]:
                partner_name = self._get_actual_filename(family["partner"])
                f.write(f"* Partner: {self._wiki_link(partner_name)}\n")

            # Write marriage bullets if present
            if family["marriage_date"]:
                f.write(f"* Marriage date: {family['marriage_date']}\n")
            if family["marriage_place"]:
                f.write(f"* Marriage place: {family['marriage_place']}\n")
            # Marriage coordinates should be emitted regardless of whether place is present
            mcoords = self._coordinate_values(family, "marriage_lat", "marriage_long")
            if mcoords:
                f.write(f"* Marriage coordinates: {', '.join(mcoords)}\n")

            # Write children if they exist
            if family["children"]:
                f.write("\n**Children:**\n")
                partner = family.get("partner")
                partner_pointer = (
                    partner.get_pointer() if hasattr(partner, "get_pointer") else None
                )
                for child in family["children"]:
                    # Defensive: skip rendering a child entry if their pointer matches the partner
                    child_pointer = getattr(child, "get_pointer", lambda: None)()
                    if child_pointer and partner_pointer and child_pointer == partner_pointer:
                        logger.debug(
                            "Skipping rendering child %s for family because it matches partner",
                            child_pointer,
                        )
                        continue
                    f.write(
                        f"* Child: {self._wiki_link(self._get_actual_filename(child))}\n"
                    )

            f.write("\n")

        f.write("\n")

    def _write_parents(self, f, individual: Individual):
        """
        Write the Parents section for an individual note, including the relationship label
        (e.g., Mother, Father, Step-father) when it can be inferred.

        Parameters:
            f: A writable text file-like object opened for the individual's markdown note.
            individual (Individual): The individual whose parents should be written.
        """
        parents = getattr(individual, "get_parents", lambda: [])()

        if not parents:
            return

        # Attempt to infer parental roles from the family records where this person is a child
        families_as_child = individual.get_families_as_child()
        father_ids = set()
        mother_ids = set()
        for fam in families_as_child:
            if fam.get('father'):
                father_ids.add(fam['father'])
            if fam.get('mother'):
                mother_ids.add(fam['mother'])

        f.write("## Parents\n")

        for parent in parents:
            ptr = parent.get_pointer()
            # Default label
            label = "Parent"
            if ptr in father_ids:
                label = "Father"
            elif ptr in mother_ids:
                label = "Mother"
            else:
                # If not matched to father/mother, try to infer step-parent from gender
                gender = parent.get_gender()
                if gender == 'M':
                    label = "Step-father"
                elif gender == 'F':
                    label = "Step-mother"

            f.write(f"* {label}: {self._wiki_link(self._get_actual_filename(parent))}\n")

        f.write("\n")

    def _write_children(self, f, individual: Individual):
        """
        Write a "Children" section listing each child as a bullet point with a wiki link.

        Does nothing if the individual has any families or has no children.
        """
        # Skip if we already wrote families section
        if getattr(individual, "get_families", lambda: [])():
            return

        children = getattr(individual, "get_children", lambda: [])()

        if not children:
            return

        f.write("## Children\n")

        for child in children:
            f.write(f"* Child: {self._wiki_link(self._get_actual_filename(child))}\n")

        f.write("\n")

    def _write_images(self, f, individual: Individual):
        """
        Write image sections to the open file for all images returned by the individual.

        Local media files are written as inline Markdown image references under a
        "## Images" heading. External URLs (http/https) are written under a
        "## External media" heading as a bullet list with the original URL preserved;
        they are not downloaded or linked to separate media files here.

        If the individual has no images, nothing is written.
        """
        images = getattr(individual, "get_all_media", None)
        if images is None:
            images = getattr(individual, "get_images", lambda: [])
        images = images()
        if not images:
            return

        # Separate local vs external images
        local_images = []
        external_images = []
        for image in images:
            file_val = image.get("file", "")
            if isinstance(file_val, str) and (file_val.startswith("http://") or file_val.startswith("https://")):
                external_images.append(image)
            else:
                local_images.append(image)

        # Write local images inline as before
        if local_images:
            f.write("## Images\n")
            person_alt = individual.get_full_name()
            for image in local_images:
                title = image.get("title") or person_alt
                filename = image.get("file")
                if self.use_subdirectories and self.media_subdir:
                    image_path = f"../{self.media_subdir}/{filename}"
                elif self.media_subdir:
                    image_path = f"{self.media_subdir}/{filename}"
                else:
                    image_path = filename
                f.write(f"![{title}]({image_path})\n\n")
            f.write("\n")

        # External images will be handled during the download pass which embeds local files into person notes.
        # Do not create separate media markdown files here; external images will be mapped and embedded after download.
        if external_images:
            if self.download_media:
                # Leave a marker for downstream rewrite, the download phase will reconstruct the Images section
                f.write("## External media\n\n")
                person_alt_ext = individual.get_full_name()
                for image in external_images:
                    title = image.get("title") or person_alt_ext
                    file_val = image.get("file")
                    f.write(f"- {title}: {file_val}\n")
                f.write("\n")
            else:
                # When not downloading media, link directly from the person's note to the external URL.
                # Use numbered fallback titles when a title is missing.
                f.write("## External media\n\n")
                for idx, image in enumerate(external_images, start=1):
                    raw_title = image.get("title")
                    title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else f"External File {idx}"
                    file_val = image.get("file")
                    f.write(f"- [{title}]({file_val})\n")
                f.write("\n")

    def _generate_story_file(self, story: dict, individual_name: str) -> str:
        """
        Generate a separate markdown file for a story and return the story note name.

        Parameters:
            story (dict): Story data containing keys:
                - title (str | None): Story title; "Untitled Story" used if empty.
                - description (str | None): Optional short description placed under the title.
                - sections (List[dict]): Ordered sections; each section may contain
                    'subtitle' (str | None), 'text' (str | None), and 'images' (List[dict]).
                    Images should be dicts with 'file' (str) and optional 'title' (str).
            individual_name (str): Full name of the individual the story relates to; used for a back-link.

        Returns:
            str: The generated story note name (filename without the ".md" extension). If a story file with the same filename was already created, returns the existing note name.
        """
        story_title = story["title"] if story["title"] else "Untitled Story"
        # Create a safe filename
        safe_title = story_title.replace("/", "-").replace("\\", "-")
        filename = f"{safe_title}.md"
        file_path = self.stories_dir / filename

        # Check if we've already generated this story
        if filename in self.generated_stories:
            return filename.replace(".md", "")

        logger.debug(f"Generating story file: {filename}")

        # Build story content in-memory and write via IO manager
        buf = io.StringIO()
        # Write story header
        buf.write(f"# {story_title}\n\n")

        # Write description if available
        if story["description"]:
            buf.write(f"*{story['description']}*\n\n")

        # Link back to the individual
        # If using subdirectories, stories are in stories/ and people are in people/
        if self.use_subdirectories:
            person_link = f"[[people/{individual_name}|{individual_name}]]"
        else:
            person_link = f"[[{individual_name}]]"

        buf.write(f"**Related to:** {person_link}\n\n")
        buf.write("---\n\n")

        # Write each section
        for section in story["sections"]:
            if section["subtitle"]:
                buf.write(f"## {section['subtitle']}\n\n")

            if section["text"]:
                buf.write(f"{section['text']}\n\n")

            # Write images for this section
            if section["images"]:
                for img in section["images"]:
                    title = img["title"] if img["title"] else "Image"
                    filename_img = img["file"]
                    # Add media subdirectory prefix if using subdirectory structure
                    if self.use_subdirectories and self.media_subdir:
                        image_path = f"../{self.media_subdir}/{filename_img}"
                    else:
                        image_path = filename_img
                    buf.write(f"![{title}]({image_path})\n\n")

        # Write to disk
        write_text_file(file_path, buf.getvalue())

        # Track that we've generated this story
        self.generated_stories[filename] = True

        # Return the note name for WikiLink (without .md extension)
        note_name = filename.replace(".md", "")

        # Return note name
        
        return note_name

    def _generate_media_file(self, media_entries: List[Dict], individual_name: str) -> str:
        """
        Generate (or reuse) a markdown file in the media directory that embeds external media URLs.
        Returns note name (without .md) suitable for WikiLink creation.
        """
        # Create safe filename
        safe_name = individual_name.replace("/", "-").replace("\\", "-")
        filename = f"{safe_name} External Media.md"

        # Reuse if already generated
        if filename in self.generated_media:
            return filename.replace(".md", "")

        # Determine directory to write media files
        if self.media_subdir:
            media_dir = self.output_dir / self.media_subdir
        else:
            media_dir = self.output_dir

        media_dir.mkdir(parents=True, exist_ok=True)
        file_path = media_dir / filename

        logger.debug(f"Generating media file: {filename}")

        self.generated_media_data[filename] = {
            "individual_name": individual_name,
            "entries": media_entries,
            "path": file_path,
        }
        self._write_media_file(file_path, individual_name, media_entries)

        self.generated_media[filename] = True
        return filename.replace(".md", "")

    def _write_media_file(self, file_path: Path, individual_name: str, media_entries: List[Dict]):
        """
        Write a media note using the current download cache when available.
        """
        with open(file_path, "w", encoding="utf-8") as mf:
            mf.write(f"# External media for {individual_name}\n\n")
            for entry in media_entries:
                title = entry.get("title") or individual_name
                url = entry.get("file")

                with self._cache_lock:
                    local_filename = self._downloaded_cache.get(url) if url else None

                mf.write(f"## {title}\n\n")

                if local_filename:
                    if self.media_subdir:
                        target_path = self.output_dir / self.media_subdir / local_filename
                    else:
                        target_path = self.output_dir / local_filename
                    rel = os.path.relpath(target_path, start=file_path.parent).replace(os.sep, "/")
                    mf.write(f"![{title}]({rel})\n\n")
                    mf.write(f"[Local file]({rel})\n\n")
                else:
                    mf.write(f"![{title}]({url})\n\n")
                    mf.write(f"[Original URL]({url})\n\n")

    def _download_url(self, url: str, media_dir: Path) -> Optional[str]:
        """
        Download a URL into media_dir and return the saved filename, or raise on unrecoverable failure.

        Behavior:
        - Respects self.download_timeout and self.download_retries.
        - Uses exponential backoff between retries.
        - Honors HTTP 429 Retry-After header (seconds or HTTP-date).
        - Writes files atomically using a temporary file + os.replace.
        - Sanitizes filenames derived from the URL path; falls back to a hash when necessary.
        - Attempts to infer file extension from Content-Type when missing.
        """
        media_dir.mkdir(parents=True, exist_ok=True)

        parsed = urllib.parse.urlparse(url)
        basename = os.path.basename(parsed.path)
        if basename:
            basename = urllib.parse.unquote(basename)
        else:
            basename = hashlib.sha256(url.encode('utf-8')).hexdigest()

        # Sanitize base name
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", basename)
        base, ext = os.path.splitext(base_name)

        # If no extension, we'll try to infer it after fetching
        ext = ext or ""

        attempts = 0
        max_attempts = max(1, self.download_retries + 1)
        backoff_base = 0.5

        def _parse_retry_after(value: Optional[str]) -> Optional[int]:
            if not value:
                return None
            value = value.strip()
            if value.isdigit():
                try:
                    return int(value)
                except Exception:
                    return None
            # Try to parse HTTP-date
            try:
                dt = parsedate_to_datetime(value)
                # Convert to UTC-aware datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                delay = (dt - datetime.now(timezone.utc)).total_seconds()
                return max(0, int(delay))
            except Exception:
                return None

        while attempts < max_attempts:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "gedcom-to-markdown/1.0"})
                with urllib.request.urlopen(req, timeout=self.download_timeout) as resp:
                    # Try to infer extension from headers before streaming
                    try:
                        ctype = resp.getheader("Content-Type")
                    except Exception:
                        ctype = None
                    if not ext and ctype:
                        guessed = mimetypes.guess_extension(ctype.split(";")[0].strip())
                        if guessed:
                            ext = guessed
                    filename = f"{base}{ext}"
                    dest = media_dir / filename

                    # Resolve collisions under lock so concurrent downloads do not
                    # choose the same target before either file is written.
                    counter = 1
                    with self._reserved_download_lock:
                        unique_dest = dest
                        while unique_dest.exists() or str(unique_dest) in self._reserved_download_filenames:
                            unique_dest = dest.parent / f"{dest.stem}_{counter}{dest.suffix}"
                            counter += 1
                        self._reserved_download_filenames.add(str(unique_dest))

                    tmp = None
                    tmpf = None
                    try:
                        tmpf = tempfile.NamedTemporaryFile(delete=False, dir=str(media_dir))
                        tmp = tmpf.name
                        total = 0
                        chunk_size = 8192
                        single_read_mode = False
                        while True:
                            try:
                                chunk = resp.read(chunk_size)
                            except TypeError:
                                # Some fake responses implement read() without a size argument
                                chunk = resp.read()
                                # If the response only supports a single read() call that returns
                                # the entire body, avoid looping forever by breaking after the first
                                # successful read.
                                single_read_mode = True
                            if not chunk:
                                break
                            # If chunk is str (unlikely), convert to bytes
                            if isinstance(chunk, str):
                                chunk = chunk.encode('utf-8')
                            tmpf.write(chunk)
                            total += len(chunk)
                            if self.download_max_bytes is not None and total > self.download_max_bytes:
                                # Exceeded allowed size; abort and remove temp
                                try:
                                    tmpf.close()
                                except Exception:
                                    pass
                                try:
                                    os.remove(tmp)
                                except Exception:
                                    pass
                                logger.warning(f"Download exceeded max bytes for {url}")
                                # Do not raise to let caller handle fallback; return None
                                return None
                            if single_read_mode:
                                # We've consumed the entire response in a single read() call; stop looping
                                break
                        tmpf.flush()
                        os.fsync(tmpf.fileno())
                        tmpf.close()
                        os.replace(tmp, str(unique_dest))
                    finally:
                        if tmp and os.path.exists(tmp):
                            try:
                                os.remove(tmp)
                            except Exception:
                                pass
                        with self._reserved_download_lock:
                            self._reserved_download_filenames.discard(str(unique_dest))

                    return unique_dest.name

            except urllib.error.HTTPError as e:
                # Respect 429 Retry-After specially
                code = getattr(e, 'code', None)
                retry_after = None
                try:
                    headers = getattr(e, 'headers', None)
                    if headers:
                        # headers might be a dict-like or email.message.Message
                        retry_after = headers.get('Retry-After') if hasattr(headers, 'get') else None
                except Exception:
                    retry_after = None

                if code == 429:
                    # Determine delay from Retry-After header or exponential backoff
                    parsed_retry_after = _parse_retry_after(retry_after)
                    delay = parsed_retry_after if parsed_retry_after is not None else (backoff_base * (2 ** attempts))
                    # Cap backoff
                    delay = min(delay, self.max_backoff)
                    # Set per-host pause so other workers respect the server's rate limit
                    host = parsed.hostname or parsed.netloc
                    with self._host_lock:
                        self._host_next_allowed[host] = time.time() + delay

                    # Sleep and retry with increased attempts
                    time.sleep(delay)
                    attempts += 1
                    continue

                # For 5xx errors, retry with backoff
                if code and 500 <= code < 600 and attempts < max_attempts - 1:
                    delay = backoff_base * (2 ** attempts)
                    time.sleep(delay)
                    attempts += 1
                    continue

                # Non-retryable HTTP error
                raise

            except (urllib.error.URLError, socket.timeout) as e:
                # Transient network errors: retry with exponential backoff
                if attempts < max_attempts - 1:
                    delay = backoff_base * (2 ** attempts)
                    time.sleep(delay)
                    attempts += 1
                    continue
                raise

        return None

    def _write_notes(self, f, individual: Individual):
        """
        Write the "Notes" section for an individual, including inline notes and links to separate story files.

        If the individual has no notes and no stories, nothing is written. For each regular note, writes the note text into the section. For each story, generates or reuses a story markdown file via the generator, then writes a WikiLink to that story (prefixed with the configured stories subdirectory when present) and includes the story's description on the same line if provided.

        Parameters:
            f: A writable text file object opened for the individual's markdown note.
            individual (Individual): The individual whose notes and stories will be rendered.
        """
        notes = getattr(individual, "get_notes", lambda: [])()
        stories = getattr(individual, "get_stories", lambda: [])()

        if not notes and not stories:
            return

        f.write("## Notes\n")

        # Write regular notes
        for note in notes:
            # Repair broken HTML tags that may span lines, then split into lines
            repaired = self._repair_broken_html_tags(note)
            lines = repaired.splitlines()
            # Escape markdown in each line to avoid accidental emphasis, then write
            esc_lines = [self._escape_markdown(ln) for ln in lines]
            self._write_multiline_note_block(f, esc_lines, nested=False)
            f.write("\n")

        # Generate separate story files and link to them
        if stories:
            f.write("### Stories\n\n")
            individual_name = self._get_actual_filename(individual)

            for story in stories:
                # Generate the story file
                story_note_name = self._generate_story_file(story, individual_name)

                # Create a WikiLink to the story
                story_title = story["title"] if story["title"] else "Untitled Story"

                # Use proper path prefix if using subdirectories
                if self.stories_subdir:
                    story_link = (
                        f"[[{self.stories_subdir}/{story_note_name}|{story_title}]]"
                    )
                else:
                    story_link = f"[[{story_note_name}|{story_title}]]"

                # Write the link with description if available
                if story["description"]:
                    f.write(f"- {story_link} - *{story['description']}*\n")
                else:
                    f.write(f"- {story_link}\n")

            f.write("\n")

        f.write("\n")

    def _collapse_single_line(self, text: str) -> str:
        """Normalize a single-line string's internal whitespace.

        Delegates to package-level utils.collapse_single_line for convenience.
        """
        return collapse_single_line(text)

    def _collapse_preserve_lines(self, text: str) -> str:
        """Collapse runs of whitespace within each line but preserve line breaks.

        Delegates to utils.text.collapse_preserve_lines.
        """
        return collapse_preserve_lines(text)

    def _format_source_entry(self, title: str, publ: str) -> str:
        """Return a formatted markdown line for a source entry.

        If title and publ are present, title is rendered as a link to publ.
        If only title present, render plain title. If only publ present, use the URL as link text.
        Title text is escaped to prevent markdown emphasis characters from triggering formatting.
        """
        title = self._collapse_single_line(title)
        publ = self._collapse_single_line(publ)
        escaped_title = self._escape_markdown(title)

        if title and publ:
            return f"[{escaped_title}]({publ})"
        if title:
            return escaped_title
        if publ:
            return f"[{publ}]({publ})"
        return "(Unknown source)"

    def _write_sources(self, f, individual: Individual):
        """
        Write the "Sources" section for an individual as a numbered list.

        Each source will include the formatted title/publication on the numbered line
        and, if present, the source's NOTE text will be written as an indented
        escaped note block beneath it (nested, non-italicized) to avoid accidental Markdown emphasis.
        """
        sources = getattr(individual, "get_sources", lambda: [])()
        if not sources:
            return

        f.write("## Sources\n\n")
        for i, src in enumerate(sources, 1):
            line = self._format_source_entry(src.get("title", ""), src.get("publ", ""))
            f.write(f"{i}. {line}\n")
            note_text = src.get("note", "")
            if note_text:
                # Repair broken HTML tags spanning lines and escape markdown
                note_text = self._repair_broken_html_tags(note_text)
                lines = [self._escape_markdown(ln) for ln in note_text.splitlines()]
                self._write_multiline_note_block(f, lines, nested=True)
        f.write("\n")

    def _generate_sources_index(self, parser):
        """Generate a global sources Index.md from the GEDCOM element dictionary.

        This method scans the parser's element dictionary for SOURCE (SOUR)
        records and writes a single streamed Index.md file inside the output
        'sources/' directory. To avoid using excessive memory when many source
        records exist, entries are written to disk as they are discovered rather
        than being accumulated in memory.

        The created Index.md contains a numbered list of sources; if a source
        has associated NOTE text, the NOTE is written as a nested, escaped
        indented block beneath the numbered entry. The function repairs certain
        HTML tags that may have been split across GEDCOM CONT lines and escapes
        markdown emphasis characters in NOTE lines to avoid accidental
        formatting.

        The method sets the generator's _sources_index_generated flag on success
        or when encountering unrecoverable errors so that subsequent calls avoid
        re-scanning the element dictionary.
        """
        try:
            elem_dict = parser.get_element_dictionary()
        except (AttributeError, ValueError) as e:
            logger.exception(
                "Failed to retrieve GEDCOM element dictionary for sources index: %s", e
            )
            # Prevent repeated attempts on failure
            self._sources_index_generated = True
            return
        except (RuntimeError, TypeError):
            # Unexpected failure type: log at debug and mark generated to avoid retry storms
            logger.exception(
                "Unexpected error retrieving GEDCOM element dictionary for sources index"
            )
            self._sources_index_generated = True
            return

        # Stream sources to the Index.md file as we discover them to avoid
        # accumulating a potentially very large in-memory list.
        if self.use_subdirectories and self.output_dir and self.output_dir.parent:
            sources_dir = self.output_dir.parent / "sources"
        else:
            sources_dir = self.output_dir / "sources"

        i = 0
        index_file = sources_dir / "Index.md"

        # Delay creating the file and directory until the first source is found so
        # that no empty Index.md is left behind when there are no SOUR records.
        f = None
        try:
            for elem in elem_dict.values():
                try:
                    if elem.get_tag() != "SOUR":
                        continue
                except (AttributeError, ValueError) as e:
                    logger.debug(
                        "Skipping non-source element or malformed element during sources scan: %s",
                        e,
                    )
                    continue

                title = ""
                publ = ""
                note_text = ""

                for sc in elem.get_child_elements():
                    tag = sc.get_tag()
                    if tag == "TITL":
                        title = sc.get_value() or ""
                    elif tag == "PUBL":
                        publ = sc.get_value() or ""
                    elif tag == "NOTE":
                        note_val = sc.get_value() or ""
                        # Use shared resolver to handle pointer vs inline NOTE with CONT/CONC semantics
                        note_text = resolve_gedcom_text(parser, note_val, sc)

                title = self._collapse_single_line(title)
                publ = self._collapse_single_line(publ)
                note_text = self._collapse_preserve_lines(note_text)

                if title or publ or note_text:
                    if f is None:
                        # First source found: create directory and open file
                        sources_dir.mkdir(parents=True, exist_ok=True)
                        f = open(index_file, "w", encoding="utf-8")
                        f.write("# Sources Index\n\n")
                    i += 1
                    entry = self._format_source_entry(title, publ)
                    f.write(f"{i}. {entry}\n")
                    if note_text:
                        # Repair broken HTML tags and escape markdown
                        note_text = self._repair_broken_html_tags(note_text)
                        lines = [
                            self._escape_markdown(ln) for ln in note_text.splitlines()
                        ]
                        self._write_multiline_note_block(f, lines, nested=True)

            if f is not None:
                f.write("\n")
        finally:
            if f is not None:
                f.close()

        # Mark that the global sources index has been generated so we don't do this again
        self._sources_index_generated = True

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown emphasis characters in text to prevent accidental formatting.

        Delegates to utils.text.escape_markdown.
        """
        return escape_markdown(text)

    def _repair_broken_html_tags(self, text: str) -> str:
        """Repair a small set of HTML tags that may have been split across GEDCOM lines.

        Delegates to utils.text.repair_broken_html_tags for conservative repairs.
        """
        return repair_broken_html_tags(text)

    def _write_multiline_note_block(
        self, f, lines: List[str], nested: bool = True
    ) -> None:
        """Write a multi-line NOTE block into the open file.

        Delegates to the shared utils.text.write_multiline_note_block implementation
        to keep rendering behavior centralized and consistent across callers.
        """
        return write_multiline_note_block(f, lines, nested)

    def _write_metadata(self, f, key: str, value: str):
        """
        Write a visible Obsidian metadata line for the given key and value.

        Parameters:
            f: A text file-like object to write the metadata line to.
            key (str): Metadata key to appear before the separator.
            value (str): Metadata value to appear after the separator.

        Description:
            Emits metadata in the Obsidian visible format: [Key:: Value]
        """
        f.write(f"[{key}:: {value}]\n")

    def _write_metadata_hidden(self, f, key: str, value: str):
        """
        Write a hidden Obsidian metadata line to the provided file.

        Writes a single line in the form "(Key:: Value)" followed by a newline to the file-like object `f`.

        Parameters:
            f: A writable file-like object to which the metadata line will be written.
            key (str): Metadata key.
            value (str): Metadata value.
        """
        f.write(f"({key}:: {value})\n")

    def _get_actual_filename(self, individual: Individual) -> str:
        """
        Get the actual filename for an individual, using the mapped name if available.

        Parameters:
            individual (Individual): The individual to get the filename for

        Returns:
            str: The actual filename without extension
        """
        individual_id = individual.get_id()
        if individual_id in self.filename_map:
            return self.filename_map[individual_id]
        return individual.get_file_name()

    def _wiki_link(self, text: str) -> str:
        """
        Format text as an Obsidian-style WikiLink.

        Returns:
            wiki_link (str): The input text wrapped in double square brackets (e.g. `[[Name]]`).
        """
        return f"[[{text}]]"

    def _download_external_media(self, individuals: List[Individual], media_subdir_path: Path):
        """Download external media URLs concurrently, then rewrite media notes."""
        if not self.download_media:
            return

        # Collect unique URLs
        urls = {}
        for individual in individuals:
            for img in individual.get_all_media():
                file_val = img.get("file", "")
                if isinstance(file_val, str) and (file_val.startswith("http://") or file_val.startswith("https://")):
                    urls[file_val] = True

        if not urls:
            return

        def _rate_limited_download(url):
            host = urllib.parse.urlparse(url).hostname or url

            # Wait until host is allowed (if another worker set Retry-After)
            with self._host_lock:
                next_allowed = self._host_next_allowed.get(host, 0)
            now = time.time()
            if next_allowed > now:
                time.sleep(next_allowed - now)

            # Acquire per-host semaphore if enabled
            sem = None
            acquired = False
            if self.enable_concurrency:
                with self._host_lock:
                    sem = self._host_semaphores.get(host)
                    if sem is None:
                        sem = threading.Semaphore(self.per_host_concurrency)
                        self._host_semaphores[host] = sem
                sem.acquire()
                acquired = True

            try:
                # Inter-request delay (fixed or randomized) takes precedence over rate
                if self.download_delay is not None:
                    if self.download_randomize_std and self.download_randomize_std > 0.0:
                        delay = max(0.0, random.gauss(self.download_delay, self.download_randomize_std))
                    else:
                        delay = self.download_delay
                    time.sleep(delay)
                elif self.download_rate:
                    # Global rate limiting
                    with self._rate_lock:
                        now = time.time()
                        min_interval = 1.0 / self.download_rate
                        delta = now - self._last_request_time
                        if delta < min_interval:
                            time.sleep(min_interval - delta)
                        self._last_request_time = time.time()

                result = self._download_url(url, media_subdir_path)
            except Exception as e:
                logger.warning(f"Prefetch failed for {url}: {e}")
                result = None
            finally:
                if acquired and sem:
                    try:
                        sem.release()
                    except Exception:
                        pass

            with self._cache_lock:
                self._downloaded_cache[url] = result
            return url, result

        # Submit downloads in ThreadPool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.download_concurrency) as exc:
            futures = [exc.submit(_rate_limited_download, u) for u in urls.keys()]
            completed = 0
            total = len(futures)
            for fut in concurrent.futures.as_completed(futures):
                try:
                    url, res = fut.result()
                    logger.debug(f"Prefetch completed: {url} -> {res}")
                except Exception:
                    logger.exception("Error in prefetch worker")
                completed += 1
                print(f"Media downloads: {completed}/{total}", flush=True)

        # Rewrite any generated media notes so downloaded files are linked locally.
        for _media_file, data in self.generated_media_data.items():
            self._write_media_file(
                data["path"],
                data["individual_name"],
                data["entries"],
            )

        # Build mapping of photos to people by scanning all individuals' media entries
        photo_person_pairs = []  # list of (photo_filename, gedcom_pointer, person_name)
        photo_to_people = {}

        for individual in individuals:
            person_name = self._get_actual_filename(individual)
            pointer = individual.get_pointer()

            for entry in individual.get_all_media():
                file_val = entry.get("file", "")
                title = entry.get("title") or "Image"

                # Determine local filename for URLs or local file references
                local_filename = None
                if isinstance(file_val, str) and (file_val.startswith("http://") or file_val.startswith("https://")):
                    with self._cache_lock:
                        local_filename = self._downloaded_cache.get(file_val)
                    if local_filename is None:
                        # Not downloaded or failed; skip mapping
                        continue
                else:
                    # Local file reference: use basename
                    local_filename = os.path.basename(file_val) if file_val else None

                if not local_filename:
                    continue

                # Record mapping (include original URL)
                photo_person_pairs.append((local_filename, pointer, person_name, title, file_val))
                photo_to_people.setdefault(local_filename, []).append((pointer, person_name, title, file_val))

        # Update each person's markdown to embed local downloaded images (prefer local files over URLs)
        person_dir = self.output_dir / self.people_subdir if getattr(self, 'people_subdir', '') else self.output_dir
        for individual in individuals:
            person_name = self._get_actual_filename(individual)
            person_path = person_dir / f"{person_name}.md"
            if not person_path.exists():
                continue

            try:
                content = person_path.read_text(encoding='utf-8')

                # Remove any existing External media sections entirely
                content = re.sub(r"## External media[\s\S]*?(?=\n## |\Z)", "", content)

                # Build Images block from individual's media entries using local filenames when available
                embed_lines = []
                for entry in individual.get_all_media():
                    file_val = entry.get("file", "")
                    title = entry.get("title") or person_name

                    if isinstance(file_val, str) and (file_val.startswith("http://") or file_val.startswith("https://")):
                        with self._cache_lock:
                            lf = self._downloaded_cache.get(file_val)
                        if lf:
                            if self.use_subdirectories and self.media_subdir:
                                img_path = f"../{self.media_subdir}/{lf}"
                            elif self.media_subdir:
                                img_path = f"{self.media_subdir}/{lf}"
                            else:
                                img_path = lf
                        else:
                            img_path = file_val
                    else:
                        # Local reference; preserve basename and prefix media_subdir
                        basename = os.path.basename(file_val) if file_val else ''
                        if self.use_subdirectories and self.media_subdir:
                            img_path = f"../{self.media_subdir}/{basename}"
                        elif self.media_subdir:
                            img_path = f"{self.media_subdir}/{basename}"
                        else:
                            img_path = basename

                    if img_path:
                        embed_lines.append(f"![{title}]({img_path})\n\n")

                if embed_lines:
                    images_block = "## Images\n\n" + "".join(embed_lines) + "\n"

                    # Replace existing Images section if present
                    m = re.search(r"## Images[\s\S]*?(?=\n## |\Z)", content)
                    if m:
                        content = content[: m.start()] + images_block + content[m.end():]
                    else:
                        # Insert before Notes section or at end
                        notes_pos = content.find("## Notes")
                        if notes_pos != -1:
                            content = content[:notes_pos] + images_block + "\n" + content[notes_pos:]
                        else:
                            content = content + "\n" + images_block

                    person_path.write_text(content, encoding='utf-8')

            except Exception:
                logger.exception(f"Failed to update images in person file for {person_name}")

        # Write a single cross-reference markdown mapping photos to GEDCOM pointers and names
        if photo_person_pairs:
            map_path = media_subdir_path / "photo_person_map.md"
            try:
                with open(map_path, "w", encoding="utf-8") as mp:
                    mp.write("# Photo to Person mapping\n\n")
                    mp.write("Photo | GEDCOM ID | Name | Title | Original URL\n")
                    mp.write("--- | --- | --- | --- | ---\n")
                    for photo, ptr, name, title, url in photo_person_pairs:
                        # Prefer a meaningful title; if absent or generic 'Image', fall back to the person's name
                        write_title = name if (not title or str(title).strip().lower() == 'image') else title
                        mp.write(f"{photo} | {ptr} | {name} | {write_title} | {url or ''}\n")
            except Exception:
                logger.exception("Failed to write photo_person_map.md")

    def generate_all(self, individuals: List[Individual]) -> List[Path]:

        """
        Generate notes for all individuals.

        Args:
            individuals: List of Individual objects

        Returns:
            List of paths to created files
        """
        logger.info(f"Generating notes for {len(individuals)} individuals")

        # Prepare media directory path for media notes and downloads
        if self.media_subdir:
            media_dir = self.output_dir / self.media_subdir
        else:
            media_dir = self.output_dir
        media_dir.mkdir(parents=True, exist_ok=True)

        paths = []
        for individual in individuals:
            try:
                path = self.generate_note(individual)
                paths.append(path)
            except (OSError, ValueError, AttributeError):
                logger.exception(
                    f"Failed to generate note for {individual.get_full_name()}"
                )

        logger.info(f"Successfully generated {len(paths)} notes")

        # Generate global sources index once (expensive) using the first available parser
        if not self._sources_index_generated:
            parser = None
            for ind in individuals:
                parser = getattr(ind, "gedcom", None)
                if parser:
                    break

            if parser:
                try:
                    self._generate_sources_index(parser)
                except (OSError, AttributeError, ValueError):
                    logger.exception("Failed to generate sources index")
        return paths
