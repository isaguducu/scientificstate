"""Module manager tests — install, remove, list, unsigned reject."""
import hashlib
import json
import tempfile
from pathlib import Path


def _make_manifest(domain_id="test_domain", version="0.1.0", include_sig=True) -> tuple[bytes, bytes, bytes]:
    """Returns (manifest_bytes_with_sig, package_bytes, public_key_bytes).

    Signing convention: signature covers canonical bytes = manifest WITHOUT the
    'signature' field (sort_keys=True). Manager strips 'signature' before verify.
    """
    from scientificstate.modules.signer import generate_keypair, sign_manifest

    package_bytes = b"fake module package content"
    checksum = hashlib.sha256(package_bytes).hexdigest()

    canonical = {"domain_id": domain_id, "version": version,
                 "package_sha256": checksum, "name": domain_id}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()

    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv) if include_sig else None
    # Schema: signature = {algorithm, public_key_id, value} | null
    sig = {"algorithm": "ed25519", "public_key_id": "test-key-id", "value": sig_hex} if sig_hex else None

    manifest = {**canonical, "signature": sig}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()

    return manifest_bytes, package_bytes, pub


def _manager(tmp_dir: Path):
    from scientificstate.modules.manager import ModuleManager
    mgr = ModuleManager(modules_dir=tmp_dir / "modules")
    # These tests predate M3 Sigstore enforcement — disable for P1 Ed25519 tests.
    mgr.set_sigstore_required(False)
    return mgr


# ── Install ────────────────────────────────────────────────────────────────────

def test_manager_import():
    from scientificstate.modules.manager import ModuleManager, InstallResult, RemoveResult
    assert ModuleManager is not None
    assert InstallResult is not None
    assert RemoveResult is not None


def test_install_valid_module_succeeds():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, pub = _make_manifest()
        result = mgr.install(manifest_bytes, pkg, pub)
        assert result.success is True
        assert result.domain_id == "test_domain"
        assert result.version == "0.1.0"
        assert result.install_path is not None
        assert result.install_path.exists()


def test_install_creates_files_on_disk():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, pub = _make_manifest()
        result = mgr.install(manifest_bytes, pkg, pub)
        assert (result.install_path / "package.bin").exists()
        assert (result.install_path / "manifest.json").exists()


def test_install_unsigned_manifest_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, pub = _make_manifest(include_sig=False)
        result = mgr.install(manifest_bytes, pkg, pub)
        assert result.success is False
        assert result.error is not None
        assert "signature" in result.error.lower() or "unsigned" in result.error.lower()


def test_install_wrong_pub_key_rejected():
    from scientificstate.modules.signer import generate_keypair
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, _ = _make_manifest()
        _, wrong_pub = generate_keypair()
        result = mgr.install(manifest_bytes, pkg, wrong_pub)
        assert result.success is False


# ── Remove ─────────────────────────────────────────────────────────────────────

def test_remove_installed_module():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, pub = _make_manifest()
        mgr.install(manifest_bytes, pkg, pub)
        result = mgr.remove("test_domain")
        assert result.success is True
        assert result.domain_id == "test_domain"


def test_remove_preserves_data():
    """P9: data_preserved must always be True."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        result = mgr.remove("nonexistent_domain")
        assert result.data_preserved is True


def test_remove_nonexistent_is_ok():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        result = mgr.remove("does_not_exist")
        assert result.success is True


# ── List ───────────────────────────────────────────────────────────────────────

def test_list_empty_when_nothing_installed():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        assert mgr.list_installed() == []


def test_list_shows_installed_module():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _manager(Path(tmp))
        manifest_bytes, pkg, pub = _make_manifest("bio_domain", "1.0.0")
        mgr.install(manifest_bytes, pkg, pub)
        installed = mgr.list_installed()
        assert len(installed) == 1
        assert installed[0]["domain_id"] == "bio_domain"
        assert installed[0]["version"] == "1.0.0"
