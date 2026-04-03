"""
Module manifest verifier — Ed25519 signature verification.

CRITICAL RULE: unsigned manifest (empty or None signature_hex) is ALWAYS rejected.
There is no override, no bypass, no exception to this rule.

Constitutional rule: the module ecosystem trust chain requires every module to
carry a valid cryptographic signature before installation is permitted.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class VerifyResult:
    """Result of a manifest signature verification.

    valid: True only if the signature is cryptographically valid.
    reason: human-readable explanation (always present).
    """

    valid: bool
    reason: str


def verify_manifest(
    manifest_bytes: bytes,
    signature_hex: str | None,
    public_key: bytes,
) -> VerifyResult:
    """Verify a module manifest signature.

    Computes SHA-256(manifest_bytes) and verifies the Ed25519 signature.

    Args:
        manifest_bytes: raw manifest content (must match what was signed)
        signature_hex: hex-encoded signature from signer.sign_manifest()
                       None or empty string → unconditional rejection.
        public_key: DER-encoded Ed25519 public key (from generate_keypair)

    Returns:
        VerifyResult(valid=True, reason="signature valid") on success.
        VerifyResult(valid=False, reason="...") on any failure.

    RULE: there is no override. Unsigned manifests are ALWAYS rejected.
    """
    # ── Hard rule: unsigned manifest rejected unconditionally ─────────────
    if not signature_hex:
        return VerifyResult(valid=False, reason="unsigned manifest rejected")

    try:
        signature_bytes = bytes.fromhex(signature_hex)
    except ValueError:
        return VerifyResult(valid=False, reason="signature_hex is not valid hex")

    try:
        from cryptography.hazmat.primitives.serialization import load_der_public_key
        from cryptography.exceptions import InvalidSignature

        digest = hashlib.sha256(manifest_bytes).digest()
        pub = load_der_public_key(public_key)
        pub.verify(signature_bytes, digest)
        return VerifyResult(valid=True, reason="signature valid")

    except InvalidSignature:
        return VerifyResult(valid=False, reason="signature verification failed")
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(valid=False, reason=f"verification error: {exc}")
