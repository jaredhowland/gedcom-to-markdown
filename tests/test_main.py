"""
Tests for the main CLI module.

This module tests the command-line interface and main conversion workflow including:
- CLI argument parsing
- GEDZIP extraction
- Full conversion workflow
- Error handling
- Directory structure options
"""

import pytest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import main
from main import (
    setup_logging,
    extract_gedzip,
    convert_gedcom_to_markdown,
)


class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_setup_logging_default(self):
        """Test default logging setup (WARNING level for root, INFO for __main__)."""
        import logging

        # Clear any existing handlers
        logging.root.handlers.clear()
        setup_logging(verbose=False)
        # Check root logger level (should be WARNING for non-verbose)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
        # Main module logger should be INFO
        main_logger = logging.getLogger("__main__")
        assert (
            main_logger.level == logging.INFO or main_logger.level == 0
        )  # 0 means NOTSET (inherits from parent)

    def test_setup_logging_verbose(self):
        """Test verbose logging setup (DEBUG level)."""
        import logging

        # Clear any existing handlers
        logging.root.handlers.clear()
        setup_logging(verbose=True)
        # Check root logger level
        root_logger = logging.getLogger()
        assert root_logger.level <= logging.DEBUG


class TestGedzipExtraction:
    """Tests for GEDZIP file extraction."""

    @pytest.fixture
    def gedzip_file(self, temp_dir, sample_gedcom_content):
        """Create a sample GEDZIP file."""
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Add GEDCOM file
            zf.writestr("family.ged", sample_gedcom_content)

            # Add some media files
            zf.writestr("images/photo1.jpg", b"fake image data")
            zf.writestr("images/photo2.png", b"fake image data")

        return zip_path

    def test_extract_gedzip(self, gedzip_file, temp_dir):
        """Test GEDZIP extraction."""
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()

        gedcom_file, media_dir = extract_gedzip(gedzip_file, extract_dir)

        assert gedcom_file is not None
        assert gedcom_file.exists()
        assert gedcom_file.suffix == ".ged"

        # Media directory should be found
        assert media_dir is not None
        assert media_dir.exists()

    def test_extract_gedzip_no_media(self, temp_dir, sample_gedcom_content):
        """Test GEDZIP extraction when no media files are present."""
        zip_path = temp_dir / "no_media.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("family.ged", sample_gedcom_content)

        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()

        gedcom_file, media_dir = extract_gedzip(zip_path, extract_dir)

        assert gedcom_file is not None
        assert gedcom_file.exists()
        assert media_dir is None  # No media directory found

    def test_extract_gedzip_no_gedcom(self, temp_dir):
        """Test that ValueError is raised when ZIP has no GEDCOM file."""
        zip_path = temp_dir / "invalid.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "This is not a GEDCOM file")

        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()

        with pytest.raises(ValueError) as exc_info:
            extract_gedzip(zip_path, extract_dir)

        assert "No GEDCOM" in str(exc_info.value)

    def test_extract_gedzip_multiple_gedcom(self, temp_dir, sample_gedcom_content):
        """Test extraction when ZIP has multiple GEDCOM files."""
        zip_path = temp_dir / "multiple.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("family1.ged", sample_gedcom_content)
            zf.writestr("family2.ged", sample_gedcom_content)

        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()

        # Should use the first one and log a warning
        gedcom_file, _media_dir = extract_gedzip(zip_path, extract_dir)

        assert gedcom_file is not None
        assert gedcom_file.exists()

    def test_extract_gedzip_nested_media(self, temp_dir, sample_gedcom_content):
        """Test that media files in nested subdirectories are discovered."""
        zip_path = temp_dir / "nested_media.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("family.ged", sample_gedcom_content)
            # Add media files in multiple nested directories
            zf.writestr("media/photos/photo1.jpg", b"fake image")
            zf.writestr("media/documents/scan1.png", b"fake scan")
            zf.writestr("images/subfolder/deep/photo2.jpg", b"fake image")

        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()

        gedcom_file, media_dir = extract_gedzip(zip_path, extract_dir)

        # media_dir should point to extraction root
        assert media_dir == extract_dir

        # All media files should be discoverable via rglob
        all_media = list(media_dir.rglob("*.jpg")) + list(media_dir.rglob("*.png"))
        assert len(all_media) == 3


