"""Shared test fixtures for materials science domain tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure Core/framework is importable
_FRAMEWORK_PATH = str(Path(__file__).parents[2] / ".." / "Core" / "framework")
if _FRAMEWORK_PATH not in sys.path:
    sys.path.insert(0, _FRAMEWORK_PATH)
