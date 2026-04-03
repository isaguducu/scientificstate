"""TUF update checker — validates root chain and checks for new targets.

Used by the daemon / CLI to discover available module updates without
trusting the transport layer.  The root chain validation ensures that
even if the registry is compromised, only metadata signed by trusted
keys is accepted.
"""
from __future__ import annotations

import json
from typing import Any

from scientificstate.modules.tuf.root import _key_id


def check_for_updates(
    current_targets: dict[str, Any],
    remote_targets: dict[str, Any],
) -> dict[str, Any]:
    """Compare current and remote targets metadata to find updates.

    Returns:
        {
            "targets_updated": bool,
            "new_targets": [target_path, ...],
            "updated_targets": [target_path, ...],
        }
    """
    current = current_targets["signed"]["targets"]
    remote = remote_targets["signed"]["targets"]

    new_targets = [p for p in remote if p not in current]
    updated_targets = [
        p for p in remote
        if p in current and remote[p]["hashes"] != current[p]["hashes"]
    ]

    return {
        "targets_updated": bool(new_targets or updated_targets),
        "new_targets": new_targets,
        "updated_targets": updated_targets,
    }


def validate_root_chain(
    current_root: dict[str, Any],
    new_root: dict[str, Any],
    public_keys: list[bytes],
) -> bool:
    """Validate root rotation: new root must be signed by threshold of
    keys trusted by the CURRENT root (trust on first use).

    Args:
        current_root: currently trusted TUF root metadata.
        new_root: candidate new root metadata.
        public_keys: list of DER-encoded Ed25519 public keys.

    Returns:
        True if new root version > current AND signed by current root's
        threshold of trusted keys.
    """
    current_version = current_root["signed"]["version"]
    new_version = new_root["signed"]["version"]

    if new_version <= current_version:
        return False

    current_root_keyids = set(current_root["signed"]["roles"]["root"]["keyids"])
    current_threshold = current_root["signed"]["roles"]["root"]["threshold"]

    signed_bytes = json.dumps(new_root["signed"], sort_keys=True).encode()

    from scientificstate.modules.verifier import verify_manifest

    valid_count = 0
    for sig_entry in new_root.get("signatures", []):
        if sig_entry["keyid"] not in current_root_keyids:
            continue
        for pub_der in public_keys:
            if _key_id(pub_der) == sig_entry["keyid"]:
                result = verify_manifest(signed_bytes, sig_entry["sig"], pub_der)
                if result.valid:
                    valid_count += 1
                    break

    return valid_count >= current_threshold