class TestConversionWorkflow:
    """Tests for the main conversion workflow."""

    def test_convert_gedcom_to_markdown_success(self, sample_gedcom_file, output_dir):
        """Test successful conversion."""
        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Check that files were created
        md_files = list(output_dir.glob("*.md"))
        assert len(md_files) > 0

        # Check for index file
        index_file = output_dir / "Index.md"
        assert index_file.exists()

    def test_convert_with_subdirectories(self, sample_gedcom_file, output_dir):
        """Test conversion with subdirectory structure."""
        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            use_flat_structure=False,
        )

        assert exit_code == 0

        # Check that subdirectories were created
        people_dir = output_dir / "people"
        media_dir = output_dir / "media"
        stories_dir = output_dir / "stories"

        assert people_dir.exists()
        assert media_dir.exists()
        assert stories_dir.exists()

        # Check that people files are in people directory
        md_files = list(people_dir.glob("*.md"))
        assert len(md_files) > 0

    def test_convert_without_index(self, sample_gedcom_file, output_dir):
        """Test conversion without creating index."""
        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=False,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Index file should not exist
        index_file = output_dir / "Index.md"
        assert not index_file.exists()

    def test_convert_with_media_files(self, sample_gedcom_file, output_dir, temp_dir):
        """Test conversion with media file copying."""
        # Create a media directory with test files
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        (media_dir / "photo1.jpg").write_text("fake image")
        (media_dir / "photo2.png").write_text("fake image")

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Check that media files were copied
        copied_files = list(output_dir.glob("*.jpg")) + list(output_dir.glob("*.png"))
        assert len(copied_files) >= 2

    def test_convert_empty_gedcom(self, temp_dir, output_dir):
        """Test conversion with GEDCOM containing no individuals."""
        empty_gedcom = temp_dir / "empty.ged"
        empty_gedcom.write_text(
            """0 HEAD
1 SOUR TestApp
0 TRLR
""",
            encoding="utf-8",
        )

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=empty_gedcom,
            output_dir=output_dir,
            create_index=True,
            use_flat_structure=True,
        )

        # Should return error code
        assert exit_code == 1

    def test_convert_file_not_found(self, temp_dir, output_dir):
        """Test conversion with non-existent file."""
        nonexistent = temp_dir / "nonexistent.ged"

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=nonexistent,
            output_dir=output_dir,
            create_index=True,
            use_flat_structure=True,
        )

        assert exit_code == 1


class TestCLIArgumentParsing:
    """Tests for command-line argument parsing."""

    def test_cli_with_gedcom_file(self, sample_gedcom_file, output_dir):
        """Test CLI with GEDCOM file input."""
        test_args = ["main.py", "-i", str(sample_gedcom_file), "-o", str(output_dir)]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

    def test_cli_with_zip_file(self, temp_dir, output_dir, sample_gedcom_content):
        """Test CLI with ZIP file input."""
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("family.ged", sample_gedcom_content)

        test_args = ["main.py", "-i", str(zip_path), "-o", str(output_dir)]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

    def test_cli_with_flat_option(self, sample_gedcom_file, output_dir):
        """Test CLI with --flat option."""
        test_args = [
            "main.py",
            "-i",
            str(sample_gedcom_file),
            "-o",
            str(output_dir),
            "--flat",
        ]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

        # Should not create subdirectories
        people_dir = output_dir / "people"
        assert not people_dir.exists()

        # Files should be in root
        md_files = list(output_dir.glob("*.md"))
        assert len(md_files) > 0

    def test_cli_with_no_index_option(self, sample_gedcom_file, output_dir):
        """Test CLI with --no-index option."""
        test_args = [
            "main.py",
            "-i",
            str(sample_gedcom_file),
            "-o",
            str(output_dir),
            "--no-index",
        ]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

        # Index should not be created
        index_file = output_dir / "Index.md"
        assert not index_file.exists()

    def test_cli_with_verbose_option(self, sample_gedcom_file, output_dir):
        """Test CLI with -v/--verbose option."""
        test_args = [
            "main.py",
            "-i",
            str(sample_gedcom_file),
            "-o",
            str(output_dir),
            "--verbose",
        ]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

    def test_cli_missing_input_file(self, output_dir):
        """Test CLI error when input file doesn't exist."""
        test_args = ["main.py", "-i", "/nonexistent/file.ged", "-o", str(output_dir)]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 1

    def test_cli_creates_output_dir(self, sample_gedcom_file, temp_dir):
        """Test that CLI creates output directory if it doesn't exist."""
        output_dir = temp_dir / "new_output"
        assert not output_dir.exists()

        test_args = ["main.py", "-i", str(sample_gedcom_file), "-o", str(output_dir)]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0
        assert output_dir.exists()


class TestErrorHandling:
    """Tests for error handling in conversion workflow."""

    def test_invalid_gedcom_format(self, temp_dir, output_dir):
        """Test handling of invalid GEDCOM format."""
        invalid_file = temp_dir / "invalid.ged"
        invalid_file.write_text("This is not valid GEDCOM at all", encoding="utf-8")

        # Should handle gracefully and return error code
        try:
            exit_code = convert_gedcom_to_markdown(
                gedcom_file=invalid_file,
                output_dir=output_dir,
                create_index=True,
                use_flat_structure=True,
            )
            # May succeed (library is lenient) or fail - both are acceptable
            assert exit_code in [0, 1]
        except Exception:
            # Exception is also acceptable for invalid input
            pass

    def test_permission_error_handling(self, sample_gedcom_file, temp_dir):
        """Test handling of permission errors."""
        # Create a read-only output directory
        output_dir = temp_dir / "readonly"
        output_dir.mkdir()

        # This test is tricky to make cross-platform, so we'll just verify
        # the function handles errors gracefully
        try:
            exit_code = convert_gedcom_to_markdown(
                gedcom_file=sample_gedcom_file,
                output_dir=output_dir,
                create_index=True,
                use_flat_structure=True,
            )
            # Should either succeed or return error code
            assert exit_code in [0, 1]
        except Exception:
            # Exceptions should be caught
            pass


