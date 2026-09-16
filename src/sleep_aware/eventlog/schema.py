"""Versioned JSONL record schema for baseline run logs.

See ``docs/LOGGING_SCHEMA.md`` for field semantics. Every line of a run log is
one JSON object whose ``record_type`` selects the field specification below.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from sleep_aware.control import Action, Intention
from sleep_aware.detection import DrowsinessState

from .privacy import redact

SCHEMA_VERSION = "1.0"

RUN_STATUSES = ("completed", "failed")

_STR = (str,)
_NUMBER = (int, float)
_INT = (int,)
_BOOL = (bool,)
_NONE = (type(None),)
_OBJECT = (dict,)
_LIST = (list,)

_COMMON_FIELDS: dict[str, tuple[type, ...]] = {
    "schema_version": _STR,
    "record_type": _STR,
    "run_id": _STR,
    "wall_time_utc": _STR,
}

RUN_START_FIELDS: dict[str, tuple[type, ...]] = {
    **_COMMON_FIELDS,
    "intention": _STR,
    "software_version": _STR,
    "git_commit": _STR + _NONE,
    "git_dirty": _BOOL + _NONE,
    "detector_name": _STR,
    "detector_version": _STR,
    "config_version": _STR,
    "detector_config": _OBJECT,
    "python_version": _STR,
    "platform": _STR,
}

FRAME_FIELDS: dict[str, tuple[type, ...]] = {
    **_COMMON_FIELDS,
    "frame_sequence": _INT,
    "monotonic_timestamp_s": _NUMBER,
    "intention": _STR,
    "ear": _NUMBER + _NONE,
    "ear_threshold": _NUMBER + _NONE,
    "previous_state": _STR + _NONE,
    "state": _STR,
    "state_changed": _BOOL,
    "actions": _LIST,
    "inference_latency_ms": _NUMBER,
    "control_latency_ms": _NUMBER,
    "end_to_end_latency_ms": _NUMBER,
}

ACTION_FIELDS: dict[str, tuple[type, ...]] = {
    "action": _STR,
    "success": _BOOL,
    "failure_reason": _STR + _NONE,
    "latency_ms": _NUMBER,
}

RUN_END_FIELDS: dict[str, tuple[type, ...]] = {
    **_COMMON_FIELDS,
    "status": _STR,
    "frame_count": _INT,
    "error_type": _STR + _NONE,
}

RECORD_FIELDS: dict[str, dict[str, tuple[type, ...]]] = {
    "run_start": RUN_START_FIELDS,
    "frame": FRAME_FIELDS,
    "run_end": RUN_END_FIELDS,
}

_ENUM_VALUES: dict[str, frozenset[str]] = {
    "intention": frozenset(item.value for item in Intention),
    "state": frozenset(item.value for item in DrowsinessState),
    "previous_state": frozenset(item.value for item in DrowsinessState),
    "action": frozenset(item.value for item in Action),
    "status": frozenset(RUN_STATUSES),
}

_NON_NEGATIVE = frozenset(
    {"inference_latency_ms", "control_latency_ms", "end_to_end_latency_ms", "latency_ms"}
)
_DETECTOR_CONFIG_KEYS = frozenset(
    {"ear_threshold", "drowsy_seconds", "recovery_seconds", "source", "action_mode"}
)


def _check_type(value: Any, allowed: tuple[type, ...]) -> bool:
    # bool is a subclass of int, so it only matches when explicitly allowed.
    if isinstance(value, bool):
        return bool in allowed
    return isinstance(value, allowed)


def _check_fields(
    record: Mapping[str, Any], spec: Mapping[str, tuple[type, ...]], where: str
) -> list[str]:
    problems = []
    for name in sorted(set(spec) - set(record)):
        problems.append(f"{where}: missing field {name!r}")
    for name in sorted(set(record) - set(spec)):
        problems.append(f"{where}: unexpected field {name!r}")
    for name, allowed in spec.items():
        if name not in record:
            continue
        value = record[name]
        if not _check_type(value, allowed):
            expected = ", ".join(kind.__name__ for kind in allowed)
            problems.append(f"{where}: field {name!r} must be {expected}, got {value!r}")
        elif isinstance(value, float) and not math.isfinite(value):
            problems.append(f"{where}: field {name!r} must be finite, got {value!r}")
        elif name in _ENUM_VALUES and value is not None and value not in _ENUM_VALUES[name]:
            problems.append(f"{where}: field {name!r} has unknown value {value!r}")
        elif name in _NON_NEGATIVE and value < 0:
            problems.append(f"{where}: field {name!r} must be non-negative, got {value!r}")
    return problems


def validate_record(record: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` describing every schema violation in one log record."""
    record_type = record.get("record_type")
    spec = RECORD_FIELDS.get(record_type) if isinstance(record_type, str) else None
    if spec is None:
        raise ValueError(f"unknown record_type {record_type!r}")

    problems = _check_fields(record, spec, record_type)
    version = record.get("schema_version")
    if version != SCHEMA_VERSION:
        problems.append(f"{record_type}: unsupported schema_version {version!r}")
    if record_type == "frame" and isinstance(record.get("actions"), list):
        for index, action in enumerate(record["actions"]):
            where = f"frame.actions[{index}]"
            if not isinstance(action, dict):
                problems.append(f"{where}: must be an object")
                continue
            problems.extend(_check_fields(action, ACTION_FIELDS, where))
            if isinstance(action, dict):
                success = action.get("success")
                reason = action.get("failure_reason")
                if success is True and reason is not None:
                    problems.append(f"{where}: successful action must not have failure_reason")
                if success is False and (not isinstance(reason, str) or not reason.strip()):
                    problems.append(f"{where}: failed action requires failure_reason")
    if record_type == "run_start" and isinstance(record.get("detector_config"), dict):
        config = record["detector_config"]
        unknown = sorted(set(config) - _DETECTOR_CONFIG_KEYS)
        if unknown:
            problems.append(f"run_start: unsupported detector_config keys {unknown!r}")
        for key, value in config.items():
            if not isinstance(value, (str, int, float, bool)) or isinstance(value, complex):
                problems.append(f"run_start: detector_config[{key!r}] must be scalar")
            elif isinstance(value, str) and redact(value) != value:
                problems.append(f"run_start: detector_config[{key!r}] contains sensitive data")
    if problems:
        raise ValueError("; ".join(problems))
