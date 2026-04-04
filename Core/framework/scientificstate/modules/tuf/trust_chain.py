"""Cross-institutional TUF trust chain.

Extends the delegated targets model (Phase 3) to support multi-institution
trust relationships.  Each institution is registered as a TUF delegation
with its own signing key.  The trust chain verifies that:

  1. The institution's delegation exists in root targets.
  2. The institution's delegated-targets metadata is correctly signed.
  3. The module hash in delegated-targets matches the actual package.
  4. The institution has NOT been revoked.

Revocation propagates to federation peers via ``propagate_revocation()``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .delegated import (
    add_delegation,
    remove_delegation,
    verify_delegated_target,
)


class TrustChain:
    """Manages cross-institutional trust via TUF delegated targets.

    Args:
        root_targets_path: Path to the root targets.json file.
            If the file exists, it is loaded; otherwise an empty
            root targets metadata dict is created in memory.
    """

    def __init__(self, root_targets_path: Path) -> None:
        self._path = root_targets_path
        if root_targets_path.exists():
            self._root_targets: dict[str, Any] = json.loads(
                root_targets_path.read_text(encoding="utf-8"),
            )
        else:
            self._root_targets = {
                "signed": {
                    "_type": "targets",
                    "spec_version": "1.0.0",
                    "version": 1,
                    "targets": {},
                },
                "signatures": [],
            }

        # institution_id → trust metadata
        self._institutions: dict[str, dict[str, Any]] = {}
        # institution_id → delegated targets metadata (for verification)
        self._delegated_targets: dict[str, dict[str, Any]] = {}
        # revoked institution IDs
        self._revoked: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_institution_trust(
        self,
        institution_id: str,
        public_key: str,
        trust_level: str = "verified",
    ) -> dict[str, Any]:
        """Register an institution as a trusted delegate.

        Creates a TUF delegation entry so the institution can sign
        its own targets metadata for modules under its namespace.

        Args:
            institution_id: Unique institution identifier (used as
                delegation name and path prefix).
            public_key: Hex-encoded Ed25519 public key.
            trust_level: One of ``"verified"``, ``"provisional"``.

        Returns:
            Dict with delegation details (institution_id, trust_level,
            paths, delegation_name).
        """
        if institution_id in self._revoked:
            self._revoked.discard(institution_id)

        paths = [f"{institution_id}/*"]
        add_delegation(
            self._root_targets,
            name=institution_id,
            public_key_hex=public_key,
            paths=paths,
        )

        info = {
            "institution_id": institution_id,
            "trust_level": trust_level,
            "public_key": public_key,
            "paths": paths,
            "delegation_name": institution_id,
        }
        self._institutions[institution_id] = info
        return info

    def set_delegated_targets(
        self,
        institution_id: str,
        delegated_meta: dict[str, Any],
    ) -> None:
        """Attach delegated-targets metadata for an institution.

        Must be called before ``verify_cross_institutional()`` so the
        chain has the signed metadata to verify against.
        """
        self._delegated_targets[institution_id] = delegated_meta

    def verify_cross_institutional(
        self,
        module_name: str,
        module_hash: str,
        signing_institution: str,
    ) -> bool:
        """Verify a module through the cross-institutional trust chain.

        Steps:
          1. Check institution is not revoked.
          2. Check institution has a delegation in root targets.
          3. Verify delegated-targets signature + hash via TUF chain.

        Args:
            module_name: Target path (e.g. ``"polymer_science/1.0.0/module.tar.gz"``).
            module_hash: SHA-256 hex digest of the downloaded package.
            signing_institution: Institution ID that signed the module.

        Returns:
            True if the full chain verifies, False otherwise.
        """
        if signing_institution in self._revoked:
            return False

        if signing_institution not in self._institutions:
            return False

        delegated = self._delegated_targets.get(signing_institution)
        if delegated is None:
            return False

        return verify_delegated_target(
            target_path=module_name,
            actual_hash=module_hash,
            root_targets=self._root_targets,
            delegated_meta=delegated,
        )

    def revoke_institution(self, institution_id: str) -> None:
        """Revoke an institution's trust.

        Removes the TUF delegation and marks the institution as revoked.
        Any subsequent ``verify_cross_institutional()`` call for this
        institution will return False.
        """
        self._revoked.add(institution_id)
        remove_delegation(self._root_targets, institution_id)
        self._institutions.pop(institution_id, None)
        self._delegated_targets.pop(institution_id, None)

    def propagate_revocation(
        self,
        institution_id: str,
        federation_peers: list[str],
    ) -> dict[str, Any]:
        """Build a revocation notification for federation peers.

        This does NOT perform network calls — it returns a structured
        dict that the caller (portal API / CLI) sends to each peer.

        Args:
            institution_id: The revoked institution.
            federation_peers: List of peer institution IDs to notify.

        Returns:
            Dict with revocation details and per-peer notification entries.
        """
        if institution_id not in self._revoked:
            self.revoke_institution(institution_id)

        notifications = []
        for peer in federation_peers:
            notifications.append({
                "peer_institution_id": peer,
                "action": "revoke_trust",
                "revoked_institution_id": institution_id,
                "status": "pending",
            })

        return {
            "revoked_institution_id": institution_id,
            "notified_peers": len(notifications),
            "notifications": notifications,
        }

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def root_targets(self) -> dict[str, Any]:
        """Return a reference to the root targets metadata."""
        return self._root_targets

    @property
    def institutions(self) -> dict[str, dict[str, Any]]:
        """Return registered (non-revoked) institutions."""
        return dict(self._institutions)

    @property
    def revoked(self) -> set[str]:
        """Return the set of revoked institution IDs."""
        return set(self._revoked)

    def save(self) -> None:
        """Persist root targets to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._root_targets, indent=2, sort_keys=True),
            encoding="utf-8",
        )
