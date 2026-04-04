"""Air-gapped registry endpoint tests — export + import via TestClient."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest


def _generate_manifest(export_dir: Path) -> None:
    """Generate MANIFEST.sha256 for an export directory."""
    lines = []
    for fpath in sorted(export_dir.rglob("*")):
        if fpath.is_file() and fpath.name != "MANIFEST.sha256":
            h = hashlib.sha256(fpath.read_bytes()).hexdigest()
            rel = fpath.relative_to(export_dir)
            lines.append(f"{h}  {rel}")
    (export_dir / "MANIFEST.sha256").write_text("\n".join(lines), encoding="utf-8")


# ── Export endpoint ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_export_creates_snapshot(client):
    """POST /registry/export creates export directory structure."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = str(Path(tmp) / "export")
        resp = await client.post(
            "/registry/export",
            json={"output_dir": output_dir},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["output_dir"] == output_dir

        # Verify directory structure
        output = Path(output_dir)
        assert output.exists()
        assert (output / "registry").exists()
        assert (output / "tuf").exists()
        assert (output / "trust").exists()
        assert (output / "packages").exists()

        # Verify index was written
        index_path = output / "registry" / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert "packages" in index
        assert "exported_at" in index


@pytest.mark.anyio
async def test_export_returns_path(client):
    """POST /registry/export response includes output_dir."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = str(Path(tmp) / "test-export")
        resp = await client.post(
            "/registry/export",
            json={"output_dir": output_dir},
        )
        assert resp.status_code == 200
        assert resp.json()["output_dir"] == output_dir


# ── Import endpoint ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_import_from_export(client):
    """POST /registry/import reads from an export directory."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create minimal export structure
        export_dir = Path(tmp) / "export"
        for subdir in ("registry", "tuf", "trust", "packages"):
            (export_dir / subdir).mkdir(parents=True)

        (export_dir / "registry" / "index.json").write_text(
            '{"packages":[]}', encoding="utf-8"
        )
        (export_dir / "tuf" / "root.json").write_text("{}", encoding="utf-8")

        # Generate MANIFEST.sha256 (mandatory for import since Phase 4)
        _generate_manifest(export_dir)

        resp = await client.post(
            "/registry/import",
            json={"input_dir": str(export_dir)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "registry_dir" in data


@pytest.mark.anyio
async def test_import_without_manifest(client):
    """POST /registry/import without MANIFEST.sha256 → 400."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp) / "no-manifest"
        export_dir.mkdir()
        (export_dir / "registry").mkdir()
        (export_dir / "registry" / "index.json").write_text("{}", encoding="utf-8")

        resp = await client.post(
            "/registry/import",
            json={"input_dir": str(export_dir)},
        )
        assert resp.status_code == 400
        assert "MANIFEST.sha256" in resp.json()["detail"]


@pytest.mark.anyio
async def test_import_not_found(client):
    """POST /registry/import with non-existent dir → 404."""
    resp = await client.post(
        "/registry/import",
        json={"input_dir": "/nonexistent/path/to/export"},
    )
    assert resp.status_code == 404


# ── Round-trip ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_export_import_round_trip(client):
    """Export → Import round-trip preserves structure."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = str(Path(tmp) / "round-trip-export")

        # Export
        resp = await client.post(
            "/registry/export",
            json={"output_dir": export_dir},
        )
        assert resp.status_code == 200

        # Import
        resp = await client.post(
            "/registry/import",
            json={"input_dir": export_dir},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"


# ── Existing endpoints unaffected ────────────────────────────────────────────


@pytest.mark.anyio
async def test_existing_mirrors_still_works(client):
    """GET /registry/mirrors still returns 200 after air-gapped additions."""
    resp = await client.get("/registry/mirrors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_existing_status_still_works(client):
    """GET /registry/status still returns 200 after air-gapped additions."""
    resp = await client.get("/registry/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "protocol_endpoints" in data
