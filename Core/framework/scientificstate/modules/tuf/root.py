"""TUF root metadata generation and validation.

Root metadata is the trust anchor of the TUF chain.  It declares which
public keys are authorised for each role (root, targets) and the minimum
number of signatures (threshold) required.

Key format convention:
    The rest of the ScientificState framework stores Ed25519 keys as
    DER-encoded bytes (see signer.py / verifier.py).  TUF metadata stores
    raw 32-byte public-key hex.  Conversion happens internally here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
)


# ── Key helpers ───────────────────────────────────────────────────────────────

def _raw_pub_hex(pub_key_der: bytes) -> str:
    """Extract raw 32-byte Ed25519 public key as hex from DER encoding."""
    pub = load_der_public_key(pub_key_der)
    return pub.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def _key_id(pub_key_der: bytes) -> str:
    """Compute TUF key ID as SHA-256 of canonical key JSON representation."""
    pub_hex = _raw_pub_hex(pub_key_der)
    canonical = json.dumps(
        {"keytype": "ed25519", "scheme": "ed25519", "keyval": {"public": pub_hex}},
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ── Root generation ───────────────────────────────────────────────────────────

def generate_root(
    root_pubkey: bytes,
    version: int = 1,
    expiry_days: int = 365,
) -> dict[str, Any]:
    """Generate a TUF root.json metadata dict.

    Args:
        root_pubkey: DER-encoded Ed25519 public key.
        version: metadata version number.
        expiry_days: days until expiry.

    Returns:
        TUF root metadata dict with empty signatures list.
    """
    now = datetime.now(tz=timezone.utc)
    expires = now + timedelta(days=expiry_days)
    pub_hex = _raw_pub_hex(root_pubkey)
    kid = _key_id(root_pubkey)

    return {
        "signed": {
            "_type": "root",
            "spec_version": "1.0.0",
            "version": version,
            "expires": expires.isoformat(),
            "keys": {
                kid: {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyval": {"public": pub_hex},
                }
            },
            "roles": {
                "root": {
                    "keyids": [kid],
                    "threshold": 1,
                },
                "targets": {
                    "keyids": [kid],
                    "threshold": 1,
                },
            },
        },
        "signatures": [],
    }


# ── Signing ───────────────────────────────────────────────────────────────────

def sign_root(
    root_meta: dict,
    private_key: bytes,
    public_key: bytes,
) -> dict:
    """Sign root metadata with an Ed25519 private key.

    Args:
        root_meta: TUF root metadata dict (modified in place).
        private_key: DER-encoded Ed25519 private key.
        public_key: DER-encoded Ed25519 public key (for key ID computation).

    Returns:
        The same root_meta dict with signature appended.
    """
    from scientificstate.modules.signer import sign_manifest

    signed_bytes = json.dumps(root_meta["signed"], sort_keys=True).encode()
    sig_hex = sign_manifest(signed_bytes, private_key)
    kid = _key_id(public_key)

    root_meta["signatures"].append({"keyid": kid, "sig": sig_hex})
    return root_meta


# ── Verification ──────────────────────────────────────────────────────────────

def verify_root(root_meta: dict, public_keys: list[bytes]) -> bool:
    """Verify root metadata has valid signatures meeting threshold.

    Args:
        root_meta: TUF root metadata dict.
        public_keys: list of DER-encoded Ed25519 public keys.

    Returns:
        True if valid signature count >= threshold for the root role.
    """
    from scientificstate.modules.verifier import verify_manifest

    signed_bytes = json.dumps(root_meta["signed"], sort_keys=True).encode()
    threshold = root_meta["signed"]["roles"]["root"]["threshold"]
    valid_keyids = set(root_meta["signed"]["roles"]["root"]["keyids"])

    valid_count = 0
    for sig_entry in root_meta.get("signatures", []):
        if sig_entry["keyid"] not in valid_keyids:
            continue
        for pub_der in public_keys:
            if _key_id(pub_der) == sig_entry["keyid"]:
                result = verify_manifest(signed_bytes, sig_entry["sig"], pub_der)
                if result.valid:
                    valid_count += 1
                    break

    return valid_count >= threshold
