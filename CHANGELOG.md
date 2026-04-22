# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- External OBJE URL handling: record remote OBJE references (FORM URL or FILE starting with http/https) in a `## External media` section within each person note.
- Optional downloading of external media with CLI flags: `--download-media`, `--media-download-timeout`, `--media-download-retries`, `--media-download-max-bytes`, `--media-download-concurrency`, and `--media-download-rate`. Downloads use streaming writes, atomic file replacement, exponential backoff, and honor HTTP 429 Retry-After headers.
- Concurrent downloads with configurable concurrency and optional global rate limiting to be polite to remote servers.
- Safe filename sanitization and collision handling for downloaded media.
- Tests covering URL-based OBJE handling, download behavior, Retry-After, filename collisions, and max-bytes enforcement.

## [1.0.0] - 2025-11-02

### Added
- GEDCOM to Markdown conversion with Obsidian-compatible WikiLinks
- GEDZIP (ZIP archive) support for packages with media files
- Automatic extraction and processing of GEDZIP archives
- Automatic detection and correction of Mac-style (CR-only) line endings
- Organized directory structure with people/, media/, and stories/ subdirectories
- Flat directory structure option via `--flat` flag
- Obsidian Canvas generation for interactive family tree visualization
- Generational layout for canvas (ancestors right, descendants left)
- Gender-aware vertical positioning in canvas to reduce edge crossings
- Interactive root person selection for canvas generation
- Support for specifying root person by selection number or GEDCOM ID
- Comprehensive individual markdown notes with:
  - Names, dates, and life events
  - Physical attributes (eyes, hair, height)
  - Multiple marriages and families
  - Parent and children relationships
  - Images and media references
  - Notes and documentation
- Separate story file extraction from `_STO` tags
- Bidirectional linking between person notes and story files
- Properly resolved image paths in story files
- Global alphabetical index of all individuals
- Media file management with automatic copying and organization
- Filename collision detection and resolution with numeric suffixes
- Proper file naming convention: "FamilyName FirstName BirthYear.md"
- WikiLinks with proper path prefixes for subdirectory navigation
- Comprehensive test suite using pytest
- Code coverage reporting with pytest-cov
- Modular architecture with separate parsers, generators, and models
- Command-line interface with argparse
- Support for `--input`/`--output` flags (with `-i`/`-o` short forms)
- Verbose logging option with `--verbose`/`-v`
- Option to skip index generation with `--no-index`
- Canvas generation option with `--canvas`
- Root person specification with `--root`
- Support for GEDCOM version 5.5.x and 5.x
- Handling of disconnected family trees in canvas visualization

### Technical
- Python 3.8+ compatibility (3.7 is EOL and no longer supported)
- Uses `python-gedcom==1.0.0` for GEDCOM parsing
- Pytest-based testing infrastructure
- Branch and line coverage analysis
- Comprehensive error handling with specific exceptions
- Module-level logging with configurable verbosity
- Type hints for all function signatures
- Google-style docstrings for all public APIs
- PEP 8 code style compliance

[1.0.0]: https://github.com/AlexKucera/gedcom-to-markdown/releases/tag/v1.0.0
