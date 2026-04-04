"""Tests for monitoring endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_monitoring_health(client):
    resp = await client.get("/monitoring/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert "database" in data
    assert "disk_free_gb" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["disk_free_gb"], (int, float))


@pytest.mark.asyncio
async def test_monitoring_metrics(client):
    resp = await client.get("/monitoring/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "daemon_uptime_seconds" in data
    assert "daemon_db_size_bytes" in data
    assert "daemon_request_count" in data
    assert "daemon_error_count" in data
    assert isinstance(data["daemon_db_size_bytes"], int)
    assert isinstance(data["daemon_request_count"], int)
    assert isinstance(data["daemon_error_count"], int)


@pytest.mark.asyncio
async def test_monitoring_version(client):
    resp = await client.get("/monitoring/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.5.0"
    assert data["phase"] == "Phase 5"
    assert "python_version" in data
    assert "pid" in data


@pytest.mark.asyncio
async def test_monitoring_metrics_counts_requests(client):
    """Metrics endpoint tracks request count."""
    # Get initial count
    resp1 = await client.get("/monitoring/metrics")
    initial_count = resp1.json()["daemon_request_count"]

    # Make some requests
    await client.get("/monitoring/health")
    await client.get("/monitoring/version")

    # Count should have increased
    resp2 = await client.get("/monitoring/metrics")
    new_count = resp2.json()["daemon_request_count"]
    assert new_count > initial_count
