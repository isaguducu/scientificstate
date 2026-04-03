"""
Auto-detect compatible domain modules for a given file.

Constitutional constraint (P7 — Non-delegation of scientific authority):
  This function ONLY suggests — it never installs or executes anything.
  The researcher must explicitly choose the domain and method.
"""
from __future__ import annotations

import json
from pathlib import Path

_FORMAT_MAP_PATH = Path(__file__).parent / "format_map.json"


def _load_format_map() -> dict[str, list[str]]:
    """Load extension → domain mapping from format_map.json."""
    if _FORMAT_MAP_PATH.exists():
        with open(_FORMAT_MAP_PATH) as f:
            return json.load(f)
    return {}


def suggest_domains(file_path: str) -> dict:
    """Suggest compatible domain modules for a file based on its extension.

    Does NOT install or execute anything — suggestion only (P7).

    Args:
        file_path: absolute or relative path to the file to analyze.

    Returns:
        {
            "suggested_domains": ["polymer_science", ...],
            "confidence": "high" | "medium" | "low"
        }
    """
    ext = Path(file_path).suffix.lstrip(".").lower()
    format_map = _load_format_map()

    domains = format_map.get(ext, [])

    if len(domains) == 1:
        confidence = "high"
    elif len(domains) > 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "suggested_domains": domains,
        "confidence": confidence,
    }
