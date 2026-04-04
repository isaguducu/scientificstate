"""Tests for monitoring/alerts endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_alerts_endpoint_returns_structure(client):
    """GET /monitoring/alerts returns valid alert structure."""
    resp = await client.get("/monitoring/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "count" in data
    assert "checked_at" in data
    assert isinstance(data["alerts"], list)
    assert isinstance(data["count"], int)
    assert data["count"] == len(data["alerts"])


@pytest.mark.asyncio
async def test_alerts_recent_restart(client):
    """Recent restart alert fires when uptime < 5 min (always true in tests)."""
    resp = await client.get("/monitoring/alerts")
    data = resp.json()
    # In test environment, daemon just started → recent_restart should fire
    types = [a["type"] for a in data["alerts"]]
    assert "recent_restart" in types


@pytest.mark.asyncio
async def test_alerts_severity_values(client):
    """All alerts have valid severity levels."""
    resp = await client.get("/monitoring/alerts")
    data = resp.json()
    valid_severities = {"critical", "warning", "info"}
    for alert in data["alerts"]:
        assert alert["severity"] in valid_severities
        assert "type" in alert
        assert "message" in alert
