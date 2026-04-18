"""
Individual person data model.

This module provides a rich data model for individuals in a family tree,
extracting all relevant information from GEDCOM data.
"""

from typing import List, Dict, Tuple, Optional
import logging
import re

from gedcom.element.individual import IndividualElement
import gedcom.tags


logger = logging.getLogger(__name__)

EVENT_TAGS = {"BIRT", "DEAT", "MARR", "OCCU", "EDUC", "RESI", "BURI"}

def collapse_single_line(text: str) -> str:
    """Normalize whitespace on a single logical line.

    This helper collapses runs of whitespace (spaces, tabs) into single spaces
    and trims leading/trailing whitespace. It is intended for short metadata
    fields such as titles, publication strings, or other single-line values
    where internal spacing should be normalized but line breaks must be
    preserved elsewhere.

    Examples:
        >>> collapse_single_line("  Overland    Travels  Pioneer   Detail  ")
        'Overland Travels Pioneer Detail'

    Returns an empty string when passed a false-y value.
    """
    return " ".join(text.split()).strip() if text else ""


def resolve_gedcom_text(parser, value: str, element=None) -> str:
    """Resolve a GEDCOM text value including CONT/CONC continuations.

    GEDCOM continuation rules:
    - CONC: concatenate to previous line (no newline inserted)
    - CONT: start a new line (insert a newline in the output)

    This helper handles both pointer-style NOTE references (e.g. "@N1@") and
    inline NOTE bodies (where the parent element contains CONT/CONC children).

    Parameters
    ----------
    parser:
        The GEDCOM parser instance used to resolve pointer targets via
        parser.get_element_dictionary().
    value (str):
        The immediate value of the tag. May be a pointer ("@N1@") or plain
        text. When it's a pointer, the referenced element is resolved and its
        child CONT/CONC lines are applied.
    element:
        Optional element whose child CONT/CONC children should be read when
        resolving inline NOTE content. Provide this when `value` is an inline
        value and the continuations are stored on the element itself.

    Returns
    -------
    str
        Resolved text with CONC concatenated directly and CONT lines separated
        by a single newline. Empty CONT/CONC values are skipped.

    Examples
    --------
    Given a referenced NOTE element with:
        0 @N1@ NOTE
        1 CONT First line
        1 CONC -continued
        1 CONT Second para
    Calling resolve_gedcom_text(parser, "@N1@") returns:
        "First line-continued\nSecond para"
    """
    # Pointer/reference to another element (e.g., NOTE record)
    if value and value.startswith("@") and value.endswith("@"):
        target = parser.get_element_dictionary().get(value)
        if not target:
            return ""
        text = target.get_value() or ""
        # Respect CONT vs CONC semantics: CONT => newline, CONC => concatenate.
        # An empty CONT line represents a blank line in GEDCOM and must still
        # contribute a newline so paragraph breaks are preserved.
        for sub in target.get_child_elements():
            tag = sub.get_tag()
            val = (sub.get_value() or "")
            if tag == "CONC":
                if val:
                    text += val
            elif tag == "CONT":
                text += "\n" + val
        return text

    # Inline text with possible CONT/CONC children.
    # Same rule: empty CONC is a no-op, but empty CONT preserves a blank line.
    text = value or ""
    if element is not None:
        for sub in element.get_child_elements():
            tag = sub.get_tag()
            val = (sub.get_value() or "")
            if tag == "CONC":
                if val:
                    text += val
            elif tag == "CONT":
                text += "\n" + val
    return text


