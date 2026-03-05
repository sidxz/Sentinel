"""Shared Pydantic types and validators for input sanitization."""

import re
from typing import Annotated

from pydantic import AfterValidator

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub("", value).strip()


def strip_html_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return strip_html(value)


SafeStr = Annotated[str, AfterValidator(strip_html)]
SafeStrOptional = Annotated[str | None, AfterValidator(strip_html_optional)]
