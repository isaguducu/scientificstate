"""Threshold signing — multi-key requirement for TUF metadata.

M2-early: single key (threshold=1).
M2-late:  2-of-3 key requirement for root rotation and critical targets.
"""
from __future__ import annotations

import json

from scientificstate.modules.signer import sign_manifest
from scientificstate.modules.tuf.root import _key_id


def threshold_sign(
    metadata: dict,
    private_keys: list[bytes],
    public_keys: list[bytes],
    threshold: int = 2,
) -> dict:
    """Sign metadata with multiple keys.

    Args:
        metadata: TUF metadata dict (modified in place).
        private_keys: list of DER-encoded Ed25519 private keys.
        public_keys: list of DER-encoded Ed25519 public keys (matching order).
        threshold: minimum signatures required.

    Returns:
        The same metadata dict with signatures appended.

    Raises:
        ValueError: if fewer keys provided than threshold.
    """
    if len(private_keys) < threshold:
        msg = f"need at least {threshold} keys to meet threshold, got {len(private_keys)}"
        raise ValueError(msg)

    signed_bytes = json.dumps(metadata["signed"], sort_keys=True).encode()

    for priv, pub in zip(private_keys, public_keys):
        sig_hex = sign_manifest(signed_bytes, priv)
        kid = _key_id(pub)
        metadata["signatures"].append({"keyid": kid, "sig": sig_hex})

    return metadata


def verify_threshold(
    metadata: dict,
    public_keys: list[bytes],
    threshold: int = 2,
) -> bool:
    """Verify that metadata has at least *threshold* valid signatures.

    Args:
        metadata: TUF metadata dict.
        public_keys: list of DER-encoded Ed25519 public keys.
        threshold: minimum valid signatures required.

    Returns:
        True if at least *threshold* signatures are valid.
    """
    from scientificstate.modules.verifier import verify_manifest

    signed_bytes = json.dumps(metadata["signed"], sort_keys=True).encode()

    key_map: dict[str, bytes] = {}
    for pub_der in public_keys:
        kid = _key_id(pub_der)
        key_map[kid] = pub_der

    valid_count = 0
    seen_keyids: set[str] = set()

    for sig_entry in metadata.get("signatures", []):
        kid = sig_entry["keyid"]
        if kid in seen_keyids:
            continue  # count each key at most once
        pub_der = key_map.get(kid)
        if pub_der is None:
            continue
        result = verify_manifest(signed_bytes, sig_entry["sig"], pub_der)
        if result.valid:
            valid_count += 1
            seen_keyids.add(kid)

    return valid_count >= threshold
