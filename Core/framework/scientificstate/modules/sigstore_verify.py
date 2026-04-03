"""Sigstore keyless signing verification for module signatures.

Phase 2 onward: new modules should carry Sigstore signatures (Main_Source §12.3).
Fallback: Ed25519 trust chain from Phase 1 is always preserved.

The sigstore-python library is an optional dependency.  When it is not
installed, verification returns a graceful fallback result instead of
raising an exception.
"""
from __future__ import annotations

from typing import Any


def verify_sigstore_signature(
    artifact_bytes: bytes,
    signature_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Verify a Sigstore signature bundle.

    Args:
        artifact_bytes: the artifact content that was signed.
        signature_bundle: Sigstore bundle dict with certificate and signature.

    Returns:
        {
            "valid": bool,
            "signer_identity": str | None,   # ORCID or email
            "transparency_log": str | None,   # Rekor entry URL
            "reason": str,
        }
    """
    if not signature_bundle:
        return {
            "valid": False,
            "signer_identity": None,
            "transparency_log": None,
            "reason": "empty signature bundle",
        }

    try:
        import sigstore  # noqa: F401
        # Integration point for sigstore-python verification.
        # When the library is available, actual Rekor + Fulcio
        # verification would be performed here.
        return {
            "valid": False,
            "signer_identity": None,
            "transparency_log": None,
            "reason": "sigstore verification not yet implemented — fallback to Ed25519",
        }
    except ImportError:
        return {
            "valid": False,
            "signer_identity": None,
            "transparency_log": None,
            "reason": "sigstore library not available — fallback to Ed25519",
        }


def is_sigstore_available() -> bool:
    """Check if sigstore library is installed."""
    try:
        import sigstore  # noqa: F401
        return True
    except ImportError:
        return False
