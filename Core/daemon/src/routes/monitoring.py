"""Monitoring endpoints — health, metrics, version, alerts, performance.

GET /monitoring/health      — detailed health check (uptime, DB, disk)
GET /monitoring/metrics     — Prometheus-compatible metric counters
GET /monitoring/version     — daemon version + build info
GET /monitoring/alerts      — active alerts (disk, DB size, recent restart)
GET /monitoring/performance — response time percentiles, throughput, error rate

Includes request-counting middleware that tracks total requests and errors.
"""
from __future__ import annotations

import collections
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

# Response time tracking (ring buffer of recent response times)
_MAX_SAMPLES = 10_000
_response_times: collections.deque[float] = collections.deque(maxlen=_MAX_SAMPLES)
_error_timestamps: collections.deque[float] = collections.deque(maxlen=_MAX_SAMPLES)


# ---------------------------------------------------------------------------
# Middleware — request/error counter
# ---------------------------------------------------------------------------


class MetricsMiddleware(BaseHTTPMiddleware):
    """Counts total requests, error responses (4xx/5xx), and response times."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        global _request_count, _error_count  # noqa: PLW0603
        start = time.time()
        response: Response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000
        with _counter_lock:
            _request_count += 1
            _response_times.append(elapsed_ms)
            if response.status_code >= 400:
                _error_count += 1
                _error_timestamps.append(time.time())
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


# ---------------------------------------------------------------------------
# GET /monitoring/performance
# ---------------------------------------------------------------------------


def _percentile(samples: list[float], pct: int) -> float:
    """Return the given percentile from a sorted list of samples."""
    if not samples:
        return 0.0
    k = (len(samples) - 1) * pct / 100
    f = int(k)
    c = f + 1 if f + 1 < len(samples) else f
    return round(samples[f] + (k - f) * (samples[c] - samples[f]), 2)


@router.get("/performance")
async def performance_metrics() -> dict:
    """Performance metrics: response time percentiles, throughput, error rate."""
    now = time.time()
    uptime = now - _START_TIME

    with _counter_lock:
        sorted_times = sorted(_response_times)
        req_count = _request_count
        # Error timestamps for windowed rates
        errors_1h = sum(1 for t in _error_timestamps if now - t < 3600)
        errors_24h = sum(1 for t in _error_timestamps if now - t < 86400)
        total_1h = max(req_count, 1)  # avoid division by zero
        total_24h = max(req_count, 1)

    rps = round(req_count / uptime, 2) if uptime > 0 else 0.0
    err_rate_1h = round(errors_1h / total_1h, 4)
    err_rate_24h = round(errors_24h / total_24h, 4)

    return {
        "response_time": {
            "p50_ms": _percentile(sorted_times, 50),
            "p95_ms": _percentile(sorted_times, 95),
            "p99_ms": _percentile(sorted_times, 99),
        },
        "throughput": {
            "requests_per_second": rps,
            "total_requests": req_count,
        },
        "error_rate": {
            "last_hour": err_rate_1h,
            "last_24h": err_rate_24h,
        },
        "uptime_seconds": round(uptime, 2),
    }
