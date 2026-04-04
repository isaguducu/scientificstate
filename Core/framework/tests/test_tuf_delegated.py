"""Tests for TUF delegated targets — delegation, signing, verification."""
from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

from scientificstate.modules.tuf.delegated import (
    add_delegation,
    generate_delegated_targets,
    remove_delegation,
    rotate_delegation_key,
    sign_delegated_targets,
    verify_delegated_target,
    _key_id,
)
from scientificstate.modules.tuf.targets import generate_targets


def _make_keypair() -> tuple[bytes, str]:
    """Generate Ed25519 keypair, return (private_der, public_hex)."""
    priv = Ed25519PrivateKey.generate()
    priv_der = priv.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return priv_der, pub_hex


def _make_root_targets() -> dict:
    """Create a minimal root targets metadata dict."""
    return generate_targets([], version=1)


# ── add_delegation ──────────────────────────────────────────────────────────


def test_add_delegation_creates_keys_and_roles():
    root = _make_root_targets()
    _, pub_hex = _make_keypair()
    add_delegation(root, "uni-tokyo", pub_hex, ["polymer_science/*"])

    delegations = root["signed"]["delegations"]
    assert len(delegations["keys"]) == 1
    assert len(delegations["roles"]) == 1
    assert delegations["roles"][0]["name"] == "uni-tokyo"
    assert delegations["roles"][0]["paths"] == ["polymer_science/*"]


def test_add_delegation_key_id_matches():
    root = _make_root_targets()
    _, pub_hex = _make_keypair()
    add_delegation(root, "pub1", pub_hex, ["*"])

    kid = _key_id(pub_hex)
    assert kid in root["signed"]["delegations"]["keys"]
    assert kid in root["signed"]["delegations"]["roles"][0]["keyids"]


def test_add_multiple_delegations():
    root = _make_root_targets()
    _, pub1 = _make_keypair()
    _, pub2 = _make_keypair()

    add_delegation(root, "org-a", pub1, ["genomics/*"])
    add_delegation(root, "org-b", pub2, ["climate/*"])

    roles = root["signed"]["delegations"]["roles"]
    assert len(roles) == 2
    names = {r["name"] for r in roles}
    assert names == {"org-a", "org-b"}


def test_add_delegation_replaces_existing_same_name():
    root = _make_root_targets()
    _, pub1 = _make_keypair()
    _, pub2 = _make_keypair()

    add_delegation(root, "org-a", pub1, ["old/*"])
    add_delegation(root, "org-a", pub2, ["new/*"])

    roles = root["signed"]["delegations"]["roles"]
    assert len(roles) == 1
    assert roles[0]["paths"] == ["new/*"]


# ── remove_delegation ───────────────────────────────────────────────────────


def test_remove_delegation():
    root = _make_root_targets()
    _, pub_hex = _make_keypair()
    add_delegation(root, "to-remove", pub_hex, ["*"])

    remove_delegation(root, "to-remove")
    assert len(root["signed"]["delegations"]["roles"]) == 0
    assert len(root["signed"]["delegations"]["keys"]) == 0


def test_remove_nonexistent_is_noop():
    root = _make_root_targets()
    remove_delegation(root, "does-not-exist")
    # Should not raise


# ── rotate_delegation_key ───────────────────────────────────────────────────


def test_rotate_key():
    root = _make_root_targets()
    _, old_pub = _make_keypair()
    _, new_pub = _make_keypair()

    add_delegation(root, "org", old_pub, ["*"])
    rotate_delegation_key(root, "org", new_pub)

    keys = root["signed"]["delegations"]["keys"]
    new_kid = _key_id(new_pub)
    old_kid = _key_id(old_pub)
    assert new_kid in keys
    assert old_kid not in keys


# ── generate_delegated_targets ──────────────────────────────────────────────


