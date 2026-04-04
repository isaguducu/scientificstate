"""Monitoring endpoints — health, metrics, version, alerts.

GET /monitoring/health   — detailed health check (uptime, DB, disk)
GET /monitoring/metrics  — Prometheus-compatible metric counters
GET /monitoring/version  — daemon version + build info
GET /monitoring/alerts   — active alerts (disk, DB size, recent restart)

Includes request-counting middleware that tracks total requests and errors.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.storage.schema import get_db_path

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_START_TIME = time.time()

# Thread-safe counters for request/error tracking
_request_count = 0
_error_count = 0
_counter_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Middleware — request/error counter
# ---------------------------------------------------------------------------


class MetricsMiddleware(BaseHTTPMiddleware):
    """Counts total requests and error responses (4xx/5xx)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        global _request_count, _error_count  # noqa: PLW0603
        response: Response = await call_next(request)
        with _counter_lock:
            _request_count += 1
            if response.status_code >= 400:
                _error_count += 1
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_db() -> bool:
    """Return True if the daemon database file exists and is readable."""
    db_path = get_db_path()
    return db_path.exists() and db_path.stat().st_size > 0


def _get_db_size() -> int:
    """Return the daemon database file size in bytes (0 if missing)."""
    db_path = get_db_path()
    if db_path.exists():
        return db_path.stat().st_size
    return 0


# ---------------------------------------------------------------------------
# GET /monitoring/health
# ---------------------------------------------------------------------------


@router.get("/health")
async def detailed_health() -> dict:
    """Detailed health check."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "database": _check_db(),
        "disk_free_gb": round(shutil.disk_usage("/").free / (1024**3), 2),
    }


# ---------------------------------------------------------------------------
# GET /monitoring/metrics
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def prometheus_metrics() -> dict:
    """Prometheus-compatible metrics."""
    with _counter_lock:
        req_count = _request_count
        err_count = _error_count
    return {
        "daemon_uptime_seconds": round(time.time() - _START_TIME, 2),
        "daemon_request_count": req_count,
        "daemon_error_count": err_count,
        "daemon_db_size_bytes": _get_db_size(),
    }


# ---------------------------------------------------------------------------
# GET /monitoring/version
# ---------------------------------------------------------------------------


@router.get("/version")
async def version_info() -> dict:
    """Daemon version + build info."""
    return {
        "version": "0.5.0",
        "phase": "Phase 5",
        "python_version": sys.version,
        "pid": os.getpid(),
    }


# ---------------------------------------------------------------------------
# GET /monitoring/alerts
# ---------------------------------------------------------------------------

_DISK_LOW_THRESHOLD = 1_073_741_824  # 1 GB
_DB_LARGE_THRESHOLD = 524_288_000  # 500 MB
_RECENT_RESTART_SECONDS = 300  # 5 min


@router.get("/alerts")
async def alerts() -> dict:
    """Active alerts — disk, DB size, recent restart."""
    alert_list: list[dict] = []

    # Disk check
    disk = shutil.disk_usage("/")
    if disk.free < _DISK_LOW_THRESHOLD:
        alert_list.append({
            "severity": "critical",
            "type": "disk_low",
            "message": f"Disk space low: {disk.free // 1_048_576}MB free",
        })

    # DB size check
    db_path = get_db_path()
    if db_path.exists() and db_path.stat().st_size > _DB_LARGE_THRESHOLD:
        alert_list.append({
            "severity": "warning",
            "type": "db_large",
            "message": f"Database large: {db_path.stat().st_size // 1_048_576}MB",
        })

    # Recent restart check
    uptime = time.time() - _START_TIME
    if uptime < _RECENT_RESTART_SECONDS:
        alert_list.append({
            "severity": "info",
            "type": "recent_restart",
            "message": f"Recent restart: {int(uptime)}s ago",
        })

    return {
        "alerts": alert_list,
        "count": len(alert_list),
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
