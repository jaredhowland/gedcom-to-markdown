import io

from utils.text import (
    collapse_single_line,
    collapse_preserve_lines,
    escape_markdown,
    repair_broken_html_tags,
    write_multiline_note_block,
)


def test_collapse_single_line():
    assert (
        collapse_single_line("  Overland    Travels  Pioneer   Detail  ")
        == "Overland Travels Pioneer Detail"
    )
    assert collapse_single_line("") == ""
    assert collapse_single_line(None) == ""


def test_collapse_preserve_lines():
    src = "  Line  one  \n  Line   two\n\n  Line three "
    out = collapse_preserve_lines(src)
    assert out == "Line one\nLine two\n\nLine three"


def test_escape_markdown():
    s = r"This *is* _a_ `test` ~tilde~ and back\\"
    escaped = escape_markdown(s)
    # Should contain escaped characters
    assert "\\*" in escaped
    assert "\\_" in escaped
    assert "\\`" in escaped
    assert "\\~" in escaped
    assert "\\\\" in escaped


def test_repair_broken_html_tags():
    # Broken tag split across lines
    src = "A line with a broken tag: <b\nr> and more"
    repaired = repair_broken_html_tags(src)
    assert "<br>" in repaired

    # Non-whitelisted tags should remain
    src2 = "<custom\nTag>keep</custom>"
    assert repair_broken_html_tags(src2) == src2


def test_write_multiline_note_block_nested():
    buf = io.StringIO()
    lines = ["First line", "Second line", "Third line"]
    write_multiline_note_block(buf, lines, nested=True)
    out = buf.getvalue()
    # Should contain nested bullet and indented continuation lines
    assert "    - First line" in out
    assert "      Second line" in out
    assert "      Third line" in out


def test_write_multiline_note_block_non_nested():
    buf = io.StringIO()
    lines = ["Line 1", "", "Line 3"]
    write_multiline_note_block(buf, lines, nested=False)
    out = buf.getvalue()
    # Blank line preserved and trailing two spaces used for hard breaks except last non-empty
    assert "Line 1  \n" in out
    assert "\n" in out
    assert "Line 3\n" in out
