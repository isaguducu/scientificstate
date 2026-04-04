"""Tests for GET /diagnostics and GET /diagnostics/startup-checks."""
from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_diagnostics_fingerprint(client):
    """GET /diagnostics returns a complete runtime fingerprint."""
    resp = await client.get("/diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "os",
        "os_version",
        "os_release",
        "architecture",
        "python_version",
        "sqlite_version",
        "disk_free_gb",
        "cpu_count",
    ):
        assert key in body, f"Missing key: {key}"
    assert isinstance(body["disk_free_gb"], (int, float))
    assert isinstance(body["cpu_count"], int)


@pytest.mark.anyio
async def test_diagnostics_startup_checks(client):
    """GET /diagnostics/startup-checks returns all_ok + checks dict."""
    resp = await client.get("/diagnostics/startup-checks")
    assert resp.status_code == 200
    body = resp.json()
    assert "all_ok" in body
    assert "checks" in body
    assert isinstance(body["all_ok"], bool)
    checks = body["checks"]
    assert "python" in checks
    assert "sqlite" in checks
    assert "disk_space" in checks


@pytest.mark.anyio
async def test_diagnostics_startup_checks_all_ok(client):
    """Verify all_ok is consistent with individual check results."""
    resp = await client.get("/diagnostics/startup-checks")
    body = resp.json()
    expected_ok = all(body["checks"].values())
    assert body["all_ok"] == expected_ok
