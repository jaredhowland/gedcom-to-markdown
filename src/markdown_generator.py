"""
Markdown note generator for Obsidian.

This module generates Obsidian-compatible markdown notes for individuals
in the family tree.
"""

from pathlib import Path
from typing import List, Optional
import logging
import re

from individual import Individual


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
    ):
        """
        Configure the MarkdownGenerator with paths and optional subdirectories for media and story files.

        Parameters:
            output_dir (Path): Directory where markdown notes will be written; must exist and be a directory.
            media_subdir (str): Optional subdirectory name (relative) to prefix media/image paths in notes.
            stories_subdir (str): Optional subdirectory name (relative) to use when constructing wiki links to generated story notes.
            stories_dir (Optional[Path]): Optional directory where story markdown files will be created; defaults to `output_dir` when not provided.
            use_subdirectories (bool): Whether the output structure uses subdirectories (people/, stories/, media/). When True, WikiLinks and image paths will include appropriate subdirectory prefixes.

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
        self.filename_map = {}  # Map from individual ID to actual filename used
        self._sources_index_generated = False  # Ensure global sources index is created only once

    def _get_unique_filename(self, base_name: str, individual_id: str) -> str:
        """
        Get a unique filename for an individual, handling duplicates by adding (1), (2), etc.

        Parameters:
            base_name (str): Base filename without extension (e.g., "Kucera Alexander Maximilian")
            individual_id (str): The individual's GEDCOM ID

        Returns:
            str: Unique filename without extension (e.g., "Kucera Alexander Maximilian (1)")
        """
        # Check if this base name has been used before
        counter = 1
        used_names = set(self.filename_map.values())
        unique_name = base_name

        while unique_name in used_names:
            unique_name = f"{base_name} ({counter})"
            counter += 1

        # Store the mapping
        self.filename_map[individual_id] = unique_name
        return unique_name

    def generate_note(self, individual: Individual) -> Path:
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

        with open(file_path, "w", encoding="utf-8") as f:
            # Write all sections
            self._write_frontmatter(f, individual)
            self._write_header(f, individual)
            self._write_events(f, individual)
            self._write_families(f, individual)
            self._write_parents(f, individual)
            self._write_children(f, individual)
            self._write_images(f, individual)
            self._write_notes(f, individual)
            # Write Sources section (if any)
            self._write_sources(f, individual)

        # Generate global sources index once if not already generated. This preserves the behavior
        # expected by callers that invoke generate_note() directly (unit tests), while avoiding
        # O(N^2) behavior when multiple notes are generated via generate_all().
        if not getattr(self, '_sources_index_generated', False):
            parser = getattr(individual, 'gedcom', None)
            if parser:
                try:
                    self._generate_sources_index(parser)
                except Exception:
                    logger.exception('Failed to generate sources index')

        return file_path

    def _write_frontmatter(self, f, individual: Individual):
        """
        Write YAML frontmatter containing individual attributes.

        Parameters:
            f (IO[str]): Open text file or writable stream to receive YAML frontmatter.
            individual (Individual): Person whose attributes are written to frontmatter.
        """
        f.write("---\n")

        birth = individual.get_birth_info()
        death = individual.get_death_info()

        f.write(f"ID: {individual.get_id()}\n")
        f.write(f"Name: {individual.get_full_name()}\n")

        # Lived years
        if birth['year'] or death['year']:
            lived = f"{birth['year']}-{death['year']}"
            f.write(f"Lived: {lived}\n")

        f.write(f"Sex: {individual.get_gender()}\n")

        # Birth details
        if birth["date"]:
            f.write(f"Born: {birth['date']}\n")
        if birth["place"]:
            f.write(f"Place of birth: {birth['place']}\n")

        # Death details
        if death["date"]:
            f.write(f"Passed away: {death['date']}\n")
        if death["place"]:
            f.write(f"Place of death: {death['place']}\n")

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
        events = individual.get_events()

        # Filter out birth and death (already in attributes)
        other_events = [e for e in events if e["type"] not in ["BIRT", "DEAT"]]

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
            event_type = event_names.get(event["type"], event["type"])
            f.write(f"### {event_type}\n")

            if event["date"]:
                f.write(f"- **Date**: {event['date']}\n")
            if event["place"]:
                f.write(f"- **Place**: {event['place']}\n")
            if event["details"]:
                f.write(f"- **Details**: {event['details']}\n")

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

            # Write children if they exist
            if family["children"]:
                f.write("\n**Children:**\n")
                for child in family["children"]:
                    f.write(f"* Child: {self._wiki_link(self._get_actual_filename(child))}\n")

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
        parents = individual.get_parents()

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
        if individual.get_families():
            return

        children = individual.get_children()

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
        images = individual.get_images()

        if not images:
            return

        f.write("## Images\n")

        for image in images:
            title = image["title"] if image["title"] else "Image"
            filename = image["file"]
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

        with open(file_path, "w", encoding="utf-8") as f:
            # Write story header
            f.write(f"# {story_title}\n\n")

            # Write description if available
            if story["description"]:
                f.write(f"*{story['description']}*\n\n")

            # Link back to the individual
            # If using subdirectories, stories are in stories/ and people are in people/
            if self.use_subdirectories:
                person_link = f"[[people/{individual_name}|{individual_name}]]"
            else:
                person_link = f"[[{individual_name}]]"

            f.write(f"**Related to:** {person_link}\n\n")
            f.write("---\n\n")

            # Write each section
            for section in story["sections"]:
                if section["subtitle"]:
                    f.write(f"## {section['subtitle']}\n\n")

                if section["text"]:
                    f.write(f"{section['text']}\n\n")

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
                        f.write(f"![{title}]({image_path})\n\n")

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
        notes = individual.get_notes()
        stories = individual.get_stories()

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
        """Collapse runs of whitespace into single spaces and strip the result."""
        return " ".join(text.split()).strip() if text else ""

    def _collapse_preserve_lines(self, text: str) -> str:
        """Collapse runs of whitespace within each line but preserve line breaks.

        Returns a string where each original line has internal whitespace collapsed
        but newline boundaries between CONT/CONC lines are preserved.
        """
        if not text:
            return ""
        return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()

    def _format_source_entry(self, title: str, publ: str) -> str:
        """Return a formatted markdown line for a source entry.

        If title and publ are present, title is rendered as a link to publ.
        If only title present, render plain title. If only publ present, use the URL as link text.
        """
        title = self._collapse_single_line(title)
        publ = self._collapse_single_line(publ)

        if title and publ:
            return f"[{title}]({publ})"
        if title:
            return title
        if publ:
            return f"[{publ}]({publ})"
        return "(Unknown source)"

    def _write_sources(self, f, individual: Individual):
        """
        Write the "Sources" section for an individual as a numbered list.

        Each source will include the formatted title/publication on the numbered line
        and, if present, the source's NOTE text will be written indented beneath it
        (formatted in italic to match the generated index).
        """
        sources = individual.get_sources()
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
        """
        Generate a summary Index.md in a sources/ subdirectory listing all SOURCE records found in the GEDCOM element dictionary.
        """
        try:
            elem_dict = parser.get_element_dictionary()
        except Exception:
            return

        sources = []
        for elem in elem_dict.values():
            try:
                if elem.get_tag() != "SOUR":
                    continue
            except Exception:
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
                    if note_val.startswith("@") and note_val.endswith("@"):
                        n_elem = elem_dict.get(note_val)
                        if n_elem:
                            note_text = n_elem.get_value() or ""
                            for sub in n_elem.get_child_elements():
                                tag_sub = sub.get_tag()
                                val_sub = (sub.get_value() or "")
                                if not val_sub:
                                    continue
                                if tag_sub == "CONC":
                                    note_text += val_sub
                                elif tag_sub == "CONT":
                                    note_text += "\n" + val_sub
                    else:
                        note_text = note_val
                        for sub in sc.get_child_elements():
                            tag_sub = sub.get_tag()
                            val_sub = (sub.get_value() or "")
                            if not val_sub:
                                continue
                            if tag_sub == "CONC":
                                note_text += val_sub
                            elif tag_sub == "CONT":
                                note_text += "\n" + val_sub

            title = self._collapse_single_line(title)
            publ = self._collapse_single_line(publ)
            note_text = self._collapse_preserve_lines(note_text)

            if title or publ or note_text:
                sources.append({"title": title, "publ": publ, "note": note_text})

        if not sources:
            return

        # Prefer a global 'sources' directory at the top-level output when using
        # the organized subdirectory layout (people/, stories/, media/). The
        # generator's output_dir is typically the people/ directory in that
        # case, so use its parent as the global output root.
        if self.use_subdirectories and self.output_dir and self.output_dir.parent:
            sources_dir = self.output_dir.parent / "sources"
        else:
            sources_dir = self.output_dir / "sources"

        sources_dir.mkdir(parents=True, exist_ok=True)
        index_file = sources_dir / "Index.md"

        with open(index_file, "w", encoding="utf-8") as f:
            f.write("# Sources Index\n\n")
            for i, src in enumerate(sources, 1):
                entry = self._format_source_entry(src.get("title", ""), src.get("publ", ""))
                f.write(f"{i}. {entry}\n")
                note_text = src.get("note", "")
                if note_text:
                    # Repair broken HTML tags and escape markdown
                    note_text = self._repair_broken_html_tags(note_text)
                    lines = [self._escape_markdown(ln) for ln in note_text.splitlines()]
                    self._write_multiline_note_block(f, lines, nested=True)
            f.write("\n")

        # Mark that the global sources index has been generated so we don't do this again
        self._sources_index_generated = True

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown emphasis characters in text to prevent accidental formatting.

        Escapes: backslash, asterisk, underscore, backtick, and tilde.
        Does not escape bracket characters so links still render.
        """
        if not text:
            return ""
        # Escape backslash first
        text = text.replace("\\", "\\\\")
        # Escape characters that trigger emphasis or code spans
        for ch in ('*', '_', '`', '~'):
            text = text.replace(ch, f"\\{ch}")
        return text

    def _repair_broken_html_tags(self, text: str) -> str:
        """Repair HTML tags that were broken across lines for a small whitelist of tags.

        Strategy:
        - Find all substrings that look like tags (<...>), possibly spanning lines.
        - For each tag, remove newlines inside the tag only if the tag name (after
          removing newlines) is in a safe whitelist. This joins broken tag names
          like "<b\nr>" into "<br>" while leaving other tags alone.
        """
        if not text or '<' not in text:
            return text

        WHITELIST = {"br", "b", "i", "strong", "em", "a", "span", "div", "p", "ul", "li"}

        def repl(m: re.Match) -> str:
            raw = m.group(0)
            content = raw[1:-1]  # inside <...>
            # Remove newline and carriage returns to inspect tag name
            content_no_nl = content.replace('\n', '').replace('\r', '')
            # Extract tag name (skip leading '/')
            name_m = re.match(r"\s*/?\s*([A-Za-z0-9]+)", content_no_nl)
            if name_m and name_m.group(1).lower() in WHITELIST:
                # Rebuild tag with newlines removed but preserve other spaces
                repaired = '<' + content_no_nl + '>'
                return repaired
            return raw

        return re.sub(r'<[^>]*>', repl, text, flags=re.DOTALL)

    def _write_multiline_note_block(self, f, lines: List[str], nested: bool = True) -> None:
        """Write a multi-line note block.

        - If nested is True, writes a nested list bullet (3 spaces + '-') for the first
          line and indented continuation lines for the rest. All lines except the
          last will end with two trailing spaces to force a hard line break; the
          final CONT line is written without the trailing spaces to avoid an extra
          blank line after the block.
        - If nested is False, writes plain lines; trailing two spaces are added to
          all but the last non-empty line.
        """
        if not lines:
            return

        total = len(lines)
        if nested:
            indent = "   "
            cont_indent = "     "
            # First line as a nested bullet; add two spaces if there are continuation lines
            if total > 1:
                f.write(f"{indent}- {lines[0]}  \n")
            else:
                f.write(f"{indent}- {lines[0]}\n")

            for idx, cont in enumerate(lines[1:], start=1):
                # For continuation lines, add two spaces except for the last line
                if idx < total - 1:
                    f.write(f"{cont_indent}{cont}  \n")
                else:
                    f.write(f"{cont_indent}{cont}\n")
        else:
            # Non-nested: add two spaces to all non-empty lines except the last non-empty
            non_empty = [ln for ln in lines if ln.strip()]
            last_non_empty = non_empty[-1] if non_empty else None
            for ln in lines:
                if not ln.strip():
                    f.write("\n")
                elif ln == last_non_empty:
                    f.write(f"{ln}\n")
                else:
                    f.write(f"{ln}  \n")

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
            except Exception:
                logger.exception(
                    f"Failed to generate note for {individual.get_full_name()}"
                )

        logger.info(f"Successfully generated {len(paths)} notes")

        # Generate global sources index once (expensive) using the first available parser
        if not self._sources_index_generated:
            parser = None
            for ind in individuals:
                parser = getattr(ind, 'gedcom', None)
                if parser:
                    break

            if parser:
                try:
                    self._generate_sources_index(parser)
                except Exception:
                    logger.exception('Failed to generate sources index')
        return paths