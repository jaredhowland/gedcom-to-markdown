"""
Markdown note generator for Obsidian.

This module generates Obsidian-compatible markdown notes for individuals
in the family tree.
"""

from pathlib import Path
from typing import List, Optional, Any
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
        media_subdir: str = "",
        stories_subdir: str = "",
        stories_dir: Optional[Path] = None,
        use_subdirectories: bool = False,
        filename_registry: FilenameRegistry | None = None,
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
        self.media_subdir = media_subdir
        self.stories_subdir = stories_subdir
        self.stories_dir = stories_dir if stories_dir else output_dir
        self.use_subdirectories = use_subdirectories
        self.generated_stories = {}  # Track generated story files
        # filename_map remains for compatibility; it will reflect the registry mapping
        self.filename_map = {}
        # Use provided registry or create a new one for deterministic naming
        self.filename_registry = filename_registry or FilenameRegistry()
        self._sources_index_generated = (
            False  # Ensure global sources index is created only once
        )

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
        file_path = self.output_dir / filename

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
        Write the Parents section for an individual note.

        If the individual has one or more parents, writes a "## Parents" heading followed by a bullet point for each parent containing a wiki link to the parent's note. If the individual has no parents, the function writes nothing.

        Parameters:
            f: A writable file-like object opened for the individual's markdown note.
            individual (Individual): The individual whose parents should be written.
        """
        parents = getattr(individual, "get_parents", lambda: [])()

        if not parents:
            return

        f.write("## Parents\n")

        for parent in parents:
            f.write(f"* Parent: {self._wiki_link(self._get_actual_filename(parent))}\n")

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
        Write an "Images" section to the open file for all images returned by the individual.

        If the individual has no images, nothing is written. Each image is written as a Markdown image reference (![title](path)). If an image has no title, the literal "Image" is used. When the generator was configured with a media subdirectory, that subdirectory is prefixed to the image filename.

        Parameters:
            f: A writable file-like object positioned where the section should be emitted.
            individual (Individual): The individual whose images are written. Expects items from individual.get_images() to be dicts with keys 'file' (filename) and optional 'title'.
        """
        images = getattr(individual, "get_images", lambda: [])()

        if not images:
            return

        f.write("## Images\n")

        for image in images:
            title = image.get("title", "") if isinstance(image, dict) else ""
            title = title if title else "Image"
            filename = image.get("file", "") if isinstance(image, dict) else ""
            if not filename:
                continue
            # Add media subdirectory prefix if specified
            if self.media_subdir:
                image_path = f"{self.media_subdir}/{filename}"
            else:
                image_path = filename
            f.write(f"![{title}]({image_path})\n\n")

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
        return filename.replace(".md", "")

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

    def generate_all(self, individuals: List[Individual]) -> List[Path]:
        """
        Generate notes for all individuals.

        Args:
            individuals: List of Individual objects

        Returns:
            List of paths to created files
        """
        logger.info(f"Generating notes for {len(individuals)} individuals")

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
