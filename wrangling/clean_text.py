"""Text cleaning utilities for messy scraped job description text."""
import re
import html


def clean_text(text: str) -> str:
    """Strip HTML entities/tags, normalize whitespace, drop boilerplate noise."""
    if not text:
        return ""

    text = html.unescape(text)                      # &amp; -> &, etc.
    text = re.sub(r"<[^>]+>", " ", text)             # strip any stray HTML tags
    text = re.sub(r"\s+", " ", text)                 # collapse whitespace/newlines
    text = text.strip()

    return text


def truncate_flag(text: str) -> bool:
    """Heuristic: does this text look cut off mid-sentence (Adzuna snippets)?"""
    if not text:
        return False
    return text.rstrip().endswith(("…", "...")) or (
        len(text) > 400 and not text.rstrip()[-1] in ".!?\""
    )
