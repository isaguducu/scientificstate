"""
Module revocation checker — checks whether a module version has been revoked.

Revocation list format:
  [{"domain_id": "...", "version": "...", "reason": "...", "revoked_at": "..."}, ...]

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations


def check_revocation(
    domain_id: str,
    version: str,
    revocation_list: list[dict],
) -> bool:
    """Check whether a specific module version is revoked.

    Args:
        domain_id: the domain module identifier
        version: SemVer version string (e.g. "1.0.0")
        revocation_list: list of revocation records
                         Each record must have "domain_id" and "version" keys.

    Returns:
        True  — module is revoked (must not be installed/used)
        False — module is active (not in revocation list)
    """
    for entry in revocation_list:
        if (
            isinstance(entry, dict)
            and entry.get("domain_id") == domain_id
            and entry.get("version") == version
        ):
            return True
    return False
