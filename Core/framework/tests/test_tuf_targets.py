"""TUF targets metadata tests — generation, hash verification, manager integration."""
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scientificstate.modules.tuf.targets import generate_targets, verify_target_hash


# ── Generation ────────────────────────────────────────────────────────────────

def test_generate_targets_structure():
    modules = [{"module_id": "polymer", "version": "1.0.0", "tarball_hash": "abc123"}]
    meta = generate_targets(modules)
    signed = meta["signed"]
    assert signed["_type"] == "targets"
    assert signed["spec_version"] == "1.0.0"
    assert signed["version"] == 1
    assert "expires" in signed
    assert meta["signatures"] == []


def test_generate_targets_single_module():
    modules = [{"module_id": "genomics", "version": "2.1.0", "tarball_hash": "deadbeef", "size": 4096}]
    meta = generate_targets(modules)
    targets = meta["signed"]["targets"]
    key = "genomics/2.1.0/module.tar.gz"
    assert key in targets
    assert targets[key]["hashes"]["sha256"] == "deadbeef"
    assert targets[key]["length"] == 4096


def test_generate_targets_multiple_modules():
    modules = [
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
        {"module_id": "climate", "version": "0.3.0", "tarball_hash": "bbb", "size": 1024},
        {"module_id": "genomics", "version": "3.0.0", "tarball_hash": "ccc"},
    ]
    meta = generate_targets(modules)
    targets = meta["signed"]["targets"]
    assert len(targets) == 3
    assert "polymer/1.0.0/module.tar.gz" in targets
    assert "climate/0.3.0/module.tar.gz" in targets
    assert "genomics/3.0.0/module.tar.gz" in targets


def test_generate_targets_default_size_zero():
    modules = [{"module_id": "test", "version": "0.1.0", "tarball_hash": "xyz"}]
    meta = generate_targets(modules)
    assert meta["signed"]["targets"]["test/0.1.0/module.tar.gz"]["length"] == 0


def test_generate_targets_custom_version_and_expiry():
    meta = generate_targets([], version=7, expiry_days=14)
    assert meta["signed"]["version"] == 7
    expires = datetime.fromisoformat(meta["signed"]["expires"])
    now = datetime.now(tz=timezone.utc)
    assert 13 <= (expires - now).days <= 14


# ── Hash verification ────────────────────────────────────────────────────────

def test_verify_target_hash_match():
    meta = generate_targets([{"module_id": "x", "version": "1.0.0", "tarball_hash": "abc123"}])
    assert verify_target_hash("x/1.0.0/module.tar.gz", "abc123", meta) is True


def test_verify_target_hash_mismatch():
    meta = generate_targets([{"module_id": "x", "version": "1.0.0", "tarball_hash": "abc123"}])
    assert verify_target_hash("x/1.0.0/module.tar.gz", "wrong_hash", meta) is False


def test_verify_target_hash_unknown_target():
    meta = generate_targets([{"module_id": "x", "version": "1.0.0", "tarball_hash": "abc123"}])
    assert verify_target_hash("unknown/1.0.0/module.tar.gz", "abc123", meta) is False


def test_verify_target_hash_empty_targets():
    meta = generate_targets([])
    assert verify_target_hash("any/1.0.0/module.tar.gz", "abc", meta) is False


# ── Manager TUF integration ──────────────────────────────────────────────────

def _make_manifest_with_tuf(domain_id="test_domain", version="0.1.0"):
    """Build a signed manifest + TUF targets for integration tests."""
    from scientificstate.modules.signer import generate_keypair, sign_manifest

    package_bytes = b"tuf test package content"
    pkg_hash = hashlib.sha256(package_bytes).hexdigest()

    canonical = {"domain_id": domain_id, "version": version,
                 "package_sha256": pkg_hash, "name": domain_id}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv)
    sig = {"algorithm": "ed25519", "public_key_id": "test-key-id", "value": sig_hex}
    manifest = {**canonical, "signature": sig}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()

    # TUF targets matching the package
    tuf_targets = generate_targets([{
        "module_id": domain_id,
        "version": version,
        "tarball_hash": pkg_hash,
        "size": len(package_bytes),
    }])

    return manifest_bytes, package_bytes, pub, tuf_targets


def test_manager_install_with_tuf_matching_hash():
    from scientificstate.modules.manager import ModuleManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        manifest_bytes, pkg, pub, tuf_targets = _make_manifest_with_tuf()
        mgr.set_tuf_targets(tuf_targets)
        result = mgr.install(manifest_bytes, pkg, pub)
        assert result.success is True


def test_manager_install_with_tuf_mismatching_hash_rejected():
    from scientificstate.modules.manager import ModuleManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        manifest_bytes, pkg, pub, tuf_targets = _make_manifest_with_tuf()

        # Tamper with TUF targets — set wrong hash
        tuf_targets["signed"]["targets"]["test_domain/0.1.0/module.tar.gz"]["hashes"]["sha256"] = "badhash"
        mgr.set_tuf_targets(tuf_targets)

        result = mgr.install(manifest_bytes, pkg, pub)
        assert result.success is False
        assert "TUF" in (result.error or "")


def test_manager_install_without_tuf_targets_skips_check():
    from scientificstate.modules.manager import ModuleManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        manifest_bytes, pkg, pub, _ = _make_manifest_with_tuf()
        # Do NOT set TUF targets — should skip TUF check
        result = mgr.install(manifest_bytes, pkg, pub)
        assert result.success is True
