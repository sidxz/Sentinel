"""Shared Pydantic types and validators for input sanitization."""

import re
from html.parser import HTMLParser
from typing import Annotated

from pydantic import AfterValidator

# Matches complete HTML tags and also unclosed/malformed tags like "<script"
_HTML_TAG_RE = re.compile(r"<[^>]*>?")


class _TextExtractor(HTMLParser):
    """Extract only text content, discarding all tags and attributes."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def strip_html(value: str) -> str:
    """Remove HTML tags from a string.

    Uses html.parser for robust handling of malformed/unclosed tags,
    with a regex fallback for any edge cases.
    """
    if "<" not in value:
        return value.strip()
    parser = _TextExtractor()
    try:
        parser.feed(value)
        result = parser.get_text()
    except Exception:
        # Fallback: regex strip including unclosed tags
        result = _HTML_TAG_RE.sub("", value).strip()
    return result


def strip_html_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return strip_html(value)


SafeStr = Annotated[str, AfterValidator(strip_html)]
SafeStrOptional = Annotated[str | None, AfterValidator(strip_html_optional)]


def sanitize_url(value: str | None) -> str | None:
    """Allow only http(s) URLs. Blocks javascript:, data:, and other schemes."""
    if value is None:
        return None
    if not value.startswith(("https://", "http://")):
        return None
    return value


SafeUrl = Annotated[str | None, AfterValidator(sanitize_url)]


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters so they match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