def test_generate_delegated_targets_structure():
    modules = [{"module_id": "polymer", "version": "1.0.0", "tarball_hash": "abc123"}]
    meta = generate_delegated_targets(modules)
    assert meta["signed"]["_type"] == "targets"
    assert "polymer/1.0.0/module.tar.gz" in meta["signed"]["targets"]


def test_generate_delegated_targets_empty():
    meta = generate_delegated_targets([])
    assert meta["signed"]["targets"] == {}
    assert meta["signatures"] == []


# ── sign_delegated_targets ──────────────────────────────────────────────────


def test_sign_delegated_targets():
    priv_der, pub_hex = _make_keypair()
    modules = [{"module_id": "test", "version": "0.1.0", "tarball_hash": "deadbeef"}]
    meta = generate_delegated_targets(modules)
    sign_delegated_targets(meta, priv_der)

    assert len(meta["signatures"]) == 1
    assert "keyid" in meta["signatures"][0]
    assert "sig" in meta["signatures"][0]


# ── verify_delegated_target ─────────────────────────────────────────────────


def _setup_delegated_chain(domain_id="polymer_science", version="1.0.0"):
    """Build a complete delegated chain for testing."""
    priv_der, pub_hex = _make_keypair()

    # Root targets with delegation
    root = _make_root_targets()
    add_delegation(root, "publisher", pub_hex, [f"{domain_id}/*"])

    # Package
    package = b"test package content"
    pkg_hash = hashlib.sha256(package).hexdigest()

    # Delegated targets
    delegated = generate_delegated_targets([{
        "module_id": domain_id,
        "version": version,
        "tarball_hash": pkg_hash,
        "size": len(package),
    }])
    sign_delegated_targets(delegated, priv_der)

    target_path = f"{domain_id}/{version}/module.tar.gz"
    return root, delegated, target_path, pkg_hash


def test_verify_delegated_target_valid():
    root, delegated, target_path, pkg_hash = _setup_delegated_chain()
    assert verify_delegated_target(target_path, pkg_hash, root, delegated) is True


def test_verify_delegated_target_wrong_hash():
    root, delegated, target_path, _ = _setup_delegated_chain()
    assert verify_delegated_target(target_path, "wrong_hash", root, delegated) is False


def test_verify_delegated_target_no_delegation():
    """Target path not covered by any delegation → False."""
    root, delegated, _, pkg_hash = _setup_delegated_chain()
    assert verify_delegated_target("unknown/1.0.0/module.tar.gz", pkg_hash, root, delegated) is False


def test_verify_delegated_target_wrong_signature():
    """Delegated targets signed with wrong key → False."""
    _, pub_hex = _make_keypair()
    wrong_priv, _ = _make_keypair()

    root = _make_root_targets()
    add_delegation(root, "pub", pub_hex, ["test/*"])

    package = b"pkg"
    pkg_hash = hashlib.sha256(package).hexdigest()

    delegated = generate_delegated_targets([{
        "module_id": "test",
        "version": "1.0.0",
        "tarball_hash": pkg_hash,
    }])
    # Sign with WRONG key
    sign_delegated_targets(delegated, wrong_priv)

    assert verify_delegated_target("test/1.0.0/module.tar.gz", pkg_hash, root, delegated) is False


def test_verify_delegated_target_unsigned():
    """Unsigned delegated targets → False."""
    _, pub_hex = _make_keypair()
    root = _make_root_targets()
    add_delegation(root, "pub", pub_hex, ["test/*"])

    delegated = generate_delegated_targets([{
        "module_id": "test",
        "version": "1.0.0",
        "tarball_hash": "abc",
    }])
    # NOT signed
    assert verify_delegated_target("test/1.0.0/module.tar.gz", "abc", root, delegated) is False


def test_verify_delegated_target_empty_root():
    """Empty root targets (no delegations) → False."""
    root = _make_root_targets()
    delegated = generate_delegated_targets([])
    assert verify_delegated_target("any/1.0.0/module.tar.gz", "abc", root, delegated) is False
