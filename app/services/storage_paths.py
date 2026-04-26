from __future__ import annotations

from pathlib import Path


INVALID_STORAGE_CHARS = '<>:"/\\|?*'


def validate_storage_id(value: str, label: str = "storage id") -> str:
    storage_id = str(value)
    if not storage_id:
        raise ValueError(f"{label} must not be empty.")
    if storage_id != storage_id.strip():
        raise ValueError(f"{label} must not have leading or trailing whitespace.")
    if storage_id in {".", ".."}:
        raise ValueError(f"{label} must not be a dot path segment.")
    if any(char in INVALID_STORAGE_CHARS for char in storage_id):
        raise ValueError(f"{label} contains a path separator or invalid filename character.")
    if any(ord(char) < 32 for char in storage_id):
        raise ValueError(f"{label} contains a control character.")
    return storage_id


def safe_child(root: Path, *parts: str) -> Path:
    root_path = root.resolve()
    current = root_path
    for index, part in enumerate(parts, start=1):
        current = current / validate_storage_id(part, f"path segment {index}")

    resolved = current.resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"Resolved path escapes storage root: {resolved}") from exc
    return resolved
