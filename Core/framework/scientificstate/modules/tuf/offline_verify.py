"""Offline TUF verification for air-gapped environments.

Verifies TUF metadata and target hashes without network access.
Uses pre-cached root.json and targets.json from USB export.

Grace period: expired metadata is accepted up to OFFLINE_GRACE_PERIOD_DAYS
after expiry to allow air-gapped deployments that cannot refresh metadata.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class VerifyResult:
    """Result of an offline TUF verification."""

    ok: bool
    error: str | None = None


class OfflineTUFVerifier:
    """Verify TUF metadata and target hashes in an air-gapped environment.

    Loads root.json, targets.json, and optionally trust-chain.json from
    a local directory (typically populated by air-gapped-import.sh).

    Args:
        tuf_dir: Directory containing TUF metadata files.
    """

    OFFLINE_GRACE_PERIOD_DAYS = 30

    def __init__(self, tuf_dir: Path) -> None:
        self._tuf_dir = Path(tuf_dir)
        self._root: dict[str, Any] | None = self._load_json(self._tuf_dir / "root.json")
        self._targets: dict[str, Any] | None = self._load_json(self._tuf_dir / "targets.json")
        self._trust_chain: dict[str, Any] | None = self._load_json(
            self._tuf_dir / "trust-chain.json"
        )

    def verify_target(self, target_name: str, target_hash: str) -> VerifyResult:
        """Verify a target against offline TUF metadata.

        Steps:
          1. Root metadata must be present and have valid structure.
          2. Targets metadata must be present.
          3. Expiry check with grace period.
          4. Target must exist in targets metadata.
          5. Target hash must match.

        Args:
            target_name: Target path (e.g. "polymer_science/1.0.0/module.tar.gz").
            target_hash: SHA-256 hex digest of the target file.

        Returns:
            VerifyResult(ok=True) on success, VerifyResult(ok=False, error=...) on failure.
        """
        # 1. Root metadata must be present
        if self._root is None:
            return VerifyResult(ok=False, error="root.json not found or invalid")

        if not self._verify_root_structure():
            return VerifyResult(ok=False, error="root.json structure invalid")

        # 2. Targets metadata must be present
        if self._targets is None:
            return VerifyResult(ok=False, error="targets.json not found or invalid")

        # 3. Expiry check with grace period
        if self._is_expired_beyond_grace():
            return VerifyResult(
                ok=False,
                error=f"targets.json expired beyond {self.OFFLINE_GRACE_PERIOD_DAYS}-day grace period",
            )

        # 4. Target must exist in targets metadata
        targets = self._targets.get("signed", {}).get("targets", {})
        if target_name not in targets:
            return VerifyResult(ok=False, error=f"target '{target_name}' not found in metadata")

        # 5. Hash must match
        expected_hash = targets[target_name].get("hashes", {}).get("sha256")
        if expected_hash is None:
            return VerifyResult(ok=False, error=f"no SHA-256 hash for target '{target_name}'")

        if target_hash != expected_hash:
            return VerifyResult(
                ok=False,
                error=f"hash mismatch for '{target_name}': expected {expected_hash}, got {target_hash}",
            )

        return VerifyResult(ok=True)

    def verify_root_signature(self, public_keys: list[bytes]) -> bool:
        """Verify root metadata has valid signatures meeting threshold.

        Delegates to the existing TUF root verification infrastructure.

        Args:
            public_keys: list of DER-encoded Ed25519 public keys.

        Returns:
            True if root signature verification passes.
        """
        if self._root is None:
            return False

        try:
            from scientificstate.modules.tuf.root import verify_root

            return verify_root(self._root, public_keys)
        except Exception:  # noqa: BLE001
            return False

    def _verify_root_structure(self) -> bool:
        """Check that root.json has the expected TUF structure."""
        if self._root is None:
            return False
        signed = self._root.get("signed", {})
        return (
            signed.get("_type") == "root"
            and "keys" in signed
            and "roles" in signed
        )

    def _is_expired_beyond_grace(self) -> bool:
        """Check if targets metadata is expired beyond the grace period.

        Returns:
            True if expired beyond grace (verification should FAIL).
            False if still within grace or not expired.
        """
        if self._targets is None:
            return True

        expires_str = self._targets.get("signed", {}).get("expires")
        if not expires_str:
            return True

        try:
            expires = datetime.fromisoformat(expires_str)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            delta = now - expires
            return delta.days > self.OFFLINE_GRACE_PERIOD_DAYS
        except (ValueError, TypeError):
            return True

    def verify_sigstore_bundle_cached(self, target_name: str) -> VerifyResult:
        """Verify that a Sigstore bundle is pre-cached for a target.

        Air-gapped exports must include Sigstore bundles alongside packages.
        This method checks that the bundle exists in the expected location
        relative to the package directory.

        Since M3, Sigstore is mandatory — missing bundles are a hard fail.

        Args:
            target_name: Target path (e.g. "polymer_science/1.0.0/module.tar.gz").

        Returns:
            VerifyResult(ok=True) if bundle is pre-cached.
            VerifyResult(ok=False, error=...) if missing.
        """
        # Derive package directory from target name
        # target_name format: "{domain_id}/{version}/module.tar.gz"
        parts = target_name.rsplit("/", maxsplit=1)
        if len(parts) != 2:
            return VerifyResult(ok=False, error=f"invalid target name format: {target_name}")

        pkg_rel = parts[0]  # e.g. "polymer_science/1.0.0"
        # Look for bundle relative to tuf_dir's parent (registry root)
        registry_dir = self._tuf_dir.parent
        bundle_path = registry_dir / "packages" / pkg_rel.replace("/", "/v", 1) / "sigstore.bundle.json"

        # Also try without "v" prefix
        if not bundle_path.exists():
            bundle_path = registry_dir / "packages" / pkg_rel / "sigstore.bundle.json"

        if not bundle_path.exists():
            return VerifyResult(
                ok=False,
                error=f"Sigstore bundle not pre-cached for {target_name} (mandatory since M3)",
            )

        # Verify bundle is valid JSON
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            if not isinstance(bundle, dict):
                return VerifyResult(ok=False, error="Sigstore bundle is not a JSON object")
        except (json.JSONDecodeError, OSError) as exc:
            return VerifyResult(ok=False, error=f"Sigstore bundle unreadable: {exc}")

        return VerifyResult(ok=True)

    @property
    def has_trust_chain(self) -> bool:
        """Whether a trust-chain.json was loaded."""
        return self._trust_chain is not None

    @property
    def root_meta(self) -> dict[str, Any] | None:
        """Return loaded root metadata (read-only access)."""
        return self._root

    @property
    def targets_meta(self) -> dict[str, Any] | None:
        """Return loaded targets metadata (read-only access)."""
        return self._targets

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        """Load a JSON file, returning None if missing or invalid."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