class Individual:
    """
    Represents an individual person in the family tree.

    This class wraps the GEDCOM IndividualElement and provides convenient
    access to all person data including names, dates, relationships, events,
    images, and notes.
    """

    def __init__(self, element: IndividualElement, parser):
        """
        Create an Individual wrapper around a GEDCOM individual element and parser.

        Stores the provided IndividualElement and parser used to resolve cross-references.

        Parameters:
            element (IndividualElement): The GEDCOM individual element to wrap.
            parser: The parser instance (e.g., gedcom.parser.Parser) used for resolving references.
        """
        self.element = element
        self.gedcom = parser

    def get_id(self) -> str:
        """
        Provide the GEDCOM identifier for this individual without surrounding '@' characters.

        Returns:
            str: The GEDCOM identifier with all '@' characters removed.
        """
        return self.element.get_pointer().replace('@', '')

    def get_pointer(self) -> str:
        """
        Get the full GEDCOM pointer/ID for this individual (with @ symbols).

        Returns:
            str: The GEDCOM pointer (e.g., '@I123@')
        """
        return self.element.get_pointer()

    def get_fs_id(self) -> str:
        """
        Return the FamilySearch Tree ID (`_FSFTID`) if present.

        Returns:
            str: FamilySearch Tree ID value, or an empty string when not available.
        """
        for child in self.element.get_child_elements():
            if child.get_tag() == "_FSFTID":
                return child.get_value() or ""
        return ""

    def get_names(self) -> Tuple[str, str]:
        """
        Return the individual's first and last name with surrounding whitespace removed.
        
        Returns:
            tuple(first_name, last_name): The person's given name and family name, both trimmed of leading and trailing whitespace.
        """
        first, last = self.element.get_name()
        return first.strip(), last.strip()

    def get_full_name(self) -> str:
        """
        Return the individual's full name formatted as "First Last".

        Returns:
            Full name string preserving original capitalization; empty string if no name parts exist.
        """
        first, last = self.get_names()
        return f"{first} {last}".strip()

    def get_file_name(self) -> str:
        """
        Build a filename-like string for the individual in the form "FamilyName FirstName BirthYear".

        Returns:
            filename (str): The generated filename string "FamilyName FirstName BirthYear" (or without year if unavailable); does not include a file extension; preserves original name capitalization.
        """
        first, last = self.get_names()
        birth_info = self.get_birth_info()
        birth_year = birth_info.get('year', '')

        # Build filename parts
        parts = []
        if last:
            parts.append(last)
        if first:
            parts.append(first)
        if birth_year:
            parts.append(birth_year)

        return " ".join(parts)

    def get_birth_info(self) -> Dict[str, str]:
        """
        Retrieve the person's birth date, place, year, and optional coordinates from the underlying GEDCOM element.

        Returns:
            dict: A dictionary with keys:
                - 'date' (str): Birth date string or '' if unavailable.
                - 'place' (str): Birth place string or '' if unavailable.
                - 'year' (str): Birth year as a string or '' if the year is unknown.
                - 'lat' (str): Latitude string if present, else ''
                - 'long' (str): Longitude string if present, else ''
        """
        birth_date, birth_place, lat, lon = self._get_event_info("BIRT")

        # Fallback to helper methods for year if available
        year = self.element.get_birth_year()
        birth_year = str(year) if year != -1 else ""

        return {
            "date": birth_date or "",
            "place": birth_place or "",
            "year": birth_year,
            "lat": lat,
            "long": lon,
        }

    def get_death_info(self) -> Dict[str, str]:
        """
        Provide the individual's death date, place, year, and optional coordinates.

        Returns:
            dict: Dictionary with keys:
                - date (str): Death date as a string, or '' if unknown.
                - place (str): Death place as a string, or '' if unknown.
                - year (str): Death year extracted from date, or '' if unavailable.
                - lat (str): Latitude if present, else ''
                - long (str): Longitude if present, else ''
        """
        death_date, death_place, lat, lon = self._get_event_info("DEAT")
        year = self._extract_year(death_date)

        return {
            "date": death_date or "",
            "place": death_place or "",
            "year": year,
            "lat": lat,
            "long": lon,
        }

    def get_gender(self) -> str:
        """
        Return the person's gender code.

        Returns:
            str: `'M'` for male, `'F'` for female, `'U'` if unspecified or unknown.
        """
        return self.element.get_gender() or 'U'

    def get_parents(self) -> List["Individual"]:
        """
        Retrieve the person's parents.

        Returns:
            A list of Individual objects representing the person's parents.
        """
        parent_elements = self.gedcom.get_parents(self.element)
        return [Individual(p, self.gedcom) for p in parent_elements]

    def get_children(self) -> List["Individual"]:
        """
        Retrieve the person's children as Individual objects.

        Returns:
            children (List[Individual]): A list of Individual instances corresponding to this person's children.
        """
        return [
            Individual(child, self.gedcom)
            for family in self.gedcom.get_families(self.element)
            for child in self.gedcom.get_family_members(
                family, gedcom.tags.GEDCOM_TAG_CHILD
            )
        ]

    def get_partners(self) -> List["Individual"]:
        """
        Retrieve this individual's spouses and partners.

        Each partner is resolved to an Individual wrapper; the subject is excluded from the result.

        Returns:
            List[Individual]: A list of Individual objects representing the person's partners (excluding the subject).
        """
        self_pointer = self.element.get_pointer()
        return [
            Individual(parent, self.gedcom)
            for family in self.gedcom.get_families(self.element)
            for parent in self.gedcom.get_family_members(family, "PARENTS")
            if parent.get_pointer() != self_pointer
        ]

    def get_families(self) -> List[Dict]:
        """
        Get all families this person is part of (as spouse).

        Returns:
            List of dictionaries with family information including:
            - partner: Individual object
            - marriage_date: str
            - marriage_place: str
            - children: List of Individual objects
        """
        families = []
        # Cache the subject pointer once; it doesn't change across families.
        self_pointer = self.element.get_pointer()
        for family in self.gedcom.get_families(self.element):
            # Get partner
            partners = [
                Individual(parent, self.gedcom)
                for parent in self.gedcom.get_family_members(family, "PARENTS")
                if parent.get_pointer() != self_pointer
            ]

            # Get marriage info
            marriage_date, marriage_place, marriage_lat, marriage_long = (
                self._get_event_info("MARR", family)
            )

            # Get children
            children = [
                Individual(child, self.gedcom)
                for child in self.gedcom.get_family_members(
                    family, gedcom.tags.GEDCOM_TAG_CHILD
                )
            ]

            families.append(
                {
                    "partner": partners[0] if partners else None,
                    "marriage_date": marriage_date,
                    "marriage_place": marriage_place,
                    "marriage_lat": marriage_lat,
                    "marriage_long": marriage_long,
                    "children": children,
                }
            )

        return families

    def get_families_as_child(self) -> List[Dict]:
        """
        Get all families where this person is a child (to find parents).

        Returns:
            List of dictionaries with family information including:
            - father: str (father's GEDCOM pointer, including surrounding '@' characters, e.g. '@I1@') or None
            - mother: str (mother's GEDCOM pointer, including surrounding '@' characters, e.g. '@I2@') or None
        """
        families = []
        self_pointer = self.element.get_pointer()

        for family in self.gedcom.get_root_child_elements():
            if family.get_tag() != gedcom.tags.GEDCOM_TAG_FAMILY:
                continue

            children = self.gedcom.get_family_members(family, gedcom.tags.GEDCOM_TAG_CHILD)
            if not any(child.get_pointer() == self_pointer for child in children):
                continue

            parents = self.gedcom.get_family_members(family, "PARENTS")
            father_id, mother_id = self._resolve_parent_ids(parents)
            families.append({"father": father_id, "mother": mother_id})

        return families

    def get_events(self) -> List[Dict[str, str]]:
        """
        Collects the individual's life events found on the GEDCOM element.

        Returns:
            List[dict]: Each dictionary represents an event with keys:
                - 'type' (str): GEDCOM event tag (e.g., 'BIRT', 'DEAT', 'MARR', 'OCCU', 'EDUC', 'RESI', 'BURI').
                - 'date' (str): Event date value if present, otherwise an empty string.
                - 'place' (str): Event place value if present, otherwise an empty string.
                - 'details' (str): The raw value of the event node (empty string if absent).
        """
        events = []

        for child in self.element.get_child_elements():
            tag = child.get_tag()

            # Common event tags
            if tag in EVENT_TAGS:
                event = {
                    "type": tag,
                    "date": "",
                    "place": "",
                    "details": child.get_value() or "",
                    "lat": "",
                    "long": "",
                }

                # Extract date, place, and optional coordinates from any event node.
                event["date"], event["place"], event["lat"], event["long"] = (
                    self._extract_date_place_and_coords(child)
                )

                events.append(event)

        return events

    def _extract_year(self, value: str) -> str:
        """Extract the first four-digit year from a string, if present."""
        if not value:
            return ""
        year_match = re.search(r"\b(\d{4})\b", value)
        return year_match.group(1) if year_match else ""

    def _resolve_parent_ids(self, parents) -> Tuple[Optional[str], Optional[str]]:
        """Resolve father/mother pointers from a list of parent elements."""
        father_id = None
        mother_id = None

        for parent in parents:
            pointer = parent.get_pointer()
            gender = self._get_element_gender(parent)

            if gender == "M":
                father_id = pointer
            elif gender == "F":
                mother_id = pointer
            elif not father_id:
                father_id = pointer
            elif not mother_id:
                mother_id = pointer

        return father_id, mother_id

    def _get_element_gender(self, element) -> str:
        """Get gender value from a GEDCOM element's SEX child tag."""
        for child in element.get_child_elements():
            if child.get_tag() == "SEX":
                return child.get_value() or ""
        return ""

    def _get_event_info(
        self, event_tag: str, parent_node=None
    ) -> Tuple[str, str, str, str]:
        """
        Find the first child event by tag and extract (date, place, lat, long).

        Parameters:
            event_tag (str): GEDCOM event tag to search for (for example "BIRT").
            parent_node: Optional node whose children are searched. Defaults to
                the wrapped individual element.
        """
        node = parent_node if parent_node is not None else self.element
        for child in node.get_child_elements():
            if child.get_tag() == event_tag:
                return self._extract_date_place_and_coords(child)
        return "", "", "", ""

    def _extract_date_place_and_coords(self, event_node) -> Tuple[str, str, str, str]:
        """
        Extract DATE, PLAC, and PLAC coordinates from an event-like GEDCOM node.

        Returns:
            Tuple[str, str, str, str]: (date, place, latitude, longitude), with
            missing values returned as empty strings.
        """
        date_value = ""
        place_value = ""
        lati = ""
        longi = ""

        for child in event_node.get_child_elements():
            if child.get_tag() == "DATE":
                date_value = child.get_value() or ""
            elif child.get_tag() == "PLAC":
                place_value = child.get_value() or ""
                lati, longi = self._extract_lat_long_from_plac(child)

        return date_value, place_value, lati, longi

    def _extract_lat_long_from_plac(self, plac_node) -> Tuple[str, str]:
        """
        Extract latitude and longitude values from a PLAC node if present.

        The function looks for a MAP child beneath the PLAC node and then for
        LATI and LONG tags. It also accepts LATI/LONG directly under PLAC.

        Returns a tuple (latitude, longitude) where missing values are empty strings.
        """
        return self._extract_lat_long_from_node(plac_node)

    def _extract_lat_long_from_node(self, node) -> Tuple[str, str]:
        """
        Recursively extract LATI/LONG values from any GEDCOM node subtree.

        This supports coordinates directly under PLAC, under MAP, or in deeper
        custom nesting used by some exports.
        """
        lati = ""
        longi = ""

        for child in node.get_child_elements():
            tag = child.get_tag()

            if tag == "LATI" and not lati:
                lati = child.get_value() or ""
                if lati and longi:
                    return lati, longi
                # Don't recurse into LATI leaf nodes
                continue
            elif tag == "LONG" and not longi:
                longi = child.get_value() or ""
                if lati and longi:
                    return lati, longi
                # Don't recurse into LONG leaf nodes
                continue

            # Recurse into other child nodes to find nested LATI/LONG
            nested_lati, nested_longi = self._extract_lat_long_from_node(child)
            if nested_lati and not lati:
                lati = nested_lati
            if nested_longi and not longi:
                longi = nested_longi

            if lati and longi:
                return lati, longi

        return lati, longi

    def get_images(self) -> List[Dict[str, str]]:
        """
        Return image/media entries referenced by this individual's OBJE nodes.
        
        Resolves OBJE references to their records and extracts FILE, TITL, and FORM values; entries without a FILE value are omitted.

        Returns:
            List[Dict[str, str]]: A list of dictionaries each containing the keys 'file', 'title', and 'format'. The 'file' value is non-empty for all returned entries.
        """
        images = []

        for child in self.element.get_child_elements():
            if child.get_tag() == "OBJE":
                image_info = self._get_obje_info(child.get_value())
                if image_info:
                    images.append(image_info)

        return images

    def _collapse_preserve_lines(self, text: str) -> str:
        """Collapse whitespace within each line but preserve line breaks."""
        if not text:
            return ""
        return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()

    def _resolve_gedcom_text(self, value: str, element=None) -> str:
        """Instance-level wrapper for the module resolve_gedcom_text helper.

        This method forwards to the module-level resolve_gedcom_text function
        passing the parser instance bound to this Individual. It exists to keep
        call sites on the Individual instance simple while centralizing the
        continuation resolution logic in one place.

        Parameters
        ----------
        value (str): The immediate tag value (may be a pointer like "@N1@"
                     or inline text).
        element: Optional element to read CONT/CONC children from when resolving
                 inline note content.

        Returns
        -------
        str: Resolved note/text with CONT/CONC applied.
        """
        return resolve_gedcom_text(self.gedcom, value, element)

    def get_notes(self) -> List[str]:
        """
        Return the person's notes with inline continuations and referenced NOTE records resolved.

        This resolves NOTE cross-references (values like `@X@`), appends `CONT`/`CONC` continuations, trims whitespace, and omits empty or unresolved references.

        Returns:
            List[str]: Note texts with continuations and referenced NOTE content merged; empty or unresolved notes are omitted.
        """
        notes = []
        for child in self.element.get_child_elements():
            if child.get_tag() != "NOTE":
                continue
            raw = child.get_value() or ""
            text = self._resolve_gedcom_text(raw, child)
            if text and not text.startswith("@"):
                notes.append(self._collapse_preserve_lines(text))
        return notes

    def get_sources(self) -> List[Dict[str, str]]:
        """Extract source references associated with this individual.

        Each source entry returned is a dictionary with keys:
            - "title": The source title (single-line whitespace collapsed)
            - "publ": The publication or URL (single-line whitespace collapsed)
            - "note": The NOTE text for the source with original line breaks preserved
                      (CONT produces a newline, CONC concatenates). Empty continuation
                      lines are skipped.

        The method handles two forms of source associations:
        1. Pointer-style references (1 SOUR @S1@) where @S1@ points to a separate
           SOURCE record elsewhere in the GEDCOM file. In this case the referenced
           SOURCE element's TITL/PUBL/NOTE children are resolved.
        2. Inline SOURCE blocks nested under the individual (1 SOUR ... with
           sub-tags at level 2). These are read directly from the child's children.

        Notes are resolved via the shared resolve_gedcom_text helper so pointer
        references and inline NOTE children are handled consistently.
        """
        sources = []
        for child in self.element.get_child_elements():
            if child.get_tag() != "SOUR":
                continue

            title = ""
            publ = ""
            note_text = ""

            # child may be a pointer to a SOURCE record or an inline SOURCE element
            src_ref = child.get_value() or ""
            # Treat as a pointer only if it both starts and ends with '@' (e.g., @S1@)
            if src_ref and src_ref.startswith("@") and src_ref.endswith("@"):
                elem_to_scan = self.gedcom.get_element_dictionary().get(src_ref) or child
            else:
                elem_to_scan = child

            for sc in elem_to_scan.get_child_elements():
                tag = sc.get_tag()
                if tag == "TITL":
                    title = sc.get_value() or ""
                elif tag == "PUBL":
                    publ = sc.get_value() or ""
                elif tag == "NOTE":
                    raw_note = sc.get_value() or ""
                    note_text = self._resolve_gedcom_text(raw_note, sc)

            # Normalize whitespace for title/publ but preserve line breaks in notes
            title = collapse_single_line(title)
            publ = collapse_single_line(publ)

            note_text = self._collapse_preserve_lines(note_text)

            if title or publ or note_text:
                sources.append({"title": title, "publ": publ, "note": note_text})

        return sources

    def get_stories(self) -> List[Dict]:
        """
        Extract story and narrative records referenced by custom `_STO` tags for this individual.

        Scans `_STO` child entries, resolves referenced story elements, and assembles structured story data.
        Each story dictionary contains:
        - `title` (str): story title (or empty string)
        - `description` (str): story-level description (or empty string)
        - `sections` (List[Dict]): ordered list of sections; each section dictionary contains:
          - `subtitle` (str): section title (or empty string)
          - `text` (str): section text with `CONT`/`CONC` continuations concatenated (or empty string)
          - `images` (List[Dict]): list of image dictionaries resolved from `OBJE` references; each image dictionary contains:
            - `file` (str): file path or name (required for inclusion)
            - `title` (str): image title (or empty string)
            - `format` (str): image format (or empty string)

        Returns:
            List[Dict]: list of story dictionaries; empty list if no stories are found.
        """
        stories = []

        for child in self.element.get_child_elements():
            if child.get_tag() == "_STO":
                story_ref = child.get_value()

                if story_ref and story_ref.startswith("@"):
                    # Resolve the story reference
                    story_element = self.gedcom.get_element_dictionary().get(story_ref)
                    if story_element:
                        story = {"title": "", "description": "", "sections": []}

                        # Get main title and metadata
                        for section in story_element.get_child_elements():
                            tag = section.get_tag()

                            if tag == "TITL":
                                story["title"] = section.get_value() or ""
                            elif tag == "DESC":
                                story["description"] = section.get_value() or ""
                            elif tag == "_STS":
                                # Story section with inline content
                                # Format: "1 @12375128@ _STS"
                                # Children at level 2 contain TITL, TEXT, OBJE
                                section_data = {
                                    "subtitle": "",
                                    "text": "",
                                    "images": [],
                                }

                                # Extract content directly from child elements
                                for sts_child in section.get_child_elements():
                                    if sts_child.get_tag() == "TITL":
                                        section_data["subtitle"] = (
                                            sts_child.get_value() or ""
                                        )
                                    elif sts_child.get_tag() == "TEXT":
                                        text = sts_child.get_value() or ""
                                        # Get CONT lines
                                        for cont in sts_child.get_child_elements():
                                            if cont.get_tag() in ["CONT", "CONC"]:
                                                text += "\n" + (cont.get_value() or "")
                                        section_data["text"] = text
                                    elif sts_child.get_tag() == "OBJE":
                                        image_info = self._get_obje_info(sts_child.get_value())
                                        if image_info:
                                            section_data["images"].append(image_info)

                                if section_data["subtitle"] or section_data["text"]:
                                    story["sections"].append(section_data)

                        if story["title"] or story["sections"]:
                            stories.append(story)

        return stories

    def _get_obje_info(self, reference: str) -> Optional[Dict[str, str]]:
        """Resolve an OBJE reference and return file metadata, or None if unavailable."""
        if not reference or not reference.startswith("@"):
            return None

        obje_element = self.gedcom.get_element_dictionary().get(reference)
        if not obje_element:
            return None

        image_info = {"file": "", "title": "", "format": ""}
        for obje_child in obje_element.get_child_elements():
            if obje_child.get_tag() == "FILE":
                image_info["file"] = obje_child.get_value() or ""
            elif obje_child.get_tag() == "TITL":
                image_info["title"] = obje_child.get_value() or ""
            elif obje_child.get_tag() == "FORM":
                image_info["format"] = obje_child.get_value() or ""

        return image_info if image_info["file"] else None

    def get_attributes(self) -> Dict[str, str]:
        """
        Collect physical attributes from the underlying GEDCOM individual element.

        Returns:
            Dict[str, str]: A dictionary with keys 'eyes', 'hair', and 'heig' (lowercase).
                Each value is the corresponding attribute string or an empty string if absent.
        """
        attributes = {}

        for child in self.element.get_child_elements():
            tag = child.get_tag()

            # Physical attributes
            if tag in ["EYES", "HAIR", "HEIG"]:
                attributes[tag.lower()] = child.get_value() or ""

        return attributes
