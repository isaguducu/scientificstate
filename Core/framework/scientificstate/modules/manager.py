"""
Module lifecycle manager — install, remove, list, update-check.

Constitutional rule (P9 reversibility):
  Module removal deletes only the module code directory.
  SSV data, claim data, and run records are NEVER deleted by module removal.
  data_preserved is always True.

The manager uses signer/verifier for trust-chain enforcement:
  Only signed modules with valid signatures may be installed.

M3 verification chain (6 steps):
  1. Ed25519 signature verify              (P1 — existing)
  2. TUF targets hash verify               (P2 — existing)
  3. TUF delegated targets verify          (M3 — NEW)
  4. Sigstore-only verify                  (M3 — Ed25519 alone insufficient)
  5. Permission manifest check             (M2 — existing)
  6. Kernel sandbox execute                (M3 — NEW)
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        self._delegated_targets: dict | None = None  # M3: delegated targets metadata
        self._root_targets_for_delegation: dict | None = None  # M3: root targets with delegations
        self._sigstore_required: bool = True  # M3: Sigstore mandatory by default
        self._sandbox_enabled: bool = False  # M3: kernel sandbox (opt-in)

    def set_tuf_targets(self, targets_meta: dict) -> None:
        """Set TUF targets metadata for hash verification during install.

        When set, every install() call will verify the package hash against
        the targets metadata before writing to disk.  Pass None to disable.
        """
        self._tuf_targets = targets_meta

    def set_delegated_targets(
        self,
        root_targets: dict[str, Any],
        delegated_meta: dict[str, Any],
    ) -> None:
        """Set TUF delegated targets for M3 delegation chain verification.

        Args:
            root_targets: root targets metadata containing delegation entries.
            delegated_meta: delegated targets metadata signed by delegate key.
        """
        self._root_targets_for_delegation = root_targets
        self._delegated_targets = delegated_meta

    def set_sigstore_required(self, required: bool) -> None:
        """Control Sigstore enforcement (M3 default: True)."""
        self._sigstore_required = required

    def set_sandbox_enabled(self, enabled: bool) -> None:
        """Enable/disable kernel sandbox execution after install."""
        self._sandbox_enabled = enabled

    def install(
        self,
        manifest_bytes: bytes,
        package_bytes: bytes,
        public_key: bytes,
    ) -> InstallResult:
        """Install a module after verifying its manifest signature.

        M3 verification chain (6 steps):
          1. Ed25519 signature verify           (P1)
          2. TUF targets hash verify            (P2, optional)
          3. TUF delegated targets verify       (M3, optional)
          4. Sigstore-only verify               (M3, mandatory by default)
          5. Permission manifest check          (M2, advisory)
          6. Write to disk                      (kernel sandbox at execution time)

        Args:
            manifest_bytes: raw manifest JSON bytes (what was signed)
            package_bytes: module package content bytes
            public_key: DER-encoded Ed25519 public key of the publisher

        Returns:
            InstallResult with success=True and install_path on success,
            or success=False with error message on any failure.
        """
        # ── Step 0: Parse manifest ────────────────────────────────────────
        try:
            manifest = json.loads(manifest_bytes)
        except (json.JSONDecodeError, ValueError) as exc:
            return InstallResult(
                success=False, domain_id="unknown", version="unknown",
                install_path=None, error=f"invalid manifest JSON: {exc}"
            )

        domain_id = manifest.get("domain_id", "unknown")
        version = manifest.get("version", "unknown")

        # ── Step 1: Ed25519 signature verify (P1) ────────────────────────
        sig_field = manifest.get("signature")
        if isinstance(sig_field, dict):
            signature_hex = sig_field.get("value")
        elif sig_field is None:
            signature_hex = None
        else:
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
        checksum_field = manifest.get("checksum")
        if isinstance(checksum_field, dict):
            expected_checksum = checksum_field.get("value")
            algorithm = checksum_field.get("algorithm", "sha256")
        else:
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

        # ── Step 2: TUF targets hash verify (P2, optional) ───────────────
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

        # ── Step 3: TUF delegated targets verify (M3, optional) ──────────
        if self._delegated_targets is not None and self._root_targets_for_delegation is not None:
            from scientificstate.modules.tuf.delegated import verify_delegated_target

            target_path = f"{domain_id}/{version}/module.tar.gz"
            actual_hash = hashlib.sha256(package_bytes).hexdigest()
            if not verify_delegated_target(
                target_path, actual_hash,
                self._root_targets_for_delegation,
                self._delegated_targets,
            ):
                return InstallResult(
                    success=False, domain_id=domain_id, version=version,
                    install_path=None,
                    error="TUF delegated target verification failed — install rejected",
                )

        # ── Step 4: Sigstore-only verify (M3, mandatory by default) ──────
        sigstore_bundle = manifest.get("sigstore_bundle")
        if self._sigstore_required:
            from scientificstate.modules.sigstore_verify import (
                verify_sigstore_signature,
            )

            result = verify_sigstore_signature(package_bytes, sigstore_bundle)
            if not result["valid"]:
                return InstallResult(
                    success=False, domain_id=domain_id, version=version,
                    install_path=None,
                    error=f"Sigstore verification failed (M3 mandatory): {result['reason']}",
                )
        elif sigstore_bundle:
            # Sigstore not required but bundle present — verify advisory
            from scientificstate.modules.sigstore_verify import (
                verify_sigstore_signature,
            )
            verify_sigstore_signature(package_bytes, sigstore_bundle)

        # ── Step 5: Permission manifest check (M2, advisory) ─────────────
        permission = manifest.get("permission")
        if permission:
            from scientificstate.modules.sandbox.config import sandbox_config_from_permission

            # Validate that permission manifest produces a valid config
            # (this is advisory — does not block install, but logs warnings)
            sandbox_config_from_permission(permission)

        # ── Step 6: Write to disk ─────────────────────────────────────────
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

    def execute_in_sandbox(
        self,
        domain_id: str,
        command: list[str],
        *,
        permission: dict[str, Any] | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command inside the kernel sandbox for a module.

        This is the M3 kernel sandbox execution (Step 6 of the chain).
        Called at RUN time, not at install time.

        Args:
            domain_id: installed module to sandbox.
            command: command + arguments to run.
            permission: permission manifest dict (flat shape).
                If None, uses a restrictive default.

        Returns:
            (exit_code, stdout, stderr) tuple.
        """
        from scientificstate.modules.sandbox import get_sandbox
        from scientificstate.modules.sandbox.config import sandbox_config_from_permission

        module_dir = self.modules_dir / domain_id
        perm = permission or {}
        config = sandbox_config_from_permission(
            perm,
            module_dir=str(module_dir),
        )

        sandbox = get_sandbox()
        result = sandbox.execute(command, config, cwd=str(module_dir))
        return result.exit_code, result.stdout, result.stderr

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
