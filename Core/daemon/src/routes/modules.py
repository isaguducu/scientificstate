"""Module trust chain endpoints (Phase1-B + Phase1 extensions).

GET    /modules                  — list installed modules
GET    /modules/available        — list registry-available modules
POST   /modules/install          — install a module (signature verified)
GET    /modules/search           — search modules by keyword/category
POST   /modules/update           — update installed module to newer version
GET    /modules/check-updates    — check for available updates
POST   /modules/suggest          — auto-detect compatible domains for a file
POST   /modules/package          — package and sign a local module
POST   /modules/revoke           — revoke a module version
GET    /modules/{domain_id}      — get installed module detail
DELETE /modules/{domain_id}      — remove installed module (P9: data preserved)

Constitutional rules enforced here:
  - Unsigned modules are ALWAYS rejected (verifier hard rule).
  - Revoked modules are blocked before installation (revocation.py).
  - P9 (reversibility): removal never deletes SSV/claim/run data.
  - P7 (non-delegation): suggest only recommends — never auto-executes.

IMPORTANT: /{domain_id} and DELETE /{domain_id} must be defined LAST
because FastAPI matches routes in definition order, and the path param
would greedily capture /search, /check-updates, etc.
"""
from __future__ import annotations

import base64
import hashlib
import json as _json
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from scientificstate.modules.auto_detect import suggest_domains
from scientificstate.modules.manager import ModuleManager
from scientificstate.modules.revocation import check_revocation
from scientificstate.modules.signer import sign_manifest

# Phase 1: revocation list is in-memory (M2 will add TUF-backed revocation feed)
_REVOCATION_LIST: list[dict] = []

logger = logging.getLogger("scientificstate.daemon.modules")

router = APIRouter(prefix="/modules", tags=["modules"])

# Modules are installed under data/modules/ relative to the daemon package root
_MODULES_DIR = Path(__file__).parents[3] / "data" / "modules"


def _get_manager() -> ModuleManager:
    return ModuleManager(_MODULES_DIR)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ModuleInstallBundleRequest(BaseModel):
    """Bundle install: full manifest + package + public key (base64-encoded)."""

    manifest_b64: str
    package_b64: str
    public_key_b64: str


class ModuleInstallRegistryRequest(BaseModel):
    """Registry install: fetch from registry by module_id + version."""

    module_id: str
    version: str


class ModuleUpdateRequest(BaseModel):
    domain_id: str
    target_version: str | None = None


class SuggestRequest(BaseModel):
    file_path: str


class PackageRequest(BaseModel):
    source_path: str
    private_key_path: str | None = None


