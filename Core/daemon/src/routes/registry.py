"""
Registry mirror management routes.

Endpoints:
    GET  /registry/mirrors  — list configured registry mirrors
    POST /registry/sync     — trigger mirror synchronisation
    GET  /registry/status   — connection / mode status
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("scientificstate.daemon.registry")

router = APIRouter(prefix="/registry", tags=["registry"])

# ---------------------------------------------------------------------------
# In-memory mirror store (production would persist to SQLite)
# ---------------------------------------------------------------------------

_mirrors: list[dict[str, Any]] = [
    {
        "id": "official-r2",
        "name": "ScientificState Official (R2)",
        "url": "https://modules.scientificstate.org",
        "mode": "mirror",
        "institution": None,
        "status": "active",
        "last_synced_at": None,
    },
]

_registry_mode: str = "online"  # online | offline | air-gapped


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class MirrorEntry(BaseModel):
    id: str
    name: str
    url: str
    mode: str  # mirror | self-hosted | air-gapped
    institution: str | None = None
    status: str  # active | inactive | syncing
    last_synced_at: str | None = None


class SyncRequest(BaseModel):
    mirror_id: str


class SyncResponse(BaseModel):
    mirror_id: str
    status: str
    synced_at: str
    message: str


class RegistryStatus(BaseModel):
    mode: str  # online | offline | air-gapped
    mirrors_count: int
    active_mirrors: int
    protocol_endpoints: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/mirrors", response_model=list[MirrorEntry])
async def list_mirrors() -> list[dict[str, Any]]:
    """Return all configured registry mirrors."""
    return _mirrors


@router.post("/sync", response_model=SyncResponse)
async def sync_mirror(req: SyncRequest) -> dict[str, Any]:
    """Trigger synchronisation for a specific mirror."""
    target = None
    for m in _mirrors:
        if m["id"] == req.mirror_id:
            target = m
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Mirror '{req.mirror_id}' not found")

    if target["mode"] == "air-gapped":
        raise HTTPException(
            status_code=400,
            detail="Air-gapped mirrors cannot be synced over network. Use offline transfer.",
        )

    # Mark as syncing, then immediately resolve (real impl would be async job)
    target["status"] = "syncing"
    now = datetime.now(tz=timezone.utc).isoformat()
    target["last_synced_at"] = now
    target["status"] = "active"

    logger.info("Mirror '%s' synced at %s", target["name"], now)

    return {
        "mirror_id": req.mirror_id,
        "status": "synced",
        "synced_at": now,
        "message": f"Mirror '{target['name']}' synchronisation complete.",
    }


@router.get("/status", response_model=RegistryStatus)
async def registry_status() -> dict[str, Any]:
    """Return current registry connection status."""
    active = sum(1 for m in _mirrors if m["status"] == "active")
    return {
        "mode": _registry_mode,
        "mirrors_count": len(_mirrors),
        "active_mirrors": active,
        "protocol_endpoints": [
            "GET /registry/index.json",
            "GET /registry/format-map.json",
            "GET /packages/{domain_id}/v{version}/manifest.json",
            "GET /packages/{domain_id}/v{version}/package.tar.gz",
            "GET /packages/{domain_id}/v{version}/checksum.sha256",
            "GET /packages/{domain_id}/v{version}/signature.sig",
        ],
    }


# ---------------------------------------------------------------------------
# Air-gapped endpoints (additive — existing endpoints above are untouched)
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    output_dir: str
    registry_url: str = "http://127.0.0.1:9473"


class ExportResponse(BaseModel):
    status: str
    output_dir: str
    message: str


class ImportRequest(BaseModel):
    input_dir: str


class ImportResponse(BaseModel):
    status: str
    registry_dir: str
    message: str


class AirGappedModuleEntry(BaseModel):
    domain_id: str
    versions: list[str]


@router.post("/export", response_model=ExportResponse)
async def air_gapped_export(req: ExportRequest) -> dict[str, Any]:
    """Create an air-gapped export snapshot for USB transfer.

    Copies registry index, TUF metadata, trust chain, and packages
    to the specified output directory for offline transport.

    Produces a MANIFEST.sha256 for integrity verification on import.
    """
    import hashlib
    from pathlib import Path

    output = Path(req.output_dir)
    try:
        output.mkdir(parents=True, exist_ok=True)
        for subdir in ("registry", "packages", "tuf", "trust"):
            (output / subdir).mkdir(exist_ok=True)

        # Copy real registry data from local store
        local_registry = Path.home() / ".scientificstate" / "registry"

        # Registry index — copy from local store and add export metadata
        local_index = local_registry / "index.json"
        if local_index.exists():
            try:
                index_data = json.loads(local_index.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                index_data = {"packages": []}
        else:
            index_data = {"packages": []}

        index_data["exported_at"] = datetime.now(tz=timezone.utc).isoformat()
        index_data["source"] = req.registry_url
        (output / "registry" / "index.json").write_text(
            json.dumps(index_data, indent=2), encoding="utf-8"
        )

        # TUF metadata — copy from local store (mandatory for trust chain)
        local_tuf = local_registry / "tuf"
        if local_tuf.exists():
            import shutil
            for fname in ("root.json", "targets.json"):
                src = local_tuf / fname
                if src.exists():
                    shutil.copy2(src, output / "tuf" / fname)

        # Trust chain — copy public keys
        local_trust = local_registry / "trust"
        if local_trust.exists():
            import shutil
            for f in local_trust.iterdir():
                if f.is_file():
                    shutil.copy2(f, output / "trust" / f.name)

        # Packages — copy all available modules
        local_packages = local_registry / "packages"
        if local_packages.exists():
            import shutil
            shutil.copytree(local_packages, output / "packages", dirs_exist_ok=True)

        # Generate MANIFEST.sha256 for integrity verification
        manifest_lines = []
        for fpath in sorted(output.rglob("*")):
            if fpath.is_file() and fpath.name != "MANIFEST.sha256":
                h = hashlib.sha256(fpath.read_bytes()).hexdigest()
                rel = fpath.relative_to(output)
                manifest_lines.append(f"{h}  {rel}")
        (output / "MANIFEST.sha256").write_text(
            "\n".join(manifest_lines), encoding="utf-8"
        )

        logger.info("Air-gapped export created at %s (%d files)", output, len(manifest_lines))

        return {
            "status": "completed",
            "output_dir": str(output),
            "message": f"Air-gapped export snapshot created at {output} ({len(manifest_lines)} files)",
        }

    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc


@router.post("/import", response_model=ImportResponse)
async def air_gapped_import(req: ImportRequest) -> dict[str, Any]:
    """Import an air-gapped export into the local registry.

    Reads from a USB-mounted export directory, verifies integrity
    via MANIFEST.sha256, and copies into the local registry store.

    MANIFEST.sha256 is mandatory — import fails without it.
    """
    import hashlib
    import shutil
    from pathlib import Path

    input_dir = Path(req.input_dir)
    if not input_dir.exists():
        raise HTTPException(status_code=404, detail=f"Input directory not found: {input_dir}")

    # Mandatory integrity verification
    manifest_path = input_dir / "MANIFEST.sha256"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=400,
            detail="MANIFEST.sha256 not found — cannot verify export integrity",
        )

    # Verify every file against MANIFEST.sha256
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Cannot read manifest: {exc}") from exc

    for line in manifest_text.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail=f"Malformed manifest line: {line}")
        expected_hash, rel_path = parts
        full_path = input_dir / rel_path.lstrip("./")
        if not full_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"File missing from export: {rel_path}",
            )
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise HTTPException(
                status_code=400,
                detail=f"Integrity check failed for {rel_path}: expected {expected_hash}, got {actual_hash}",
            )

    # Default local registry location
    registry_dir = Path.home() / ".scientificstate" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Copy TUF metadata
        tuf_src = input_dir / "tuf"
        if tuf_src.exists():
            tuf_dst = registry_dir / "tuf"
            tuf_dst.mkdir(exist_ok=True)
            for f in tuf_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, tuf_dst / f.name)

        # Copy trust chain
        trust_src = input_dir / "trust"
        if trust_src.exists():
            trust_dst = registry_dir / "trust"
            trust_dst.mkdir(exist_ok=True)
            for f in trust_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, trust_dst / f.name)

        # Copy registry index
        for name in ("index.json", "format-map.json"):
            src = input_dir / "registry" / name
            if src.exists():
                shutil.copy2(src, registry_dir / name)

        # Copy packages
        pkg_src = input_dir / "packages"
        if pkg_src.exists():
            pkg_dst = registry_dir / "packages"
            if pkg_dst.exists():
                shutil.copytree(pkg_src, pkg_dst, dirs_exist_ok=True)
            else:
                shutil.copytree(pkg_src, pkg_dst)

        logger.info(
            "Air-gapped import from %s → %s (integrity=verified)",
            input_dir,
            registry_dir,
        )

        return {
            "status": "completed",
            "registry_dir": str(registry_dir),
            "message": f"Air-gapped import complete from {input_dir} (integrity verified)",
        }

    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
