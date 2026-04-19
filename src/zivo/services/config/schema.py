"""Validation helpers for config file sections and fields."""

from __future__ import annotations


def validate_section_dict(
    section: object,
    section_name: str,
    warnings: list[str],
) -> dict[str, object] | None:
    """Return the section if it is a dict, otherwise None (with optional warning)."""

    if section is None:
        return None
    if not isinstance(section, dict):
        warnings.append(f"{section_name} must be a table; using defaults.")
        return None
    return section


def read_bool(
    section: dict[str, object],
    *,
    key: str,
    default: bool,
    warnings: list[str],
    section_name: str,
) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if key in section:
        warnings.append(f"{section_name}.{key} must be true or false; using default.")
    return default


def read_int(
    section: dict[str, object],
    *,
    key: str,
    default: int,
    minimum: int = 0,
    valid_values: frozenset[int] | None = None,
    warnings: list[str],
    section_name: str,
) -> int:
    value = section.get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        if valid_values is not None:
            if value in valid_values:
                return value
            if key in section:
                valid_display = ", ".join(str(item) for item in sorted(valid_values))
                warnings.append(
                    f"{section_name}.{key} must be one of {valid_display}; using default."
                )
            return default
        if value >= minimum:
            return value
        if key in section:
            warnings.append(f"{section_name}.{key} must be >= {minimum}; using default.")
        return default
    if key in section:
        warnings.append(f"{section_name}.{key} must be an integer; using default.")
    return default


def read_enum(
    section: dict[str, object],
    *,
    key: str,
    default: str,
    valid_values: frozenset[str],
    valid_display: str,
    section_name: str,
    warnings: list[str],
) -> str:
    value = section.get(key, default)
    if isinstance(value, str) and value in valid_values:
        return value
    if key in section:
        warnings.append(f"{section_name}.{key} must be one of {valid_display}; using default.")
    return default
