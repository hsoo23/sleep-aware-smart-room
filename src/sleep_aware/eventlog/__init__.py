"""Structured run logging for baseline experiments."""

from .jsonl import JsonlEventLogger
from .metadata import RunMetadata, git_revision, new_run_id
from .privacy import redact
from .schema import SCHEMA_VERSION, validate_record

__all__ = [
    "SCHEMA_VERSION",
    "JsonlEventLogger",
    "RunMetadata",
    "git_revision",
    "new_run_id",
    "redact",
    "validate_record",
]
