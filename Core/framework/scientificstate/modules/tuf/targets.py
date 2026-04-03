"""TUF targets metadata — maps module versions to expected hashes.

Each published module version is registered as a TUF target with its
SHA-256 hash and size.  During install the manager checks the downloaded
package hash against the targets metadata before writing to disk.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _expiry_iso(days: int) -> str:
    """Return ISO 8601 expiry timestamp *days* from now."""
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def generate_targets(
    modules: list[dict[str, Any]],
    version: int = 1,
    expiry_days: int = 90,
) -> dict[str, Any]:
    """Generate TUF targets.json metadata.

    Args:
        modules: list of dicts with keys:
            module_id (str), version (str), tarball_hash (str), size (int, optional).
        version: metadata version number.
        expiry_days: days until expiry.

    Returns:
        TUF targets metadata dict with empty signatures list.
    """
    targets: dict[str, Any] = {}
    for m in modules:
        target_path = f"{m['module_id']}/{m['version']}/module.tar.gz"
        targets[target_path] = {
            "length": m.get("size", 0),
            "hashes": {
                "sha256": m["tarball_hash"],
            },
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


def verify_target_hash(
    target_path: str,
    actual_hash: str,
    targets_meta: dict[str, Any],
) -> bool:
    """Verify downloaded tarball hash matches targets.json expectation.

    Args:
        target_path: e.g. "polymer_science/1.0.0/module.tar.gz"
        actual_hash: SHA-256 hex digest of the downloaded tarball.
        targets_meta: TUF targets metadata dict.

    Returns:
        True if hashes match, False if mismatch or target unknown.
    """
    target_info = targets_meta["signed"]["targets"].get(target_path)
    if not target_info:
        return False
    expected_hash = target_info["hashes"].get("sha256")
    return expected_hash == actual_hash
