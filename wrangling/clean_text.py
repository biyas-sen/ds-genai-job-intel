"""Text cleaning utilities for messy scraped job description text."""
import re
import html

# Known boilerplate injected by recruiting platforms that appears verbatim
# across totally unrelated job postings -- pure noise for any text analysis
# (skill extraction, clustering, etc). Stripped before general cleaning.
BOILERPLATE_PATTERNS = [
    re.compile(
        r"This job is with .*?myGwork.*?Please do not contact the recruiter directly\.?",
        re.IGNORECASE | re.DOTALL,
    ),
]


def clean_text(text: str) -> str:
    """Strip boilerplate, HTML entities/tags, normalize whitespace and punctuation."""
    if not text:
        return ""

    # Normalize "smart" typographic punctuation to plain ASCII equivalents.
    # Different sources (Adzuna vs JSearch) encode the same sentence with
    # different quote/dash characters (curly '' "" vs straight '' ""; em/en
    # dash vs hyphen). Left unnormalized, this makes two otherwise-identical
    # strings compare as different -- which silently broke company
    # boilerplate detection (exact-prefix matching) further downstream.
    smart_punctuation = {
        "\u2018": "'", "\u2019": "'",   # curly single quotes
        "\u201c": '"', "\u201d": '"',   # curly double quotes
        "\u2013": "-", "\u2014": "-",   # en dash, em dash
        "\u2026": "...",                 # ellipsis character
    }
    for smart, plain in smart_punctuation.items():
        text = text.replace(smart, plain)

    for pattern in BOILERPLATE_PATTERNS:
        text = pattern.sub(" ", text)

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
