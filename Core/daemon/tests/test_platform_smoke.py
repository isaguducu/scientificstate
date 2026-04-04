"""Platform smoke tests — cross-platform readiness checks.

Validates that the daemon runs correctly on the host platform:
health endpoint, metrics, runtime fingerprint, filesystem access,
and deterministic startup behavior.

Uses the shared conftest.py async client fixture (httpx + ASGITransport).
"""
from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200_and_healthy(client):
    """GET /monitoring/health returns 200 with status 'healthy'."""
    resp = await client.get("/monitoring/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_returns_200_with_required_fields(client):
    """GET /monitoring/metrics returns 200 with all required counters."""
    resp = await client.get("/monitoring/metrics")
    assert resp.status_code == 200
    data = resp.json()
    required = [
        "daemon_uptime_seconds",
        "daemon_request_count",
        "daemon_error_count",
        "daemon_db_size_bytes",
    ]
    for field in required:
        assert field in data, f"Missing required field: {field}"


# ---------------------------------------------------------------------------
# Runtime fingerprint (version endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_has_runtime_fields(client):
    """GET /monitoring/version returns version, python_version, pid."""
    resp = await client.get("/monitoring/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "python_version" in data
    assert "pid" in data
    assert isinstance(data["pid"], int)


def test_platform_os_is_known():
    """platform.system() returns one of Darwin, Linux, or Windows."""
    assert platform.system() in ("Darwin", "Linux", "Windows")


# ---------------------------------------------------------------------------
# Filesystem checks
# ---------------------------------------------------------------------------


def test_home_directory_exists():
    """The user home directory must exist on any supported platform."""
    home = Path.home()
    assert home.exists(), f"Home directory does not exist: {home}"
    assert home.is_dir(), f"Home path is not a directory: {home}"


def test_temp_directory_writable():
    """The system temp directory must be writable."""
    tmp_dir = Path(tempfile.gettempdir())
    assert tmp_dir.exists(), f"Temp directory does not exist: {tmp_dir}"

    # Write and read back a canary file
    canary = tmp_dir / "scientificstate_smoke_test.tmp"
    try:
        canary.write_text("smoke-test")
        assert canary.read_text() == "smoke-test"
    finally:
        canary.unlink(missing_ok=True)


def test_app_data_directory_creatable():
    """An app data directory can be created under the user home."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    app_dir = base / "scientificstate-smoke-test"
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        assert app_dir.exists()
        assert app_dir.is_dir()
    finally:
        app_dir.rmdir()


# ---------------------------------------------------------------------------
# Deterministic startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_health_response_structure(client):
    """Two consecutive health calls return the same response structure."""
    resp1 = await client.get("/monitoring/health")
    resp2 = await client.get("/monitoring/health")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    keys1 = set(resp1.json().keys())
    keys2 = set(resp2.json().keys())
    assert keys1 == keys2, f"Response keys differ: {keys1} vs {keys2}"


@pytest.mark.asyncio
async def test_deterministic_metrics_response_structure(client):
    """Two consecutive metrics calls return the same response structure."""
    resp1 = await client.get("/monitoring/metrics")
    resp2 = await client.get("/monitoring/metrics")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    keys1 = set(resp1.json().keys())
    keys2 = set(resp2.json().keys())
    assert keys1 == keys2, f"Response keys differ: {keys1} vs {keys2}"


# ---------------------------------------------------------------------------
# Performance endpoint (optional — warn if missing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alerts_endpoint_responds(client):
    """GET /monitoring/alerts should respond (alerts are an optional feature)."""
    resp = await client.get("/monitoring/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "count" in data
    assert isinstance(data["alerts"], list)
