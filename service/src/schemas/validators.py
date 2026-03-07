"""Shared Pydantic types and validators for input sanitization."""

from typing import Annotated

import nh3
from pydantic import AfterValidator


def strip_html(value: str) -> str:
    """Remove HTML tags from a string using nh3 (Rust-based sanitizer)."""
    if "<" not in value:
        return value.strip()
    return nh3.clean(value, tags=set()).strip()


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
