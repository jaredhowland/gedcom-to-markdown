"""
Individual person data model.

This module provides a rich data model for individuals in a family tree,
extracting all relevant information from GEDCOM data.
"""

from typing import List, Dict, Tuple
import logging
import re

from gedcom.element.individual import IndividualElement
import gedcom.tags


logger = logging.getLogger(__name__)


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
        Retrieve the person's birth date, place, and year from the underlying GEDCOM element.

        Returns:
            dict: A dictionary with keys:
                - 'date' (str): Birth date string or '' if unavailable.
                - 'place' (str): Birth place string or '' if unavailable.
                - 'year' (str): Birth year as a string or '' if the year is unknown.
        """
        date, place, _sources = self.element.get_birth_data()
        year = self.element.get_birth_year()

        return {
            "date": date or "",
            "place": place or "",
            "year": str(year) if year != -1 else "",
        }

    def get_death_info(self) -> Dict[str, str]:
        """
        Provide the individual's death date, place, and year.

        Returns:
            dict: Dictionary with keys:
                - date (str): Death date as a string, or '' if unknown.
                - place (str): Death place as a string, or '' if unknown.
                - year (str): Death year extracted from date, or '' if unavailable.
        """
        date, place, _sources = self.element.get_death_data()

        # Extract year from date string using regex
        # Handles formats like "1850", "ABT 1850", "1 JAN 1850", "JAN 1850"
        year = ""
        if date:
            year_match = re.search(r'\b(\d{4})\b', date)
            if year_match:
                year = year_match.group(1)

        return {"date": date or "", "place": place or "", "year": year}

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
        children = []
        for family in self.gedcom.get_families(self.element):
            child_elements = self.gedcom.get_family_members(
                family, gedcom.tags.GEDCOM_TAG_CHILD
            )
            for child in child_elements:
                children.append(Individual(child, self.gedcom))
        return children

    def get_partners(self) -> List["Individual"]:
        """
        Retrieve this individual's spouses and partners.

        Each partner is resolved to an Individual wrapper; the subject is excluded from the result.

        Returns:
            List[Individual]: A list of Individual objects representing the person's partners (excluding the subject).
        """
        partners = []
        for family in self.gedcom.get_families(self.element):
            parent_elements = self.gedcom.get_family_members(family, "PARENTS")
            for parent in parent_elements:
                # Don't include self
                if parent.get_pointer() != self.element.get_pointer():
                    partners.append(Individual(parent, self.gedcom))
        return partners

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
        for family in self.gedcom.get_families(self.element):
            # Get partner
            partners = []
            for parent in self.gedcom.get_family_members(family, "PARENTS"):
                if parent.get_pointer() != self.element.get_pointer():
                    partners.append(Individual(parent, self.gedcom))

            # Get marriage info
            marriage_date = ""
            marriage_place = ""
            for child in family.get_child_elements():
                if child.get_tag() == "MARR":
                    for subchild in child.get_child_elements():
                        if subchild.get_tag() == "DATE":
                            marriage_date = subchild.get_value()
                        elif subchild.get_tag() == "PLAC":
                            marriage_place = subchild.get_value()

            # Get children
            children = []
            for child in self.gedcom.get_family_members(
                family, gedcom.tags.GEDCOM_TAG_CHILD
            ):
                children.append(Individual(child, self.gedcom))

            families.append(
                {
                    "partner": partners[0] if partners else None,
                    "marriage_date": marriage_date,
                    "marriage_place": marriage_place,
                    "children": children,
                }
            )

        return families

    def get_families_as_child(self) -> List[Dict]:
        """
        Get all families where this person is a child (to find parents).

        Returns:
            List of dictionaries with family information including:
            - father: str (father's GEDCOM ID) or None
            - mother: str (mother's GEDCOM ID) or None
        """
        families = []

        # Use the python-gedcom method to get parents
        # Then find the family record that connects them
        parent_elements = self.gedcom.get_parents(self.element)

        # Get all family records
        for family in self.gedcom.get_root_child_elements():
            if family.get_tag() == gedcom.tags.GEDCOM_TAG_FAMILY:
                # Check if this person is a child in this family
                children = self.gedcom.get_family_members(family, gedcom.tags.GEDCOM_TAG_CHILD)
                child_pointers = [c.get_pointer() for c in children]

                if self.element.get_pointer() in child_pointers:
                    # This person is a child in this family, get the parents
                    parents = self.gedcom.get_family_members(family, "PARENTS")

                    father_id = None
                    mother_id = None

                    for parent in parents:
                        # Determine gender to assign father/mother
                        # Check gender tag
                        gender = None
                        for child_elem in parent.get_child_elements():
                            if child_elem.get_tag() == "SEX":
                                gender = child_elem.get_value()
                                break

                        if gender == "M":
                            father_id = parent.get_pointer()
                        elif gender == "F":
                            mother_id = parent.get_pointer()
                        else:
                            # If no gender specified, assign to father if empty, else mother
                            if not father_id:
                                father_id = parent.get_pointer()
                            elif not mother_id:
                                mother_id = parent.get_pointer()

                    families.append({
                        "father": father_id,
                        "mother": mother_id,
                    })

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
            if tag in ["BIRT", "DEAT", "MARR", "OCCU", "EDUC", "RESI", "BURI"]:
                event = {
                    "type": tag,
                    "date": "",
                    "place": "",
                    "details": child.get_value() or "",
                }

                # Extract date and place
                for subchild in child.get_child_elements():
                    if subchild.get_tag() == "DATE":
                        event["date"] = subchild.get_value()
                    elif subchild.get_tag() == "PLAC":
                        event["place"] = subchild.get_value()

                events.append(event)

        return events

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
                # OBJE can have a reference or inline data
                reference = child.get_value()
                if reference and reference.startswith("@"):
                    # Resolve the reference to get actual file info
                    obje_element = self.gedcom.get_element_dictionary().get(reference)
                    if obje_element:
                        image_info = {"file": "", "title": "", "format": ""}

                        for obje_child in obje_element.get_child_elements():
                            if obje_child.get_tag() == "FILE":
                                image_info["file"] = obje_child.get_value() or ""
                            elif obje_child.get_tag() == "TITL":
                                image_info["title"] = obje_child.get_value() or ""
                            elif obje_child.get_tag() == "FORM":
                                image_info["format"] = obje_child.get_value() or ""

                        if image_info["file"]:
                            images.append(image_info)

        return images

    def _collapse_preserve_lines(self, text: str) -> str:
        """Collapse whitespace within each line but preserve line breaks."""
        if not text:
            return ""
        return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()

    def _resolve_gedcom_text(self, value: str, element=None) -> str:
        """Resolve a GEDCOM text value which may be a pointer to another element or inline text.

        Appends CONT/CONC child lines (skipping empty ones) separated by single newlines.
        """
        if not value:
            return ""

        # Pointer/reference to another element (e.g., NOTE record)
        if value.startswith("@") and value.endswith("@"):
            target = self.gedcom.get_element_dictionary().get(value)
            if not target:
                return ""
            text = target.get_value() or ""
            # Respect CONT vs CONC semantics: CONT => newline, CONC => concatenate
            for sub in target.get_child_elements():
                tag = sub.get_tag()
                val = (sub.get_value() or "")
                if not val:
                    continue
                if tag == "CONC":
                    # concatenate directly
                    text += val
                elif tag == "CONT":
                    text += "\n" + val
            return text

        # Inline text with possible CONT/CONC children
        text = value or ""
        if element is not None:
            for sub in element.get_child_elements():
                tag = sub.get_tag()
                val = (sub.get_value() or "")
                if not val:
                    continue
                if tag == "CONC":
                    text += val
                elif tag == "CONT":
                    text += "\n" + val
        return text

    def get_notes(self) -> List[str]:
        """Return the person's notes with continuations resolved and extraneous whitespace collapsed per-line."""
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
        """
        Extract SOUR references for this individual and return normalized entries.
        Each entry is a dict: {"title": str, "publ": str, "note": str} with internal whitespace collapsed.

        Handles both referenced SOURCE pointers (SOUR @X@) and inline SOURCE blocks under the individual.
        """
        def _collapse_single_line(text: str) -> str:
            return " ".join(text.split()).strip() if text else ""

        sources = []
        for child in self.element.get_child_elements():
            if child.get_tag() != "SOUR":
                continue

            title = ""
            publ = ""
            note_text = ""

            # child may be a pointer to a SOURCE record or an inline SOURCE element
            src_ref = child.get_value() or ""
            if src_ref and src_ref.startswith("@"):
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
            title = _collapse_single_line(title)
            publ = _collapse_single_line(publ)

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
                                        # Resolve image reference
                                        img_ref = sts_child.get_value()
                                        if img_ref and img_ref.startswith("@"):
                                            obje_element = self.gedcom.get_element_dictionary().get(
                                                img_ref
                                            )
                                            if obje_element:
                                                image_info = {
                                                    "file": "",
                                                    "title": "",
                                                    "format": "",
                                                }
                                                for (
                                                    obje_child
                                                ) in obje_element.get_child_elements():
                                                    if obje_child.get_tag() == "FILE":
                                                        image_info["file"] = (
                                                            obje_child.get_value() or ""
                                                        )
                                                    elif obje_child.get_tag() == "TITL":
                                                        image_info["title"] = (
                                                            obje_child.get_value() or ""
                                                        )
                                                    elif obje_child.get_tag() == "FORM":
                                                        image_info["format"] = (
                                                            obje_child.get_value() or ""
                                                        )
                                                if image_info["file"]:
                                                    section_data["images"].append(
                                                        image_info
                                                    )

                                if section_data["subtitle"] or section_data["text"]:
                                    story["sections"].append(section_data)

                        if story["title"] or story["sections"]:
                            stories.append(story)

        return stories

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