"""TUF delegated targets — institutional publisher key delegation.

Delegated targets allow institutional publishers to sign their own
targets metadata without requiring the root targets key.  This
implements the TUF delegation model:

  root targets → delegated targets → target hash verification

Key ceremony documentation:
  1. Root key holder creates a delegation for publisher X.
  2. Publisher X signs a delegated-targets.json listing their modules.
  3. During install, the chain is verified:
     a. Root targets must contain the delegation entry.
     b. Delegation's public key must verify the delegated-targets signature.
     c. Target hash in delegated-targets must match the actual package.

Key rotation:
  - Call ``rotate_delegation_key()`` with the old and new public keys.
  - Root targets must be re-signed after rotation.
  - Clients must refresh metadata to pick up the new key.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any


def _expiry_iso(days: int) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def _key_id(public_key_hex: str) -> str:
    """Compute a TUF key ID from a hex-encoded public key."""
    canonical = json.dumps(
        {"keytype": "ed25519", "scheme": "ed25519", "keyval": {"public": public_key_hex}},
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Delegation management
# ---------------------------------------------------------------------------


def add_delegation(
    root_targets: dict[str, Any],
    name: str,
    public_key_hex: str,
    paths: list[str],
    *,
    threshold: int = 1,
) -> dict[str, Any]:
    """Add a delegation entry to root targets metadata.

    Args:
        root_targets: mutable root targets metadata dict (with "signed" key).
        name: delegation name (e.g. "university-of-tokyo").
        public_key_hex: hex-encoded Ed25519 public key of the delegate.
        paths: glob patterns the delegate may sign (e.g. ["polymer_science/*"]).
        threshold: number of signatures required (default 1).

    Returns:
        The modified root_targets (same reference, mutated in place).
    """
    signed = root_targets["signed"]
    kid = _key_id(public_key_hex)

    # Register key
    keys = signed.setdefault("delegations", {}).setdefault("keys", {})
    keys[kid] = {
        "keytype": "ed25519",
        "scheme": "ed25519",
        "keyval": {"public": public_key_hex},
    }

    # Register role
    roles = signed["delegations"].setdefault("roles", [])

    # Replace existing delegation with same name
    roles[:] = [r for r in roles if r["name"] != name]
    roles.append({
        "name": name,
        "keyids": [kid],
        "paths": paths,
        "threshold": threshold,
        "terminating": True,
    })

    return root_targets


def remove_delegation(
    root_targets: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    """Remove a delegation entry from root targets metadata."""
    signed = root_targets["signed"]
    delegations = signed.get("delegations", {})
    roles = delegations.get("roles", [])

    # Find key IDs to remove
    keyids_to_remove: set[str] = set()
    for role in roles:
        if role["name"] == name:
            keyids_to_remove.update(role.get("keyids", []))

    # Remove the role
    roles[:] = [r for r in roles if r["name"] != name]

    # Remove orphaned keys (not referenced by any remaining role)
    used_keyids: set[str] = set()
    for role in roles:
        used_keyids.update(role.get("keyids", []))
    keys = delegations.get("keys", {})
    for kid in keyids_to_remove - used_keyids:
        keys.pop(kid, None)

    return root_targets


def rotate_delegation_key(
    root_targets: dict[str, Any],
    name: str,
    new_public_key_hex: str,
) -> dict[str, Any]:
    """Rotate the signing key for a delegation.

    Removes the old key and registers the new one.
    Root targets must be re-signed after this operation.
    """
    signed = root_targets["signed"]
    delegations = signed.get("delegations", {})
    roles = delegations.get("roles", [])
    keys = delegations.get("keys", {})

    new_kid = _key_id(new_public_key_hex)

    for role in roles:
        if role["name"] == name:
            old_keyids = role["keyids"]
            # Remove old keys
            for kid in old_keyids:
                keys.pop(kid, None)
            # Set new key
            role["keyids"] = [new_kid]
            keys[new_kid] = {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {"public": new_public_key_hex},
            }
            break

    return root_targets


# ---------------------------------------------------------------------------
# Delegated targets generation
# ---------------------------------------------------------------------------


def generate_delegated_targets(
    modules: list[dict[str, Any]],
    version: int = 1,
    expiry_days: int = 90,
) -> dict[str, Any]:
    """Generate a delegated-targets.json metadata dict.

    Same shape as regular TUF targets but intended to be signed
    by the delegated publisher's key (not the root targets key).

    Args:
        modules: list of dicts with module_id, version, tarball_hash, size.
        version: metadata version number.
        expiry_days: days until expiry.
    """
    targets: dict[str, Any] = {}
    for m in modules:
        target_path = f"{m['module_id']}/{m['version']}/module.tar.gz"
        targets[target_path] = {
            "length": m.get("size", 0),
            "hashes": {"sha256": m["tarball_hash"]},
        }

    return {
        "signed": {
            "_type": "targets",
            "spec_version": "1.0.0",
            "version": version,
            "expires": _expiry_iso(expiry_days),
            "targets": targets,
        },
        "signatures": [],
    }


def sign_delegated_targets(
    delegated_meta: dict[str, Any],
    private_key: bytes,
) -> dict[str, Any]:
    """Sign delegated targets metadata with the delegate's private key.

    Args:
        delegated_meta: delegated targets metadata dict.
        private_key: DER-encoded Ed25519 private key bytes.

    Returns:
        The modified delegated_meta with signature appended.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_der_private_key

    from cryptography.hazmat.primitives.serialization import Encoding as _Enc, PublicFormat as _PubFmt

    canonical = json.dumps(delegated_meta["signed"], sort_keys=True).encode()
    key = load_der_private_key(private_key, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("expected Ed25519 private key")

    sig_bytes = key.sign(canonical)
    pub_bytes = key.public_key().public_bytes(_Enc.Raw, _PubFmt.Raw)
    kid = _key_id(pub_bytes.hex())

    delegated_meta["signatures"].append({
        "keyid": kid,
        "sig": sig_bytes.hex(),
    })
    return delegated_meta


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _match_path(target_path: str, patterns: list[str]) -> bool:
    """Check if target_path matches any delegation path pattern.

    Patterns use simple glob: "domain/*" matches "domain/1.0.0/module.tar.gz".
    """
    for pattern in patterns:
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if target_path.startswith(prefix + "/"):
                return True
        elif pattern == target_path:
            return True
    return False


def verify_delegated_target(
    target_path: str,
    actual_hash: str,
    root_targets: dict[str, Any],
    delegated_meta: dict[str, Any],
) -> bool:
    """Verify a target through the delegated chain.

    Steps:
      1. Find the delegation in root_targets that covers target_path.
      2. Verify delegated_meta signature against the delegation's public key.
      3. Check that target_path hash in delegated_meta matches actual_hash.

    Args:
        target_path: e.g. "polymer_science/1.0.0/module.tar.gz"
        actual_hash: SHA-256 hex digest of the downloaded package.
        root_targets: root targets metadata (must contain delegations).
        delegated_meta: delegated targets metadata (signed by delegate key).

    Returns:
        True if the full chain verifies, False otherwise.
    """
    signed = root_targets.get("signed", {})
    delegations = signed.get("delegations", {})
    roles = delegations.get("roles", [])
    keys = delegations.get("keys", {})

    # Step 1: Find delegation covering this target path
    matching_role = None
    for role in roles:
        if _match_path(target_path, role.get("paths", [])):
            matching_role = role
            break

    if matching_role is None:
        return False

    # Step 2: Verify delegated_meta signature
    canonical = json.dumps(delegated_meta["signed"], sort_keys=True).encode()
    signatures = delegated_meta.get("signatures", [])

    verified_count = 0
    for sig_entry in signatures:
        kid = sig_entry["keyid"]
        if kid not in matching_role.get("keyids", []):
            continue
        key_info = keys.get(kid)
        if not key_info:
            continue

        pub_hex = key_info["keyval"]["public"]
        pub_bytes = bytes.fromhex(pub_hex)

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey as _Pub,
            )

            pub_key = _Pub.from_public_bytes(pub_bytes)
            sig_bytes = bytes.fromhex(sig_entry["sig"])
            pub_key.verify(sig_bytes, canonical)
            verified_count += 1
        except Exception:  # noqa: BLE001
            continue

    threshold = matching_role.get("threshold", 1)
    if verified_count < threshold:
        return False

    # Step 3: Verify target hash
    dtargets = delegated_meta.get("signed", {}).get("targets", {})
    target_info = dtargets.get(target_path)
    if not target_info:
        return False

    expected_hash = target_info.get("hashes", {}).get("sha256")
    return expected_hash == actual_hash