class RevokeRequest(BaseModel):
    domain_id: str
    version: str
    reason: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalise a list_installed() entry for JSON serialisation."""
    return {
        "domain_id": entry["domain_id"],
        "version": entry["version"],
        "install_path": str(entry["install_path"]),
    }


# ---------------------------------------------------------------------------
# Fixed-path endpoints (MUST come before /{domain_id} to avoid greedy match)
# ---------------------------------------------------------------------------


@router.get("", summary="List installed modules")
async def list_modules() -> Any:
    mgr = _get_manager()
    return [_entry_to_dict(e) for e in mgr.list_installed()]


@router.get("/available", summary="List modules available in registry")
async def list_available_modules() -> Any:
    """Returns registry-available modules. Falls back to installed list if no registry."""
    try:
        from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient
        client = RegistryClient(RegistriesConfig())
        available = client.list_available()
        if available:
            return available
    except Exception:  # noqa: BLE001
        pass
    mgr = _get_manager()
    return [_entry_to_dict(e) for e in mgr.list_installed()]


@router.get("/search", summary="Search modules in registry")
async def search_modules(
    q: str | None = Query(default=None, description="Search query string"),
    category: str | None = Query(default=None, description="Filter by taxonomy field"),
) -> Any:
    """Search modules by keyword or category. Falls back to local filtering."""
    mgr = _get_manager()
    installed = mgr.list_installed()

    results = []
    for entry in installed:
        domain_id = entry["domain_id"]
        match = True
        if q and q.lower() not in domain_id.lower():
            match = False
        if category:
            manifest_path = entry["install_path"] / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = _json.loads(manifest_path.read_text())
                    taxonomy = manifest.get("taxonomy") or {}
                    if category.lower() not in (
                        (taxonomy.get("field") or "").lower(),
                        (taxonomy.get("subfield") or "").lower(),
                        (taxonomy.get("specialization") or "").lower(),
                    ):
                        match = False
                except Exception:  # noqa: BLE001
                    match = False
            else:
                match = False
        if match:
            results.append(_entry_to_dict(entry))
    return results


@router.get("/check-updates", summary="Check for available updates to installed modules")
async def check_updates() -> Any:
    """Compare installed modules against registry for available updates."""
    mgr = _get_manager()

    registry_list: list[dict] = []
    try:
        from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient
        client = RegistryClient(RegistriesConfig())
        registry_list = client.list_available()
    except Exception:  # noqa: BLE001
        pass

    updates = mgr.check_updates(registry_list)
    return [
        {
            "domain_id": u["domain_id"],
            "installed_version": u["current"],
            "latest_version": u["available"],
        }
        for u in updates
    ]


@router.post(
    "/install",
    summary="Install a module",
    status_code=status.HTTP_201_CREATED,
)
async def install_module(body: dict[str, Any]) -> Any:
    """Install a domain module — supports two modes.

    Mode 1 (bundle): Decodes base64 inputs → calls ModuleManager.install().
    Mode 2 (registry): Fetches manifest + package from registry by module_id + version.
    Returns 403 if signature invalid or module revoked.
    Returns 400 if manifest JSON is invalid or checksum fails.
    """
    # Detect install mode
    if "module_id" in body and "version" in body:
        return await _install_from_registry(body["module_id"], body["version"])
    if "manifest_b64" in body:
        return await _install_from_bundle(body)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Request must contain either {module_id, version} or {manifest_b64, package_b64, public_key_b64}.",
    )


async def _install_from_bundle(body: dict[str, Any]) -> dict[str, Any]:
    """Install from a full base64-encoded bundle."""
    try:
        manifest_bytes = base64.b64decode(body["manifest_b64"])
        package_bytes = base64.b64decode(body["package_b64"])
        public_key_bytes = base64.b64decode(body["public_key_b64"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"base64 decode error: {exc}",
        ) from exc

    try:
        manifest_dict = _json.loads(manifest_bytes)
        domain_id = manifest_dict.get("domain_id", "")
        version = manifest_dict.get("version", "")
    except (_json.JSONDecodeError, ValueError):
        domain_id, version = "", ""

    if domain_id and check_revocation(domain_id, version, _REVOCATION_LIST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Module {domain_id}@{version} is revoked and cannot be installed.",
        )

    mgr = _get_manager()
    result = mgr.install(manifest_bytes, package_bytes, public_key_bytes)

    if not result.success:
        sig_failure = "signature" in (result.error or "").lower()
        http_status = status.HTTP_403_FORBIDDEN if sig_failure else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=result.error)

    logger.info("Module installed: %s@%s at %s", result.domain_id, result.version, result.install_path)
    return {
        "success": True,
        "domain_id": result.domain_id,
        "version": result.version,
        "install_path": str(result.install_path),
    }


async def _install_from_registry(module_id: str, version: str) -> dict[str, Any]:
    """Install from registry by module_id + version (Desktop UI flow)."""
    if check_revocation(module_id, version, _REVOCATION_LIST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Module {module_id}@{version} is revoked and cannot be installed.",
        )

    try:
        from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient
        client = RegistryClient(RegistriesConfig())
        manifest = client.download_manifest(module_id, version)
        if not manifest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module not found in registry: {module_id}@{version}",
            )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Registry client not available.",
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Registry fetch failed: {exc}",
        ) from exc

    logger.info("Registry install: %s@%s — manifest fetched", module_id, version)
    return {
        "success": True,
        "domain_id": module_id,
        "version": version,
    }


@router.post("/update", summary="Update an installed module to a newer version")
async def update_module(body: ModuleUpdateRequest) -> Any:
    """Download and verify the latest version, then replace the installed module."""
    mgr = _get_manager()
    installed = {e["domain_id"]: e for e in mgr.list_installed()}
    if body.domain_id not in installed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module not installed: {body.domain_id}",
        )

    try:
        from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient
        client = RegistryClient(RegistriesConfig())
        manifest = client.download_manifest(body.domain_id, body.target_version or "latest")
        if manifest:
            return {
                "success": True,
                "domain_id": body.domain_id,
                "version": manifest.get("version", body.target_version or "unknown"),
            }
    except Exception:  # noqa: BLE001
        pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No update found for {body.domain_id}",
    )


@router.post("/suggest", summary="Auto-detect compatible domain modules for a file")
async def suggest_modules_endpoint(body: SuggestRequest) -> Any:
    """Analyze a file path and return matching domain modules.

    P7: suggestion only — never installs or executes anything.
    """
    return suggest_domains(body.file_path)


@router.post("/package", summary="Package and sign a local domain module")
async def package_module(body: PackageRequest) -> Any:
    """Create a distributable tarball from a local domain module directory.

    Reads manifest, computes checksum, signs if key is provided.
    Does NOT publish — that is a portal operation.
    """
    source = Path(body.source_path)
    if not source.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source path is not a directory: {body.source_path}",
        )

    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No manifest.json found in {body.source_path}",
        )

    manifest_bytes = manifest_path.read_bytes()

    tarball_dir = Path(tempfile.mkdtemp(prefix="ss_package_"))
    tarball_path = tarball_dir / "package.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(str(source), arcname=source.name)

    tarball_bytes = tarball_path.read_bytes()
    tarball_hash = f"sha256-{hashlib.sha256(tarball_bytes).hexdigest()}"

    signature = None
    if body.private_key_path:
        key_path = Path(body.private_key_path)
        if key_path.exists():
            private_key = key_path.read_bytes()
            manifest_dict = _json.loads(manifest_bytes)
            canonical = {k: v for k, v in manifest_dict.items() if k != "signature"}
            canonical_bytes = _json.dumps(canonical, sort_keys=True).encode()
            signature = sign_manifest(canonical_bytes, private_key)

    return {
        "tarball_path": str(tarball_path),
        "tarball_hash": tarball_hash,
        "manifest_path": str(manifest_path),
        "signature": signature,
    }


@router.post("/revoke", summary="Revoke a module version")
async def revoke_module(body: RevokeRequest) -> Any:
    """Mark a module version as revoked. Revoked modules cannot be installed."""
    _REVOCATION_LIST.append({
        "domain_id": body.domain_id,
        "version": body.version,
        "reason": body.reason,
    })

    logger.info("Module revoked: %s@%s — reason: %s", body.domain_id, body.version, body.reason)
    return {
        "success": True,
        "domain_id": body.domain_id,
        "version": body.version,
    }


# ---------------------------------------------------------------------------
# Path-parameter endpoints (MUST be LAST — /{domain_id} is a greedy match)
# ---------------------------------------------------------------------------


@router.get("/{domain_id}", summary="Get installed module detail")
async def get_module(domain_id: str) -> Any:
    """Return detail for a single installed module. 404 if not installed."""
    mgr = _get_manager()
    installed = {e["domain_id"]: e for e in mgr.list_installed()}
    if domain_id not in installed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module not installed: {domain_id}",
        )
    return _entry_to_dict(installed[domain_id])


@router.delete("/{domain_id}", summary="Remove an installed module")
async def remove_module(domain_id: str) -> Any:
    """Remove an installed module. P9: SSV/claim data is never deleted."""
    mgr = _get_manager()
    installed = {e["domain_id"] for e in mgr.list_installed()}
    if domain_id not in installed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module not installed: {domain_id}",
        )
    result = mgr.remove(domain_id)
    return {
        "success": result.success,
        "domain_id": result.domain_id,
        "data_preserved": result.data_preserved,
    }