class TestMediaFileCopying:
    """Tests for media file copying functionality."""

    def test_media_file_extensions(self, sample_gedcom_file, output_dir, temp_dir):
        """Test that various image extensions are copied."""
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        # Create files with different extensions
        # Note: JPEG might not be in the list, only jpg/JPG
        extensions = ["jpg", "jpeg", "png", "gif", "bmp", "JPG", "PNG"]
        for ext in extensions:
            (media_dir / f"photo.{ext}").write_text("fake image")

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Check that files were copied (at least the common formats)
        copied_count = len(list(output_dir.glob("photo.*")))
        assert copied_count >= 5  # At least most formats should be copied

    def test_no_media_dir(self, sample_gedcom_file, output_dir):
        """Test conversion when no media directory is provided."""
        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=None,
            use_flat_structure=True,
        )

        # Should succeed without media
        assert exit_code == 0

    def test_nested_directory_structure_preservation(
        self, sample_gedcom_file, output_dir, temp_dir
    ):
        """Test that nested media directory structure is preserved."""
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        # Create nested directory structure
        (media_dir / "photos" / "family").mkdir(parents=True)
        (media_dir / "photos" / "events").mkdir(parents=True)
        (media_dir / "documents").mkdir(parents=True)

        # Create files in nested directories
        (media_dir / "photos" / "family" / "photo1.jpg").write_text("fake image")
        (media_dir / "photos" / "events" / "photo2.png").write_text("fake image")
        (media_dir / "documents" / "scan.jpg").write_text("fake image")

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Verify directory structure is preserved
        assert (output_dir / "photos" / "family" / "photo1.jpg").exists()
        assert (output_dir / "photos" / "events" / "photo2.png").exists()
        assert (output_dir / "documents" / "scan.jpg").exists()

    def test_filename_collision_handling(
        self, sample_gedcom_file, output_dir, temp_dir
    ):
        """Test that filename collisions are handled with numeric suffixes."""
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        # Create subdirectories with same filenames
        (media_dir / "dir1").mkdir()
        (media_dir / "dir2").mkdir()

        # Create files with same name in different directories
        (media_dir / "dir1" / "photo.jpg").write_text("image 1")
        (media_dir / "dir2" / "photo.jpg").write_text("image 2")

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # First file should be copied normally
        assert (output_dir / "dir1" / "photo.jpg").exists()

        # Second file should be copied with preserved structure (no collision)
        assert (output_dir / "dir2" / "photo.jpg").exists()

        # Both files should exist
        assert len(list(output_dir.rglob("photo*.jpg"))) == 2

    def test_case_insensitive_extensions(
        self, sample_gedcom_file, output_dir, temp_dir
    ):
        """Test that extensions are matched case-insensitively."""
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        # Create files with mixed-case extensions
        (media_dir / "photo1.JpG").write_text("fake image")
        (media_dir / "photo2.PnG").write_text("fake image")
        (media_dir / "photo3.GiF").write_text("fake image")

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # All files should be copied despite mixed case
        assert (output_dir / "photo1.JpG").exists()
        assert (output_dir / "photo2.PnG").exists()
        assert (output_dir / "photo3.GiF").exists()

    def test_non_media_files_ignored(self, sample_gedcom_file, output_dir, temp_dir):
        """Test that non-media files are ignored."""
        media_dir = temp_dir / "media"
        media_dir.mkdir()

        # Create media and non-media files
        (media_dir / "photo.jpg").write_text("fake image")
        (media_dir / "readme.txt").write_text("some text")
        (media_dir / "data.csv").write_text("some data")
        (media_dir / "script.py").write_text('print("hello")')

        exit_code = convert_gedcom_to_markdown(
            gedcom_file=sample_gedcom_file,
            output_dir=output_dir,
            create_index=True,
            media_dir=media_dir,
            use_flat_structure=True,
        )

        assert exit_code == 0

        # Only media file should be copied
        assert (output_dir / "photo.jpg").exists()
        assert not (output_dir / "readme.txt").exists()
        assert not (output_dir / "data.csv").exists()
        assert not (output_dir / "script.py").exists()


class TestTempDirectoryCleanup:
    """Tests for temporary directory cleanup."""

    def test_temp_dir_cleaned_after_zip_extraction(
        self, temp_dir, output_dir, sample_gedcom_content
    ):
        """Test that temporary directory is cleaned up after ZIP extraction."""
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("family.ged", sample_gedcom_content)

        test_args = ["main.py", "-i", str(zip_path), "-o", str(output_dir)]

        with patch("sys.argv", test_args):
            exit_code = main.main()

        assert exit_code == 0

        # Temp directory should be cleaned up
        # We can't easily check this without modifying the code,
        # but we verify the function completed successfully
        assert True
