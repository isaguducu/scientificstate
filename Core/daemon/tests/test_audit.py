"""Tests for audit log endpoints — 15 tests.

Tests INSERT-only audit log: valid entries, invalid action/resource_type
rejection, timestamp generation, query filters, and actions listing.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Patch DB path before importing audit module
_tmp = tempfile.mkdtemp()
_test_db = Path(_tmp) / "test_audit.db"


def _mock_db_path() -> Path:
    _test_db.parent.mkdir(parents=True, exist_ok=True)
    return _test_db


# Patch at module level before import
with patch("src.storage.schema.get_db_path", _mock_db_path):
    with patch("src.routes.audit.get_db_path", _mock_db_path):
        from src.routes.audit import router, VALID_ACTIONS, VALID_RESOURCE_TYPES

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db():
    """Reset DB for each test."""
    if _test_db.exists():
        _test_db.unlink()
    yield
    if _test_db.exists():
        _test_db.unlink()


# ---------------------------------------------------------------------------
# POST /audit/log — append entries
# ---------------------------------------------------------------------------


def test_append_claim_create():
    """Append a claim.create audit entry."""
    resp = client.post("/audit/log", json={
        "actor_id": "user-1",
        "actor_type": "user",
        "action": "claim.create",
        "resource_type": "claim",
        "resource_id": "claim-abc",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["action"] == "claim.create"
    assert data["resource_type"] == "claim"
    assert "id" in data
    assert "created_at" in data


def test_append_auth_login():
    """Append an auth.login audit entry."""
    resp = client.post("/audit/log", json={
        "actor_id": "user-2",
        "actor_type": "user",
        "action": "auth.login",
        "resource_type": "session",
    })
    assert resp.status_code == 201
    assert resp.json()["action"] == "auth.login"


def test_append_gdpr_export_request():
    """Append a gdpr.export_request audit entry."""
    resp = client.post("/audit/log", json={
        "actor_id": "user-3",
        "actor_type": "user",
        "action": "gdpr.export_request",
        "resource_type": "gdpr_request",
        "resource_id": "gdpr-req-1",
    })
    assert resp.status_code == 201
    assert resp.json()["action"] == "gdpr.export_request"


def test_append_federation_sync_pull():
    """Append a federation.sync_pull audit entry."""
    resp = client.post("/audit/log", json={
        "actor_type": "federation",
        "action": "federation.sync_pull",
        "resource_type": "federation_sync",
        "metadata": {"source": "remote-node-1"},
    })
    assert resp.status_code == 201
    assert resp.json()["action"] == "federation.sync_pull"


def test_append_system_action():
    """Append an entry with system actor_type."""
    resp = client.post("/audit/log", json={
        "actor_type": "system",
        "action": "run.create",
        "resource_type": "compute_run",
        "resource_id": "run-xyz",
    })
    assert resp.status_code == 201
    assert resp.json()["action"] == "run.create"


# ---------------------------------------------------------------------------
# Validation — invalid action / resource_type
# ---------------------------------------------------------------------------


def test_invalid_action_rejected():
    """Invalid action returns 400."""
    resp = client.post("/audit/log", json={
        "action": "invalid.action",
        "resource_type": "claim",
    })
    assert resp.status_code == 400
    assert "Invalid action" in resp.json()["detail"]


def test_invalid_resource_type_rejected():
    """Invalid resource_type returns 400."""
    resp = client.post("/audit/log", json={
        "action": "claim.create",
        "resource_type": "invalid_type",
    })
    assert resp.status_code == 400
    assert "Invalid resource_type" in resp.json()["detail"]


def test_invalid_actor_type_rejected():
    """Invalid actor_type returns 400."""
    resp = client.post("/audit/log", json={
        "actor_type": "hacker",
        "action": "claim.create",
        "resource_type": "claim",
    })
    assert resp.status_code == 400
    assert "Invalid actor_type" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Timestamp auto-generated
# ---------------------------------------------------------------------------


def test_timestamp_auto_generated():
    """created_at is auto-generated on append."""
    resp = client.post("/audit/log", json={
        "action": "module.publish",
        "resource_type": "module",
        "resource_id": "mod-1",
    })
    assert resp.status_code == 201
    created_at = resp.json()["created_at"]
    assert "T" in created_at  # ISO 8601 format


# ---------------------------------------------------------------------------
# GET /audit/log — query
# ---------------------------------------------------------------------------


def test_query_all_entries():
    """Query returns all appended entries."""
    # Append 3 entries
    for action in ["claim.create", "auth.login", "run.create"]:
        resource_type = {
            "claim.create": "claim",
            "auth.login": "session",
            "run.create": "compute_run",
        }[action]
        client.post("/audit/log", json={
            "action": action,
            "resource_type": resource_type,
        })

    resp = client.get("/audit/log")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert len(data["entries"]) == 3


def test_query_by_action_filter():
    """Query with action filter returns only matching entries."""
    client.post("/audit/log", json={
        "action": "claim.create",
        "resource_type": "claim",
    })
    client.post("/audit/log", json={
        "action": "auth.login",
        "resource_type": "session",
    })

    resp = client.get("/audit/log", params={"action": "claim.create"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["entries"][0]["action"] == "claim.create"


def test_query_by_resource_type_filter():
    """Query with resource_type filter returns only matching entries."""
    client.post("/audit/log", json={
        "action": "claim.create",
        "resource_type": "claim",
    })
    client.post("/audit/log", json={
        "action": "run.create",
        "resource_type": "compute_run",
    })

    resp = client.get("/audit/log", params={"resource_type": "compute_run"})
    data = resp.json()
    assert data["count"] == 1
    assert data["entries"][0]["resource_type"] == "compute_run"


def test_query_with_limit():
    """Query with limit returns at most N entries."""
    for i in range(5):
        client.post("/audit/log", json={
            "action": "claim.create",
            "resource_type": "claim",
            "resource_id": f"claim-{i}",
        })

    resp = client.get("/audit/log", params={"limit": 2})
    data = resp.json()
    assert data["count"] == 2
    assert len(data["entries"]) == 2


def test_query_cursor_pagination():
    """Cursor pagination skips entries after cursor timestamp."""
    # Create entries
    ids = []
    for i in range(3):
        r = client.post("/audit/log", json={
            "action": "claim.create",
            "resource_type": "claim",
            "resource_id": f"claim-{i}",
        })
        ids.append(r.json())

    # Get first page
    resp1 = client.get("/audit/log", params={"limit": 2})
    data1 = resp1.json()
    assert data1["count"] == 2
    cursor = data1["next_cursor"]

    # Get second page using cursor
    resp2 = client.get("/audit/log", params={"limit": 2, "cursor": cursor})
    data2 = resp2.json()
    assert data2["count"] == 1


# ---------------------------------------------------------------------------
# GET /audit/log/actions — list valid types
# ---------------------------------------------------------------------------


def test_list_actions_endpoint():
    """List actions returns all valid action types."""
    resp = client.get("/audit/log/actions")
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert "resource_types" in data
    assert "actor_types" in data
    assert "claim.create" in data["actions"]
    assert "claim" in data["resource_types"]
    assert "user" in data["actor_types"]
    assert len(data["actions"]) == len(VALID_ACTIONS)
    assert len(data["resource_types"]) == len(VALID_RESOURCE_TYPES)
