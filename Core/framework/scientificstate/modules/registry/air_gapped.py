"""Air-gapped registry — offline module installation from USB export.

Provides full offline install flow:
  1. TUF offline verification (root + targets metadata)
  2. Ed25519 signature verification
  3. Sigstore offline verification (pre-cached certificate)
  4. Permission manifest → sandbox config
  5. Package extraction + installation

Works entirely from local filesystem — zero network calls.
"""
from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InstallResult:
    """Result of an air-gapped module installation."""

    ok: bool
    module_name: str
    version: str | None = None
    error: str | None = None


class AirGappedRegistry:
    """Offline module registry for air-gapped environments.

    Reads from a local registry directory populated by air-gapped-import.sh.
    All verification happens locally — no network calls.

    Args:
        registry_dir: Path to the local registry directory
            (e.g. ~/.scientificstate/registry).
        tuf_verifier: OfflineTUFVerifier instance for TUF metadata checks.
    """

    def __init__(
        self,
        registry_dir: Path,
        tuf_verifier: Any,
    ) -> None:
        from scientificstate.modules.tuf.offline_verify import OfflineTUFVerifier

        self._registry_dir = Path(registry_dir)
        self._tuf_verifier: OfflineTUFVerifier = tuf_verifier
        self._packages_dir = self._registry_dir / "packages"
        self._install_dir = self._registry_dir / "installed"

    def install_module(self, module_name: str, version: str | None = None) -> InstallResult:
        """Install a module from the air-gapped registry.

        Verification chain:
          1. TUF offline verify (target hash)
          2. Ed25519 signature verify
          3. Sigstore offline verify (pre-cached certificate)
          4. Permission manifest → sandbox config
          5. Extract + install

        Args:
            module_name: Module identifier (domain_id).
            version: Specific version string. If None, uses latest available.

        Returns:
            InstallResult with ok=True on success, ok=False with error on failure.
        """
        # Resolve version
        if version is None:
            version = self._resolve_latest_version(module_name)
            if version is None:
                return InstallResult(
                    ok=False, module_name=module_name, error="no versions available"
                )

        pkg_dir = self._packages_dir / module_name / f"v{version}"
        if not pkg_dir.exists():
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error=f"package directory not found: {pkg_dir}",
            )

        # 1. TUF offline verify
        tarball_path = pkg_dir / "package.tar.gz"
        if not tarball_path.exists():
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error="package.tar.gz not found",
            )

        tarball_hash = _sha256_file(tarball_path)
        target_name = f"{module_name}/{version}/module.tar.gz"
        tuf_result = self._tuf_verifier.verify_target(target_name, tarball_hash)
        if not tuf_result.ok:
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error=f"TUF verification failed: {tuf_result.error}",
            )

        # 2. Ed25519 signature verify
        manifest_path = pkg_dir / "manifest.json"
        signature_path = pkg_dir / "signature.sig"
        ed25519_result = self._verify_ed25519(manifest_path, signature_path)
        if ed25519_result is not None:
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error=f"Ed25519 verification failed: {ed25519_result}",
            )

        # 3. Sigstore offline verify
        sigstore_result = self._verify_sigstore_offline(tarball_path, pkg_dir)
        if sigstore_result is not None:
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error=f"Sigstore verification failed: {sigstore_result}",
            )

        # 4. Permission manifest → sandbox config
        permissions = self._load_permissions(manifest_path)

        # 5. Extract + install
        install_path = self._install_dir / module_name / f"v{version}"
        install_path.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(path=str(install_path), filter="data")
        except (tarfile.TarError, OSError) as exc:
            return InstallResult(
                ok=False,
                module_name=module_name,
                version=version,
                error=f"extraction failed: {exc}",
            )

        # Write sandbox config alongside installed module
        if permissions:
            sandbox_config_path = install_path / "_sandbox.json"
            sandbox_config_path.write_text(
                json.dumps(permissions, indent=2), encoding="utf-8"
            )

        return InstallResult(ok=True, module_name=module_name, version=version)

    def list_available(self) -> list[dict[str, Any]]:
        """List available modules from the offline registry index.

        Returns:
            List of module dicts from index.json, or empty list if unavailable.
        """
        index_path = self._registry_dir / "index.json"
        if not index_path.exists():
            return []

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            return data.get("packages", [])
        except (json.JSONDecodeError, OSError):
            return []

    def verify_integrity(self, export_dir: Path) -> bool:
        """Verify integrity of an air-gapped export using MANIFEST.sha256.

        Args:
            export_dir: Path to the export directory containing MANIFEST.sha256.

        Returns:
            True if all checksums match, False otherwise.
        """
        manifest_path = Path(export_dir) / "MANIFEST.sha256"
        if not manifest_path.exists():
            return False

        try:
            lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return False

        for line in lines:
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                return False
            expected_hash, file_path = parts
            # file_path may be relative to export_dir
            full_path = Path(export_dir) / file_path.lstrip("./")
            if not full_path.exists():
                return False
            actual_hash = _sha256_file(full_path)
            if actual_hash != expected_hash:
                return False

        return True

    def _resolve_latest_version(self, module_name: str) -> str | None:
        """Find the latest version available for a module."""
        module_dir = self._packages_dir / module_name
        if not module_dir.exists():
            return None

        versions = []
        for d in sorted(module_dir.iterdir()):
            if d.is_dir() and d.name.startswith("v"):
                versions.append(d.name[1:])  # strip leading "v"

        return versions[-1] if versions else None

    def _verify_ed25519(
        self, manifest_path: Path, signature_path: Path
    ) -> str | None:
        """Verify Ed25519 signature of manifest.

        Returns None on success, error string on failure.
        """
        if not manifest_path.exists():
            return "manifest.json not found"
        if not signature_path.exists():
            return "signature.sig not found"

        try:
            from scientificstate.modules.verifier import verify_manifest

            manifest_bytes = manifest_path.read_bytes()
            signature_hex = signature_path.read_text(encoding="utf-8").strip()

            # Load public key from trust chain or registry
            pubkey_path = self._registry_dir / "trust" / "public_key.der"
            if not pubkey_path.exists():
                return "public key not found in trust chain (trust/public_key.der)"

            public_key = pubkey_path.read_bytes()
            result = verify_manifest(manifest_bytes, signature_hex, public_key)
            if not result.valid:
                return result.reason
            return None
        except Exception as exc:  # noqa: BLE001
            return str(exc)

    def _verify_sigstore_offline(
        self, tarball_path: Path, pkg_dir: Path
    ) -> str | None:
        """Verify Sigstore bundle in offline mode.

        Returns None on success (or if bundle not present — soft fail in air-gapped),
        error string on verification failure.
        """
        bundle_path = pkg_dir / "sigstore.bundle.json"
        if not bundle_path.exists():
            return "sigstore.bundle.json not found (mandatory since M3)"

        try:
            from scientificstate.modules.sigstore_verify import verify_sigstore_signature

            artifact_bytes = tarball_path.read_bytes()
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            result = verify_sigstore_signature(artifact_bytes, bundle)
            if not result["valid"]:
                return result["reason"]
            return None
        except Exception as exc:  # noqa: BLE001
            return str(exc)

    @staticmethod
    def _load_permissions(manifest_path: Path) -> dict[str, Any] | None:
        """Extract permission manifest from module manifest."""
        if not manifest_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return manifest.get("permissions")
        except (json.JSONDecodeError, OSError):
            return None


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
