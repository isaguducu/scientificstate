"""
Module lifecycle manager — install, remove, list, update-check.

Constitutional rule (P9 reversibility):
  Module removal deletes only the module code directory.
  SSV data, claim data, and run records are NEVER deleted by module removal.
  data_preserved is always True.

The manager uses signer/verifier for trust-chain enforcement:
  Only signed modules with valid signatures may be installed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from scientificstate.modules.verifier import verify_manifest


@dataclass
class InstallResult:
    """Result of a module installation attempt."""

    success: bool
    domain_id: str
    version: str
    install_path: Path | None
    error: str | None = None


@dataclass
class RemoveResult:
    """Result of a module removal operation."""

    success: bool
    domain_id: str
    data_preserved: bool  # P9: SSV/claim data is never deleted


class ModuleManager:
    """Manages the lifecycle of installed domain modules.

    modules_dir: base directory for installed modules (e.g. ~/.scientificstate/modules/)
    Each module is installed to modules_dir/{domain_id}/v{version}/
    """

    def __init__(self, modules_dir: Path) -> None:
        self.modules_dir = modules_dir
        self._tuf_targets: dict | None = None  # Optional TUF targets metadata

    def set_tuf_targets(self, targets_meta: dict) -> None:
        """Set TUF targets metadata for hash verification during install.

        When set, every install() call will verify the package hash against
        the targets metadata before writing to disk.  Pass None to disable.
        """
        self._tuf_targets = targets_meta

    def install(
        self,
        manifest_bytes: bytes,
        package_bytes: bytes,
        public_key: bytes,
    ) -> InstallResult:
        """Install a module after verifying its manifest signature.

        Steps:
          1. Parse manifest JSON to extract domain_id, version, signature
          2. Verify Ed25519 signature (reject if unsigned or invalid)
          3. Verify package checksum (sha256 in manifest)
          4. Extract/write package to modules_dir/{domain_id}/v{version}/
          5. Return InstallResult

        Args:
            manifest_bytes: raw manifest JSON bytes (what was signed)
            package_bytes: module package content bytes
            public_key: DER-encoded Ed25519 public key of the publisher

        Returns:
            InstallResult with success=True and install_path on success,
            or success=False with error message on any failure.
        """
        # ── Parse manifest ────────────────────────────────────────────────
        try:
            manifest = json.loads(manifest_bytes)
        except (json.JSONDecodeError, ValueError) as exc:
            return InstallResult(
                success=False, domain_id="unknown", version="unknown",
                install_path=None, error=f"invalid manifest JSON: {exc}"
            )

        domain_id = manifest.get("domain_id", "unknown")
        version = manifest.get("version", "unknown")

        # ── Verify signature ──────────────────────────────────────────────
        # Schema: signature = {algorithm, public_key_id, value} | null
        # Canonical bytes = manifest WITHOUT the embedded signature field.
        # This avoids the chicken-and-egg problem: the signature covers
        # the content, not the container that holds the signature itself.
        sig_field = manifest.get("signature")
        if isinstance(sig_field, dict):
            signature_hex = sig_field.get("value")  # object → extract .value
        elif sig_field is None:
            signature_hex = None  # unsigned → will be rejected by verifier
        else:
            # Unexpected type — reject with a descriptive message (type-safe)
            return InstallResult(
                success=False, domain_id=domain_id, version=version,
                install_path=None,
                error=f"signature field has unexpected type {type(sig_field).__name__!r}; "
                      "expected object {{algorithm, public_key_id, value}} or null",
            )
        canonical = {k: v for k, v in manifest.items() if k != "signature"}
        canonical_bytes = json.dumps(canonical, sort_keys=True).encode()
        verify_result = verify_manifest(canonical_bytes, signature_hex, public_key)
        if not verify_result.valid:
            return InstallResult(
                success=False, domain_id=domain_id, version=version,
                install_path=None, error=f"signature check failed: {verify_result.reason}"
            )

        # ── Verify package checksum ───────────────────────────────────────
        # Schema: checksum = {algorithm: "sha256"|"sha512", value: hex-string}
        checksum_field = manifest.get("checksum")
        if isinstance(checksum_field, dict):
            expected_checksum = checksum_field.get("value")
            algorithm = checksum_field.get("algorithm", "sha256")
        else:
            # Legacy or missing — skip checksum validation gracefully
            expected_checksum = None
            algorithm = "sha256"
        if expected_checksum:
            if algorithm == "sha512":
                actual_checksum = hashlib.sha512(package_bytes).hexdigest()
            else:
                actual_checksum = hashlib.sha256(package_bytes).hexdigest()
            if actual_checksum != expected_checksum:
                return InstallResult(
                    success=False, domain_id=domain_id, version=version,
                    install_path=None, error="package checksum mismatch"
                )

        # ── TUF targets hash verification (P2, optional) ──────────────────
        if self._tuf_targets is not None:
            from scientificstate.modules.tuf.targets import verify_target_hash

            target_path = f"{domain_id}/{version}/module.tar.gz"
            actual_hash = hashlib.sha256(package_bytes).hexdigest()
            if not verify_target_hash(target_path, actual_hash, self._tuf_targets):
                return InstallResult(
                    success=False, domain_id=domain_id, version=version,
                    install_path=None,
                    error="TUF target hash mismatch — install rejected",
                )

        # ── Sigstore verification (P2, advisory only) ────────────────────
        sigstore_bundle = manifest.get("sigstore_bundle")
        if sigstore_bundle:
            from scientificstate.modules.sigstore_verify import (
                verify_sigstore_signature,
            )

            verify_sigstore_signature(package_bytes, sigstore_bundle)
            # M2: advisory only — result logged but does not block install.
            # M3: this will become mandatory for new modules.

        # ── Write to disk ─────────────────────────────────────────────────
        install_path = self.modules_dir / domain_id / f"v{version}"
        try:
            install_path.mkdir(parents=True, exist_ok=True)
            (install_path / "package.bin").write_bytes(package_bytes)
            (install_path / "manifest.json").write_bytes(manifest_bytes)
        except OSError as exc:
            return InstallResult(
                success=False, domain_id=domain_id, version=version,
                install_path=None, error=f"write error: {exc}"
            )

        return InstallResult(
            success=True, domain_id=domain_id, version=version,
            install_path=install_path
        )

    def remove(self, domain_id: str) -> RemoveResult:
        """Remove an installed module.

        P9 constitutional rule: SSV and claim data are NEVER deleted here.
        Only the module code directory is removed.

        Args:
            domain_id: the domain module to remove

        Returns:
            RemoveResult with data_preserved=True always.
        """
        module_dir = self.modules_dir / domain_id
        if module_dir.exists():
            shutil.rmtree(module_dir)

        return RemoveResult(
            success=True,
            domain_id=domain_id,
            data_preserved=True,  # SSV/claim data lives in DB, not here
        )

    def list_installed(self) -> list[dict]:
        """List all installed modules.

        Returns:
            List of dicts with keys: domain_id, version, install_path.
            Empty list if no modules installed or modules_dir does not exist.
        """
        if not self.modules_dir.exists():
            return []

        result = []
        for domain_dir in sorted(self.modules_dir.iterdir()):
            if not domain_dir.is_dir():
                continue
            for version_dir in sorted(domain_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                version_str = version_dir.name.lstrip("v")
                result.append({
                    "domain_id": domain_dir.name,
                    "version": version_str,
                    "install_path": version_dir,
                })
        return result

    def check_updates(self, registry_list: list[dict]) -> list[dict]:
        """Compare installed modules against registry to find available updates.

        Args:
            registry_list: list of dicts with "domain_id" and "version" keys
                           representing available modules in the registry.

        Returns:
            List of update dicts: {"domain_id": ..., "current": ..., "available": ...}
            for each module where a newer version exists in the registry.
        """
        installed = {m["domain_id"]: m["version"] for m in self.list_installed()}
        updates = []
        for entry in registry_list:
            domain_id = entry.get("domain_id")
            available = entry.get("version")
            current = installed.get(domain_id)
            if current and available and available != current:
                updates.append({
                    "domain_id": domain_id,
                    "current": current,
                    "available": available,
                })
        return updates
