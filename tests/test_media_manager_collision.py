import pytest
from pathlib import Path
import shutil

import media_manager


def test_copy_media_handles_collisions(tmp_path):
    # Prepare source with a single media file
    src = tmp_path / "src"
    (src / "images").mkdir(parents=True)
    src_file = src / "images" / "photo.jpg"
    src_file.write_bytes(b"source-content")

    # Case 1: dest already has photo.jpg -> copy should create photo_1.jpg
    dest1 = tmp_path / "dest1"
    (dest1 / "images").mkdir(parents=True)
    (dest1 / "images" / "photo.jpg").write_bytes(b"existing")

    mapping1 = media_manager.copy_media(src, dest1)
    assert mapping1["images/photo.jpg"] == "photo_1.jpg"
    # Ensure the destination file exists and contains the source content
    dest_name1 = mapping1["images/photo.jpg"]
    assert (dest1 / "images" / dest_name1).read_bytes() == b"source-content"

    # Case 2: dest already has photo.jpg and photo_1.jpg -> should create photo_2.jpg
    dest2 = tmp_path / "dest2"
    (dest2 / "images").mkdir(parents=True)
    (dest2 / "images" / "photo.jpg").write_bytes(b"existing")
    (dest2 / "images" / "photo_1.jpg").write_bytes(b"existing-1")

    mapping2 = media_manager.copy_media(src, dest2)
    assert mapping2["images/photo.jpg"] == "photo_2.jpg"
    assert (dest2 / "images" / "photo_2.jpg").read_bytes() == b"source-content"
