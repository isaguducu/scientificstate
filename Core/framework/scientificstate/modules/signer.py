"""
Module manifest signer — Ed25519 digital signatures.

Signs a SHA-256 hash of manifest bytes with an Ed25519 private key.
Used during module publication to prove authorship and prevent tampering.

Constitutional rule: unsigned manifests are unconditionally rejected.
There is no override mechanism — this is enforced in verifier.py.
"""
from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a new Ed25519 keypair.

    Returns:
        (private_key_bytes, public_key_bytes) — raw 32-byte seeds in DER format.
        Both as bytes, suitable for storage and later use with sign_manifest / verify_manifest.
    """
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo,
    )
    return private_bytes, public_bytes


def sign_manifest(manifest_bytes: bytes, private_key: bytes) -> str:
    """Sign a module manifest.

    Computes SHA-256(manifest_bytes) then signs the digest with Ed25519.

    Args:
        manifest_bytes: raw manifest content (e.g. JSON bytes)
        private_key: DER-encoded Ed25519 private key (from generate_keypair)

    Returns:
        hex-encoded signature string (128 hex chars = 64 bytes)
    """
    from cryptography.hazmat.primitives.serialization import load_der_private_key

    digest = hashlib.sha256(manifest_bytes).digest()
    priv = load_der_private_key(private_key, password=None)
    signature = priv.sign(digest)
    return signature.hex()
