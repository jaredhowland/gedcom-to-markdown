"""Shared text helpers for GEDCOM->Markdown project.

Functions:
- collapse_single_line(text): collapse internal whitespace on single lines
- collapse_preserve_lines(text): collapse runs of whitespace within each line but preserve line breaks
- escape_markdown(text): escape markdown emphasis characters
- repair_broken_html_tags(text): conservative repair for simple HTML tags split across lines
- write_multiline_note_block(f, lines, nested=True): write multi-line note block compatible with Obsidian

These implementations intentionally mirror the existing logic in MarkdownGenerator and Individual
so behavior is unchanged during migration.
"""

from typing import List, Optional
import re


def collapse_single_line(text: Optional[str]) -> str:
    """Normalize whitespace on a single logical line.

    Collapse runs of whitespace into single spaces and trim leading/trailing whitespace.
    Returns empty string for falsy input.
    """
    return " ".join(text.split()).strip() if text else ""


def collapse_preserve_lines(text: str) -> str:
    """Collapse runs of whitespace within each line but preserve newline boundaries.

    Each line has internal whitespace collapsed, line breaks remain.
    """
    if not text:
        return ""
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def escape_markdown(text: str) -> str:
    """Escape markdown emphasis characters to avoid accidental formatting.

    Escapes: backslash, asterisk, underscore, backtick, tilde.
    Does not escape brackets so links still render.
    """
    if not text:
        return ""
    # Escape backslash first
    text = text.replace("\\", "\\\\")
    for ch in ("*", "_", "`", "~"):
        text = text.replace(ch, f"\\{ch}")
    return text


def repair_broken_html_tags(text: str) -> str:
    """Repair a small whitelist of simple HTML tags that may be split across GEDCOM lines.

    Conservative: only removes newlines inside simple tag tokens for a small whitelist.
    """
    if not text or "<" not in text:
        return text

    WHITELIST = {"br", "b", "i", "strong", "em", "a", "span", "div", "p", "ul", "li"}

    def repl(m: re.Match) -> str:
        raw = m.group(0)
        content = raw[1:-1]
        content_no_nl = content.replace("\n", "").replace("\r", "")
        name_m = re.match(r"\s*/?\s*([A-Za-z0-9]+)", content_no_nl)
        if name_m and name_m.group(1).lower() in WHITELIST:
            repaired = "<" + content_no_nl + ">"
            return repaired
        return raw

    return re.sub(r"<[^>]*>", repl, text, flags=re.DOTALL)


def write_multiline_note_block(f, lines: List[str], nested: bool = True) -> None:
    """Write a multi-line NOTE block into the open file-like object `f`.

    Mirrors the rendering strategy used by the MarkdownGenerator:
    - nested=True: writes as an indented nested bullet block
    - nested=False: writes plain lines with intentional two-space hard breaks
    """
    if not lines:
        return

    total = len(lines)
    if nested:
        indent = "    "
        cont_indent = "      "
        if total > 1:
            f.write(f"{indent}- {lines[0]}  \n")
        else:
            f.write(f"{indent}- {lines[0]}\n")

        for idx, cont in enumerate(lines[1:], start=1):
            if idx < total - 1:
                f.write(f"{cont_indent}{cont}  \n")
            else:
                f.write(f"{cont_indent}{cont}\n")
    else:
        last_non_empty_idx = next(
            (idx for idx in range(len(lines) - 1, -1, -1) if lines[idx].strip()), None
        )
        for idx, ln in enumerate(lines):
            if not ln.strip():
                f.write("\n")
            elif idx == last_non_empty_idx:
                f.write(f"{ln}\n")
            else:
                f.write(f"{ln}  \n")
