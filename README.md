<div align="center">

![Family Tree Header](https://github.com/AlexKucera/gedcom-to-markdown/blob/main/assets/vivian-arcidiacono-WksHX9oosJI-unsplash.jpg)

# GEDCOM to Markdown Converter

**Convert GEDCOM genealogy files to Obsidian-compatible markdown notes with WikiLinks**

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Tests](https://github.com/AlexKucera/gedcom-to-markdown/actions/workflows/tests.yml/badge.svg)](https://github.com/AlexKucera/gedcom-to-markdown/actions/workflows/tests.yml)
[![Codecov](https://codecov.io/gh/AlexKucera/gedcom-to-markdown/branch/main/graph/badge.svg)](https://codecov.io/gh/AlexKucera/gedcom-to-markdown)
[![CodeRabbit Reviews](https://img.shields.io/coderabbit/prs/github/AlexKucera/gedcom-to-markdown?utm_source=oss&utm_medium=github&utm_campaign=AlexKucera%2Fgedcom-to-markdown&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit)](https://coderabbit.ai)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Examples](#examples) • [Documentation](#project-structure)

</div>

---

## Features

### Core Capabilities
- 📦 **GEDZIP Support**: Automatically extracts and processes ZIP archives with media files
- 🔧 **Automatic Line Ending Fix**: Detects and corrects Mac-style line endings
- 📁 **Organized Directory Structure**: Creates separate subdirectories for people, media, and stories (or flat structure with `--flat` flag)
- 🎨 **Canvas Visualization**: Generates Obsidian Canvas files for interactive family tree visualization with generational layout

### Rich Data Extraction
- 👤 **Complete Individual Notes**: Generates detailed markdown notes for each person
- 📖 **Separate Story Files**: Extracts long-form narratives to individual markdown files with bidirectional linking
- 🔗 **WikiLinks**: All relationships use `[[WikiLinks]]` format for Obsidian with proper path prefixes
- 📊 **Comprehensive Data**: Captures births, deaths, marriages, events, physical attributes, images, and notes
- 💑 **Multiple Marriages**: Supports individuals with multiple spouses

### File Management
- 🖼️ **Media Management**: Automatically copies and organizes image files with correct relative paths
- 📑 **Global Index**: Creates an alphabetical index of all individuals
- 🏷️ **Proper Naming**: Files named as "FamilyName FirstName BirthYear.md"

## Installation

```bash
# Clone the repository
git clone https://github.com/AlexKucera/gedcom-to-markdown.git
cd gedcom-to-markdown

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Convert a GEDCOM file with all default options
python src/main.py -i path/to/family.ged -o output/

# Convert a GEDZIP archive (recommended - includes media)
python src/main.py -i path/to/family.zip -o output/

# Generate with family tree visualization
python src/main.py -i path/to/family.zip -o output/ --canvas
```

## Usage

### Basic Usage

```bash
# Full syntax
python src/main.py --input path/to/family.ged --output output/directory

# Short form
python src/main.py -i path/to/family.ged -o output/directory
```

### GEDZIP Support (Recommended)

For best results, **export your genealogy data as a GEDZIP (ZIP) file** which includes both the GEDCOM data and all media files:

```bash
python src/main.py -i path/to/family.zip -o output/directory
```

This will automatically:
- Extract the ZIP file
- Find and process the GEDCOM file
- Copy all media files to the output directory
- Fix line endings if needed
- Clean up temporary files
- Create organized subdirectories for people, media, and stories

### Directory Structure

By default, the converter creates an **organized directory structure**:

```text
output/
├── Index.md                    # Alphabetical index of all people
├── people/                     # Person markdown files
│   ├── Knebl Maria.md
│   ├── Schaaf Clemens.md
│   └── ...
├── media/                      # Images and media files
│   ├── 57328800.jpg
│   └── ...
└── stories/                    # Separate story files
    ├── Der lange Weg meiner Familie.md
    └── ...
```

**Flat Structure Mode**: Use the `--flat` flag to put all files in the output root directory instead:

```bash
python src/main.py -i family.zip -o output --flat
```

### Options

- `-i`, `--input FILE`: Path to input GEDCOM (.ged) or GEDZIP (.zip) file (required)
- `-o`, `--output DIR`: Output directory for generated notes (required)
- `--flat`: Use flat structure (all files in output root). Default creates subdirectories
- `--no-index`: Skip creating the index file
- `--canvas`: Create an Obsidian canvas file for family tree visualization
- `--root ID`: Root person for canvas. Can be a selection number (e.g., `85`) or GEDCOM ID (e.g., `@I253884714@` or `I253884714`). If not provided with `--canvas`, will prompt interactively
- `--verbose` or `-v`: Enable detailed logging

### Examples

**With GEDZIP file (structured output):**
```bash
python src/main.py -i examples/family.zip -o examples/output --verbose
```

**With plain GEDCOM file (flat output):**
```bash
python src/main.py -i examples/family.ged -o examples/output --flat --verbose
```

**Generate family tree canvas with specific root person (by selection number):**
```bash
python src/main.py -i family.ged -o output --canvas --root 85
```

**Generate canvas with specific root person (by GEDCOM ID):**
```bash
python src/main.py -i family.ged -o output --canvas --root @I253884714@
```

**Generate canvas with interactive root person selection:**
```bash
python src/main.py -i family.ged -o output --canvas
```

**Using long form arguments:**
```bash
python src/main.py --input examples/family.zip --output examples/output
```

## Output Format

### Person Notes

Each person gets a markdown note in the `people/` directory (or output root if using `--flat`) with sections for:
- **Attributes**: Name, birth, death, physical characteristics
- **Life Events**: Occupations, education, residences, etc.
- **Families**: Marriages with dates, places, and children
- **Parents**: Links to parent notes
- **Images**: Media references with proper paths
- **Notes**: General notes and links to story files

### Story Files

Long-form narratives and stories are extracted to **separate markdown files** in the `stories/` directory (or output root if using `--flat`). Each story file includes:
- Story title and description
- Link back to the related person
- Multiple sections with text and images
- Properly resolved image paths

Stories are linked from person notes using WikiLinks, making it easy to navigate between family members and their stories in Obsidian.

### Index File

The `Index.md` file at the root contains an alphabetical listing of all individuals with WikiLinks to their person notes.

## Canvas Visualization

The `--canvas` option generates an **Obsidian Canvas file** that provides an interactive, visual representation of your family tree. This creates a `.canvas` file in your output directory that can be opened in Obsidian for a graphical view of family relationships.

### How It Works

The canvas generator uses a **generational layout algorithm** that arranges family members spatially:

- **Timeline Layout**: Ancestors appear to the right, descendants to the left, creating a left-to-right timeline
- **Vertical Positioning**: Family members are arranged vertically with gender-aware positioning to minimize relationship line crossings
- **Automatic Tree Building**: Uses breadth-first search from the selected root person to build the family tree
- **Disconnected Families**: Automatically detects and includes unconnected family groups as separate sections
- **Visual Elements**:
  - Each person appears as a card/node with their name and basic information
  - Person images are embedded in the canvas nodes when available
  - Parent-child relationships shown as lines connecting left to right
  - Spouse relationships shown as bidirectional vertical connections

### Root Person Selection

When using the `--canvas` flag, you can specify the root person in several ways:

```bash
# Interactive selection (displays numbered list)
python src/main.py -i family.ged -o output --canvas

# By selection number
python src/main.py -i family.ged -o output --canvas --root 85

# By GEDCOM ID
python src/main.py -i family.ged -o output --canvas --root @I253884714@
```

The root person serves as the starting point for building the family tree visualization.

### Limitations and Known Issues

While the canvas generator creates a useful visualization, it has some limitations:

1. **Spacing Approximations**: The algorithm calculates node positions using heuristics for spacing. Complex family structures (many siblings, multiple marriages) can sometimes result in:
   - Nodes positioned slightly too close together
   - Occasional minor overlaps between adjacent cards

2. **Manual Adjustments Expected**: In most cases, **a few nodes may overlap slightly**, but these overlaps are typically minimal and **can easily be fixed by hand** in Obsidian by dragging the nodes to better positions.

3. **Complex Marriages**: Individuals with multiple marriages may have relationship lines that cross in non-optimal ways.

4. **Large Trees**: Very large family trees (100+ individuals) may require manual adjustment for optimal viewing.

5. **Edge Routing**: Connection lines between nodes use straight lines, which can sometimes cross through other nodes in complex family structures.

### Tips for Best Results

- Start with a central family member (grandparent or parent) as the root person
- For large families, consider creating multiple canvas files focused on different branches
- Use Obsidian's zoom and pan features to navigate large canvases
- After initial generation, spend a few minutes adjusting any overlapping nodes for a cleaner layout
- The canvas is fully interactive - you can reorganize it to suit your preferences while maintaining all the relationship connections

### Canvas Plugin System

The canvas generator can be extended or replaced via a plugin system. Third-party packages may register a Canvas implementation under the entry-point group `gedcom_to_markdown.canvas_plugins`.

- Entry-point group: `gedcom_to_markdown.canvas_plugins`
- CLI selection: `--canvas-plugin NAME` (default: `default`)
- Runtime listing: `--list-canvas-plugins` prints discovered plugins
- Programmatic selection: `src.api.convert(..., plugin_name="NAME")`

Example `pyproject.toml` entry-point (third-party package):

```toml
[project.entry-points."gedcom_to_markdown.canvas_plugins"]
# example plugin published by another package
example = "example_pkg.plugins:PluginClass"
```

Minimal plugin example (class should accept `individuals, output_dir` and implement `generate_canvas(root_id, canvas_filename)`):

```py
class MyCanvasPlugin:
    def __init__(self, individuals, output_dir):
        self.individuals = individuals
        self.output_dir = output_dir

    def generate_canvas(self, root_person_id, canvas_filename="Family Tree.canvas"):
        # create canvas file at self.output_dir and return path
        return f"{self.output_dir}/{canvas_filename}"
```

After packaging and installing a plugin, it will be discovered at runtime; use `--canvas-plugin <name>` to select it when running the CLI.

## Project Structure

```text
src/
├── gedcom_parser.py      # GEDCOM file parsing
├── individual.py         # Person data model
├── markdown_generator.py # Note generation
├── index_generator.py    # Index file creation
├── canvas_generator.py   # Obsidian Canvas visualization
├── person_selector.py    # Interactive root person selection
└── main.py              # CLI entry point

tests/
├── conftest.py              # Shared test fixtures
├── test_gedcom_parser.py    # Parser tests
├── test_individual.py       # Individual model tests
├── test_markdown_generator.py # Markdown generation tests
├── test_index_generator.py  # Index generation tests
└── test_main.py             # CLI integration tests
```

## Requirements

- Python 3.8+
- python-gedcom==1.0.0

## Common Issues

### Line Ending Issue

Some GEDCOM files exported from macOS applications use old Mac-style line endings (CR only). **This is automatically detected and fixed** by the converter.

If you see a warning message like:
```text
WARNING - Detected old Mac-style (CR-only) line endings in GEDCOM file.
Converting to Unix-style (LF) line endings...
```

This is normal and the file will be automatically corrected. No manual intervention is needed.

### GEDCOM Version Compatibility

This tool works best with **GEDCOM version 5.5.x or 5.x**. If you're using GEDCOM 7.0+, you may encounter issues with custom tags and story extraction. When exporting from your genealogy software:

1. Choose GEDCOM version 5.5.1 or 5.1.0 if available
2. Avoid GEDCOM version 7.0+ for better compatibility
3. **Export as GEDZIP (ZIP)** to include media files automatically

### Exporting GEDZIP from Your Genealogy Software

Most genealogy applications support exporting to GEDZIP format:

- **Family Tree Maker**: File → Export → GEDCOM Package (includes media)
- **MobileFamilyTree**: Share → GEDCOM Package → Include Media
- **Ancestry**: Export family tree → Include media files → Download as ZIP
- **Gramps**: Family Trees → Export → GEDCOM with Media

The GEDZIP format is a standard ZIP archive containing:
- A `.ged` file with your family tree data
- All referenced media files (photos, documents, etc.)

This is the **recommended export format** for use with this converter.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run tests in verbose mode
pytest -v
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [python-gedcom](https://github.com/nickreynke/python-gedcom) for GEDCOM parsing
- Designed for [Obsidian](https://obsidian.md) - the knowledge base that works on local Markdown files
- Family tree visualization inspired by genealogy research workflows

---

<div align="center">

**Made with ❤️ for genealogy enthusiasts and family historians**

[⬆ Back to Top](#gedcom-to-markdown-converter)

</div>
