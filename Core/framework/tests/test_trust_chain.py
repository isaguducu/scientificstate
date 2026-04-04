"""Tests for cross-institutional TUF trust chain (Phase 4 W2)."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from scientificstate.modules.tuf.delegated import (
    generate_delegated_targets,
    sign_delegated_targets,
)
from scientificstate.modules.tuf.trust_chain import TrustChain


def _make_keypair() -> tuple[bytes, str]:
    """Generate Ed25519 keypair → (private_der, public_hex)."""
    priv = Ed25519PrivateKey.generate()
    priv_der = priv.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return priv_der, pub_hex


def _build_delegated(
    institution_id: str,
    version: str,
    package: bytes,
    priv_der: bytes,
) -> tuple[dict, str, str]:
    """Build signed delegated targets for a module.

    Returns (delegated_meta, target_path, pkg_hash).
    """
    pkg_hash = hashlib.sha256(package).hexdigest()
    delegated = generate_delegated_targets([{
        "module_id": institution_id,
        "version": version,
        "tarball_hash": pkg_hash,
        "size": len(package),
    }])
    sign_delegated_targets(delegated, priv_der)
    target_path = f"{institution_id}/{version}/module.tar.gz"
    return delegated, target_path, pkg_hash


# ── add_institution_trust ──────────────────────────────────────────────


def test_add_institution_creates_delegation():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        info = chain.add_institution_trust("uni-tokyo", pub)
        assert info["institution_id"] == "uni-tokyo"
        assert info["trust_level"] == "verified"
        assert info["paths"] == ["uni-tokyo/*"]


def test_add_institution_appears_in_root_targets():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("mit", pub)
        roles = chain.root_targets["signed"]["delegations"]["roles"]
        assert any(r["name"] == "mit" for r in roles)


def test_add_multiple_institutions():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub1 = _make_keypair()
        _, pub2 = _make_keypair()
        chain.add_institution_trust("org-a", pub1)
        chain.add_institution_trust("org-b", pub2)
        assert len(chain.institutions) == 2
        assert "org-a" in chain.institutions
        assert "org-b" in chain.institutions


def test_add_institution_provisional():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        info = chain.add_institution_trust("new-org", pub, trust_level="provisional")
        assert info["trust_level"] == "provisional"


# ── verify_cross_institutional ─────────────────────────────────────────


def test_verify_trusted_institution():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        priv, pub = _make_keypair()
        chain.add_institution_trust("uni-tokyo", pub)

        package = b"polymer module content"
        delegated, target_path, pkg_hash = _build_delegated(
            "uni-tokyo", "1.0.0", package, priv,
        )
        chain.set_delegated_targets("uni-tokyo", delegated)

        assert chain.verify_cross_institutional(target_path, pkg_hash, "uni-tokyo") is True


def test_verify_unknown_institution_returns_false():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        assert chain.verify_cross_institutional(
            "unknown/1.0.0/module.tar.gz", "abc", "unknown",
        ) is False


def test_verify_revoked_institution_returns_false():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        priv, pub = _make_keypair()
        chain.add_institution_trust("revoked-org", pub)

        package = b"module"
        delegated, target_path, pkg_hash = _build_delegated(
            "revoked-org", "1.0.0", package, priv,
        )
        chain.set_delegated_targets("revoked-org", delegated)

        chain.revoke_institution("revoked-org")
        assert chain.verify_cross_institutional(target_path, pkg_hash, "revoked-org") is False


def test_verify_wrong_hash_returns_false():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        priv, pub = _make_keypair()
        chain.add_institution_trust("org-x", pub)

        delegated, target_path, _ = _build_delegated(
            "org-x", "1.0.0", b"real content", priv,
        )
        chain.set_delegated_targets("org-x", delegated)

        assert chain.verify_cross_institutional(target_path, "wrong_hash", "org-x") is False


def test_verify_wrong_signature_returns_false():
    """Delegated targets signed with wrong key → False."""
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        wrong_priv, _ = _make_keypair()
        chain.add_institution_trust("org-y", pub)

        package = b"content"
        # Sign with WRONG key
        delegated, target_path, pkg_hash = _build_delegated(
            "org-y", "1.0.0", package, wrong_priv,
        )
        chain.set_delegated_targets("org-y", delegated)

        assert chain.verify_cross_institutional(target_path, pkg_hash, "org-y") is False


def test_verify_no_delegated_targets_returns_false():
    """Institution registered but no delegated targets attached → False."""
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("org-z", pub)
        assert chain.verify_cross_institutional(
            "org-z/1.0.0/module.tar.gz", "abc", "org-z",
        ) is False


# ── revoke_institution ─────────────────────────────────────────────────


def test_revoke_removes_from_institutions():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("to-revoke", pub)
        chain.revoke_institution("to-revoke")

        assert "to-revoke" not in chain.institutions
        assert "to-revoke" in chain.revoked


def test_revoke_removes_delegation_from_root():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("org-del", pub)
        chain.revoke_institution("org-del")

        roles = chain.root_targets["signed"].get("delegations", {}).get("roles", [])
        assert not any(r["name"] == "org-del" for r in roles)


def test_revoke_nonexistent_is_safe():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        chain.revoke_institution("ghost")
        assert "ghost" in chain.revoked


# ── propagate_revocation ───────────────────────────────────────────────


def test_propagate_revocation_all_peers():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("bad-org", pub)

        result = chain.propagate_revocation("bad-org", ["peer-1", "peer-2", "peer-3"])
        assert result["revoked_institution_id"] == "bad-org"
        assert result["notified_peers"] == 3
        assert len(result["notifications"]) == 3
        assert all(n["action"] == "revoke_trust" for n in result["notifications"])
        assert {n["peer_institution_id"] for n in result["notifications"]} == {
            "peer-1", "peer-2", "peer-3",
        }


def test_propagate_revocation_empty_peers():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("lonely-org", pub)

        result = chain.propagate_revocation("lonely-org", [])
        assert result["notified_peers"] == 0
        assert result["notifications"] == []


def test_propagate_also_revokes_if_not_already():
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        _, pub = _make_keypair()
        chain.add_institution_trust("auto-revoke", pub)

        chain.propagate_revocation("auto-revoke", ["peer-1"])
        assert "auto-revoke" in chain.revoked


# ── re-trust after revoke ──────────────────────────────────────────────


def test_re_add_after_revoke():
    """Re-adding a revoked institution clears revocation."""
    with tempfile.TemporaryDirectory() as tmp:
        chain = TrustChain(Path(tmp) / "root.json")
        priv, pub = _make_keypair()
        chain.add_institution_trust("comeback", pub)
        chain.revoke_institution("comeback")
        assert "comeback" in chain.revoked

        chain.add_institution_trust("comeback", pub)
        assert "comeback" not in chain.revoked
        assert "comeback" in chain.institutions


# ── persistence ────────────────────────────────────────────────────────


def test_save_and_reload():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "root.json"
        chain = TrustChain(path)
        _, pub = _make_keypair()
        chain.add_institution_trust("saved-org", pub)
        chain.save()

        assert path.exists()
        loaded = json.loads(path.read_text())
        roles = loaded["signed"]["delegations"]["roles"]
        assert any(r["name"] == "saved-org" for r in roles)


def test_load_existing_root():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "root.json"
        # Write a minimal root targets file
        root = {
            "signed": {
                "_type": "targets",
                "spec_version": "1.0.0",
                "version": 1,
                "targets": {},
            },
            "signatures": [],
        }
        path.write_text(json.dumps(root), encoding="utf-8")

        chain = TrustChain(path)
        assert chain.root_targets["signed"]["_type"] == "targets"
