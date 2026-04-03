"""Tests for new /modules endpoints (Phase 1 extensions)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_search_returns_list(client):
    """GET /modules/search?q=polymer → 200 + list."""
    resp = await client.get("/modules/search", params={"q": "polymer"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_search_no_query_returns_all(client):
    """GET /modules/search without query → 200 + list (all installed)."""
    resp = await client.get("/modules/search")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_suggest_csv_returns_polymer(client):
    """POST /modules/suggest with .csv → suggested_domains list."""
    resp = await client.post("/modules/suggest", json={"file_path": "/data/sample.csv"})
    assert resp.status_code == 200
    body = resp.json()
    assert "suggested_domains" in body
    assert "polymer_science" in body["suggested_domains"]
    assert body["confidence"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_suggest_unknown_ext(client):
    """POST /modules/suggest with unknown extension → empty list + low confidence."""
    resp = await client.post("/modules/suggest", json={"file_path": "/data/mystery.xyz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_domains"] == []
    assert body["confidence"] == "low"


@pytest.mark.asyncio
async def test_package_bad_path_returns_400(client):
    """POST /modules/package with non-existent path → 400."""
    resp = await client.post("/modules/package", json={"source_path": "/nonexistent/path"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_package_with_valid_dir(client, tmp_path):
    """POST /modules/package with valid dir → tarball_path + hash."""
    # Create a minimal module dir with manifest.json
    import json
    manifest = {"domain_id": "test_mod", "version": "0.1.0"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    resp = await client.post("/modules/package", json={"source_path": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert "tarball_path" in body
    assert body["tarball_hash"].startswith("sha256-")
    assert "manifest_path" in body


@pytest.mark.asyncio
async def test_revoke_returns_success(client):
    """POST /modules/revoke → 200 + success."""
    resp = await client.post("/modules/revoke", json={
        "domain_id": "test_domain",
        "version": "1.0.0",
        "reason": "Security vulnerability CVE-2026-0001",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["domain_id"] == "test_domain"
    assert body["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_check_updates_returns_list(client):
    """GET /modules/check-updates → 200 + list."""
    resp = await client.get("/modules/check-updates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_update_not_installed_returns_404(client):
    """POST /modules/update for non-installed module → 404."""
    resp = await client.post("/modules/update", json={"domain_id": "nonexistent"})
    assert resp.status_code == 404
