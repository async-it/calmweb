"""Low-level custom.cfg parsing and writing helpers.

Each function does one clear thing so it can be tested independently.
"""

from __future__ import annotations

import os
from enum import StrEnum

from .log import log


class CfgSection(StrEnum):
    """Known section headers in custom.cfg."""

    BLOCK = "BLOCK"
    WHITELIST = "WHITELIST"
    OPTIONS = "OPTIONS"


# Lookup set for fast membership tests
_SECTIONS = frozenset(CfgSection)


# -------------------------------------------------------------------
# Parsing helpers
# -------------------------------------------------------------------


def _normalize_domain(raw: str) -> str:
    """Strip leading dots, lowercase, and strip whitespace."""
    return raw.strip().lower().lstrip(".")


def _parse_section_line(line: str) -> tuple[CfgSection | None, str | None]:
    """Decide whether *line* is a section header or a data value.

    Returns ``(new_section, None)`` when the line is a header like
    ``[BLOCK]``, or ``(None, value)`` when it is a regular data line.
    """
    stripped = line.strip()
    up = stripped.upper()
    # Check for known section headers
    if up.startswith("[") and up.endswith("]"):
        name = up[1:-1]
        if name in _SECTIONS:
            return CfgSection(name), None
    # Not a header -- return current section unchanged and the raw value
    return None, stripped


def _parse_option_line(line: str) -> tuple[str, bool] | None:
    """Parse a ``key = value`` option line.

    Returns ``(key, enabled)`` or ``None`` when the line is malformed.
    """
    if "=" not in line:
        return None
    try:
        key, val = line.split("=", 1)
        key = key.strip().lower()
        val = val.strip().lower()
        enabled = val in ("1", "true", "yes", "on")
        return key, enabled
    except Exception:
        return None


def parse_cfg_file(path: str) -> tuple[set[str], set[str], dict[str, bool]]:
    """Parse a custom.cfg file at *path*.

    Returns ``(blocked_domains, whitelist_domains, options_dict)``.
    Tolerant to malformed lines; never raises.
    """
    blocked: set[str] = set()
    whitelist: set[str] = set()
    options: dict[str, bool] = {}

    if not os.path.exists(path):
        log(f"custom.cfg not found at {path}")
        return blocked, whitelist, options

    section: CfgSection | None = None
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                try:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue

                    new_section, value = _parse_section_line(line)
                    if new_section is not None:
                        section = new_section
                        continue

                    # value is the stripped line content
                    if section is CfgSection.BLOCK:
                        blocked.add(_normalize_domain(value))
                    elif section is CfgSection.WHITELIST:
                        whitelist.add(_normalize_domain(value))
                    elif section is CfgSection.OPTIONS:
                        parsed = _parse_option_line(value)
                        if parsed is not None:
                            options[parsed[0]] = parsed[1]
                    else:
                        # Lines before any section header go to blocked
                        blocked.add(_normalize_domain(value))
                except Exception:
                    # Skip problematic line
                    continue
    except Exception as e:
        log(f"Error reading custom.cfg {path}: {e}")

    return blocked, whitelist, options


# -------------------------------------------------------------------
# Writing helper
# -------------------------------------------------------------------


def write_cfg_file(
    path: str,
    blocked_set: set[str],
    whitelist_set: set[str],
    options: dict[str, bool],
) -> None:
    """Write a complete custom.cfg file with BLOCK, WHITELIST, and OPTIONS sections.

    Never raises; logs errors instead.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            # --- BLOCK section ---
            f.write(f"[{CfgSection.BLOCK}]\n")
            for d in sorted(blocked_set):
                f.write(f"{d}\n")

            # --- WHITELIST section ---
            f.write(f"\n[{CfgSection.WHITELIST}]\n")
            for d in sorted(whitelist_set):
                f.write(f"{d}\n")

            # --- OPTIONS section ---
            f.write(f"\n[{CfgSection.OPTIONS}]\n")
            for key in sorted(options):
                f.write(f"{key} = {'1' if options[key] else '0'}\n")

        log(f"Fichier de configuration créé: {path}")
    except Exception as e:
        log(f"Erreur de création du fichier de configuration {path}: {e}")
