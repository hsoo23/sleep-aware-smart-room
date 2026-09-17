"""Redaction of personal or network identifiers from free-text log fields."""

from __future__ import annotations

import re

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # URLs first so credentials, paths, and query strings inside them are removed whole.
    (re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s'\"<>]+"), "<url>"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<ip>"),
    (
        re.compile(
            r"(?<![\w:])(?:(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
            r"|(?:[0-9A-Fa-f]{1,4}:)*[0-9A-Fa-f]{0,4}::(?:[0-9A-Fa-f]{1,4}:)*[0-9A-Fa-f]{0,4})"
            r"(?![\w:])"
        ),
        "<ip>",
    ),
    # A user name may contain spaces, so mask through the next separator when one follows;
    # over-masking the rest of a message is preferred to leaking part of a path.
    (
        re.compile(r"(?:/Users|/home)/(?:[^/\n'\"<>]+/[^\s'\"<>]*|[^\s'\"<>]+)"),
        "<path>",
    ),
    (
        re.compile(
            r"\b[A-Za-z]:\\(?:Users|Documents and Settings)\\"
            r"(?:[^\\\n'\"<>]+\\[^\s'\"<>]*|[^\s'\"<>]+)"
        ),
        "<path>",
    ),
    # Local-network hostnames such as raspberrypi.local; public domains stay readable.
    (
        re.compile(
            r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
            r"(?:local|lan|home|internal|localdomain)\.?(?![\w.-])",
            re.IGNORECASE,
        ),
        "<host>",
    ),
)


def redact(text: str) -> str:
    """Replace emails, URLs, IPs, home-directory paths, and local hostnames with placeholders."""
    for pattern, placeholder in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
