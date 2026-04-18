import tempfile
from pathlib import Path
from utils.media import copy_media_preserve_structure


def write_file(p: Path, data: bytes = b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_skip_identical_files(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    # Create source file
    s = src / "photo.jpg"
    write_file(s, b"ABC")

    # Pre-create identical file in destination to simulate existing copy
    d = dst / "photo.jpg"
    write_file(d, b"ABC")

    copy_media_preserve_structure(src, dst)

    # Should not create suffix file; destination remains single file with same content
    assert (dst / "photo.jpg").exists()
    files = [p for p in dst.iterdir() if p.is_file()]
    assert len(files) == 1
    assert (dst / "photo.jpg").read_bytes() == b"ABC"


def test_sequential_collision_suffixing(tmp_path):
    src1 = tmp_path / "src1"
    src2 = tmp_path / "src2"
    dst = tmp_path / "dst"

    # First source file
    s1 = src1 / "photo.jpg"
    write_file(s1, b"first")
    copy_media_preserve_structure(src1, dst)
    assert (dst / "photo.jpg").exists()
    assert (dst / "photo.jpg").read_bytes() == b"first"

    # Second source has a file with same relative path but different content
    s2 = src2 / "photo.jpg"
    write_file(s2, b"second")
    copy_media_preserve_structure(src2, dst)

    # Now dst should have photo.jpg and photo-1.jpg
    assert (dst / "photo.jpg").exists()
    assert (dst / "photo-1.jpg").exists()
    assert (dst / "photo-1.jpg").read_bytes() == b"second"

    # Third sequential copy should create photo-2.jpg
    src3 = tmp_path / "src3"
    s3 = src3 / "photo.jpg"
    write_file(s3, b"third")
    copy_media_preserve_structure(src3, dst)
    assert (dst / "photo-2.jpg").exists()
    assert (dst / "photo-2.jpg").read_bytes() == b"third"


def test_extension_case_insensitivity(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    s = src / "IMAGE.JPEG"
    write_file(s, b"jpegdata")

    copy_media_preserve_structure(src, dst)

    # Should copy despite uppercase extension
    assert (dst / "IMAGE.JPEG").exists()
    assert (dst / "IMAGE.JPEG").read_bytes() == b"jpegdata"
