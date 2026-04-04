"""Runtime health diagnostics.

GET /diagnostics            — system fingerprint (OS, Python, SQLite, disk, CPU)
GET /diagnostics/startup-checks — pre-flight checks for minimum requirements
"""
from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import sys

from fastapi import APIRouter

router = APIRouter(prefix="/diagnostics", tags=["health"])


@router.get("")
async def runtime_fingerprint() -> dict:
    """Return a JSON fingerprint of the host runtime environment."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "sqlite_version": sqlite3.sqlite_version,
        "disk_free_gb": round(shutil.disk_usage("/").free / (1024**3), 2),
        "cpu_count": os.cpu_count(),
    }


@router.get("/startup-checks")
async def startup_checks() -> dict:
    """Run pre-flight checks and return pass/fail for each."""
    checks: dict[str, bool] = {}
    checks["python"] = sys.version_info >= (3, 11)
    checks["sqlite"] = (
        tuple(int(x) for x in sqlite3.sqlite_version.split(".")) >= (3, 35)
    )
    checks["disk_space"] = shutil.disk_usage("/").free > 1024**3
    if platform.system() == "Linux":
        checks["bubblewrap"] = shutil.which("bwrap") is not None
    return {"all_ok": all(checks.values()), "checks": checks}
