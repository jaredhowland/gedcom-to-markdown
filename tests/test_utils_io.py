import zipfile
from pathlib import Path

from utils.io import normalize_line_endings, extract_gedzip


def test_normalize_cr_only(tmp_path):
    content = b"0 HEAD\r1 SOUR TestApp\r0 TRLR\r"
    normalized = normalize_line_endings(content)
    assert "\n" in normalized
    assert "\r" not in normalized


def test_extract_gedzip_with_media(tmp_path):
    zp = tmp_path / "sample.zip"
    ged = "family.ged"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr(ged, "0 HEAD\n0 TRLR")
        zf.writestr("images/photo.jpg", b"fake")

    outdir = tmp_path / "out"
    outdir.mkdir()
    gedfile, media_dir = extract_gedzip(zp, outdir)
    assert gedfile.exists()
    assert media_dir == outdir


def test_extract_gedzip_no_gedcom(tmp_path):
    zp = tmp_path / "bad.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("readme.txt", "hello")

    outdir = tmp_path / "out"
    outdir.mkdir()
    try:
        extract_gedzip(zp, outdir)
        assert False, "Expected ValueError"
    except ValueError:
        pass
