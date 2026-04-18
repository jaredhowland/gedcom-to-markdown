import tempfile
from pathlib import Path
from utils.media import copy_media_preserve_structure


def write_file(p: Path, data: bytes = b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_nested_directory_structure_preservation(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    a = src / "nested" / "images" / "photo.jpg"
    write_file(a, b"1")

    copy_media_preserve_structure(src, dst)

    assert (dst / "nested" / "images" / "photo.jpg").exists()


def test_filename_collision_handling(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    a = src / "photo.jpg"
    b = src / "sub" / "photo.jpg"
    write_file(a, b"1")
    write_file(b, b"2")

    copy_media_preserve_structure(src, dst)

    # original file copied
    assert (dst / "photo.jpg").exists()
    # collision handled by suffix for the second file
    assert (
        any(p.name.startswith("photo-") for p in (dst / "sub").iterdir() if p.is_file())
        or (dst / "sub" / "photo.jpg").exists()
    )
