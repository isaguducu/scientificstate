"""Tests for Sigstore-only mandatory enforcement (M3 S16.2).

M3 rule: Sigstore bundle MUST be present.
Ed25519 alone is INSUFFICIENT — hard block, no override.
"""
from __future__ import annotations

from scientificstate.modules.sigstore_verify import (
    is_sigstore_available,
    verify_sigstore_signature,
)


# ── Hard block: missing bundle ──────────────────────────────────────────────


def test_none_bundle_hard_block():
    """None bundle → hard block (M3 S16.2)."""
    result = verify_sigstore_signature(b"artifact", None)
    assert result["valid"] is False
    assert "hard block" in result["reason"].lower() or "missing" in result["reason"].lower()


def test_empty_bundle_hard_block():
    """Empty dict bundle → hard block."""
    result = verify_sigstore_signature(b"artifact", {})
    assert result["valid"] is False
    assert "missing" in result["reason"].lower()


def test_ed25519_alone_insufficient():
    """Ed25519 sig without Sigstore bundle → rejected.

    This is the key M3 change: even if Ed25519 verification passes,
    the module is rejected if Sigstore bundle is missing.
    """
    result = verify_sigstore_signature(b"artifact", None)
    assert result["valid"] is False
    assert "insufficient" in result["reason"].lower() or "missing" in result["reason"].lower()


# ── Hard block: incomplete bundle ───────────────────────────────────────────


def test_bundle_missing_cert():
    """Bundle without cert → rejected."""
    result = verify_sigstore_signature(b"artifact", {"sig": "abc123"})
    assert result["valid"] is False
    assert "incomplete" in result["reason"].lower() or "missing" in result["reason"].lower()


def test_bundle_missing_sig():
    """Bundle without sig → rejected."""
    result = verify_sigstore_signature(b"artifact", {"cert": "some-cert"})
    assert result["valid"] is False
    assert "incomplete" in result["reason"].lower() or "missing" in result["reason"].lower()


# ── Valid bundle acceptance ─────────────────────────────────────────────────


def test_valid_bundle_accepted():
    """Structurally valid bundle → accepted (dev mode or with library)."""
    bundle = {
        "cert": "-----BEGIN CERTIFICATE-----\nMIIB...\n-----END CERTIFICATE-----",
        "sig": "deadbeef0123456789",
        "identity": "researcher@university.edu",
        "rekor_url": "https://rekor.sigstore.dev/api/v1/log/entries/abc123",
    }
    result = verify_sigstore_signature(b"artifact content", bundle)
    assert result["valid"] is True
    assert result["signer_identity"] == "researcher@university.edu"
    assert result["transparency_log"] == "https://rekor.sigstore.dev/api/v1/log/entries/abc123"


def test_minimal_valid_bundle():
    """Minimal bundle with just cert + sig → accepted."""
    bundle = {"cert": "CERT", "sig": "SIG"}
    result = verify_sigstore_signature(b"data", bundle)
    assert result["valid"] is True


# ── Response format ─────────────────────────────────────────────────────────


def test_response_always_has_required_keys():
    """All responses must have valid, signer_identity, transparency_log, reason."""
    for bundle in [None, {}, {"cert": "c", "sig": "s"}]:
        result = verify_sigstore_signature(b"x", bundle)
        assert set(result.keys()) == {"valid", "signer_identity", "transparency_log", "reason"}


def test_is_sigstore_available_returns_bool():
    assert isinstance(is_sigstore_available(), bool)


# ── Manager integration: Sigstore mandatory blocks install ──────────────────


def test_manager_rejects_without_sigstore_bundle():
    """Manager with sigstore_required=True rejects modules without bundle."""
    import hashlib
    import json
    import tempfile
    from pathlib import Path

    from scientificstate.modules.manager import ModuleManager
    from scientificstate.modules.signer import generate_keypair, sign_manifest

    package_bytes = b"test package"
    checksum = hashlib.sha256(package_bytes).hexdigest()
    canonical = {"domain_id": "test", "version": "0.1.0", "package_sha256": checksum, "name": "test"}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv)
    sig = {"algorithm": "ed25519", "public_key_id": "k", "value": sig_hex}
    manifest = {**canonical, "signature": sig}
    # NO sigstore_bundle field!
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        mgr.set_sigstore_required(True)
        result = mgr.install(manifest_bytes, package_bytes, pub)
        assert result.success is False
        assert "Sigstore" in (result.error or "")


def test_manager_accepts_with_sigstore_bundle():
    """Manager with sigstore_required=True accepts modules WITH valid bundle."""
    import hashlib
    import json
    import tempfile
    from pathlib import Path

    from scientificstate.modules.manager import ModuleManager
    from scientificstate.modules.signer import generate_keypair, sign_manifest

    package_bytes = b"test package with sigstore"
    checksum = hashlib.sha256(package_bytes).hexdigest()
    canonical = {"domain_id": "test_sig", "version": "0.1.0", "package_sha256": checksum, "name": "test_sig"}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    # sigstore_bundle must be part of canonical (manager strips only "signature")
    canonical["sigstore_bundle"] = {"cert": "CERT", "sig": "SIG", "identity": "test@sci.org"}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv)
    sig = {"algorithm": "ed25519", "public_key_id": "k", "value": sig_hex}
    manifest = {**canonical, "signature": sig}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        mgr.set_sigstore_required(True)
        result = mgr.install(manifest_bytes, package_bytes, pub)
        assert result.success is True


def test_manager_sigstore_not_required_allows_without_bundle():
    """Manager with sigstore_required=False allows modules without bundle (M2 compat)."""
    import hashlib
    import json
    import tempfile
    from pathlib import Path

    from scientificstate.modules.manager import ModuleManager
    from scientificstate.modules.signer import generate_keypair, sign_manifest

    package_bytes = b"test no sigstore"
    checksum = hashlib.sha256(package_bytes).hexdigest()
    canonical = {"domain_id": "nosig", "version": "0.1.0", "package_sha256": checksum, "name": "nosig"}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv)
    sig = {"algorithm": "ed25519", "public_key_id": "k", "value": sig_hex}
    manifest = {**canonical, "signature": sig}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        mgr.set_sigstore_required(False)
        result = mgr.install(manifest_bytes, package_bytes, pub)
        assert result.success is True
