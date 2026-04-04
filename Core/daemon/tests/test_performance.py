"""Tests for GET /monitoring/performance — response time, throughput, error rate."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_performance_endpoint_exists(client: TestClient):
    """Endpoint returns 200 with valid JSON."""
    resp = client.get("/monitoring/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "response_time" in data
    assert "throughput" in data
    assert "error_rate" in data
    assert "uptime_seconds" in data


def test_performance_response_shape(client: TestClient):
    """Response has the expected nested structure."""
    data = client.get("/monitoring/performance").json()

    rt = data["response_time"]
    assert "p50_ms" in rt
    assert "p95_ms" in rt
    assert "p99_ms" in rt

    tp = data["throughput"]
    assert "requests_per_second" in tp
    assert "total_requests" in tp

    er = data["error_rate"]
    assert "last_hour" in er
    assert "last_24h" in er


def test_performance_values_are_numeric(client: TestClient):
    """All performance metric values are numeric (int or float)."""
    data = client.get("/monitoring/performance").json()

    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0

    for k in ["p50_ms", "p95_ms", "p99_ms"]:
        assert isinstance(data["response_time"][k], (int, float))
        assert data["response_time"][k] >= 0

    for k in ["requests_per_second", "total_requests"]:
        assert isinstance(data["throughput"][k], (int, float))
        assert data["throughput"][k] >= 0

    for k in ["last_hour", "last_24h"]:
        assert isinstance(data["error_rate"][k], (int, float))
        assert 0 <= data["error_rate"][k] <= 1.0


def test_performance_uptime_positive(client: TestClient):
    """Uptime should be positive (daemon has been running)."""
    data = client.get("/monitoring/performance").json()
    assert data["uptime_seconds"] > 0


def test_existing_alerting_not_broken(client: TestClient):
    """Existing monitoring endpoints still work after performance addition."""
    assert client.get("/monitoring/health").status_code == 200
    assert client.get("/monitoring/metrics").status_code == 200
    assert client.get("/monitoring/version").status_code == 200
    assert client.get("/monitoring/alerts").status_code == 200
