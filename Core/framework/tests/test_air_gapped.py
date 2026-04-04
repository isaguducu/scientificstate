"""AirGappedRegistry tests — offline module install, list, integrity check."""

import hashlib
import json
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from scientificstate.modules.registry.air_gapped import AirGappedRegistry
from scientificstate.modules.tuf.offline_verify import OfflineTUFVerifier


# ── Helpers ──────────────────────────────────────────────────────────────────


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_targets_meta(targets: dict | None = None) -> dict:
    expires = (datetime.now(tz=timezone.utc) + timedelta(days=90)).isoformat()
    return {
        "signed": {
            "_type": "targets",
            "spec_version": "1.0.0",
            "version": 1,
            "expires": expires,
            "targets": targets or {},
        },
        "signatures": [],
    }


def _make_root_meta() -> dict:
    return {
        "signed": {
            "_type": "root",
            "spec_version": "1.0.0",
            "version": 1,
            "expires": (datetime.now(tz=timezone.utc) + timedelta(days=365)).isoformat(),
            "keys": {
                "k1": {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyval": {"public": "aa" * 32},
                }
            },
            "roles": {
                "root": {"keyids": ["k1"], "threshold": 1},
                "targets": {"keyids": ["k1"], "threshold": 1},
            },
        },
        "signatures": [],
    }


def _setup_registry(
    tmp: str,
    module_name: str = "test_module",
    version: str = "1.0.0",
    file_content: bytes = b"module content",
    manifest_data: dict | None = None,
    *,
    include_trust_chain: bool = True,
) -> tuple[Path, Path, str]:
    """Set up a minimal air-gapped registry for testing.

    Args:
        include_trust_chain: If True, creates trust/public_key.der and
            sigstore.bundle.json (needed for mandatory verification since M3).

    Returns (registry_dir, tuf_dir, tarball_hash).
    """
    registry_dir = Path(tmp) / "registry"
    tuf_dir = registry_dir / "tuf"
    tuf_dir.mkdir(parents=True)

    # Create tarball
    pkg_dir = registry_dir / "packages" / module_name / f"v{version}"
    pkg_dir.mkdir(parents=True)

    tarball_path = pkg_dir / "package.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        import io

        info = tarfile.TarInfo(name="module.py")
        info.size = len(file_content)
        tar.addfile(info, io.BytesIO(file_content))

    tarball_hash = _sha256_file(tarball_path)

    # Write manifest
    manifest = manifest_data or {"name": module_name, "version": version}
    manifest_path = pkg_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # Write dummy signature
    sig_path = pkg_dir / "signature.sig"
    sig_path.write_text("aa" * 64, encoding="utf-8")

    # Write trust chain artifacts (mandatory since M3)
    if include_trust_chain:
        trust_dir = registry_dir / "trust"
        trust_dir.mkdir(parents=True, exist_ok=True)

        # Generate real Ed25519 key pair
        private_key = Ed25519PrivateKey.generate()
        public_key_der = private_key.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        (trust_dir / "public_key.der").write_bytes(public_key_der)

        # Sign the manifest with the real key (SHA-256 → Ed25519)
        manifest_bytes = manifest_path.read_bytes()
        digest = hashlib.sha256(manifest_bytes).digest()
        signature = private_key.sign(digest)
        sig_path.write_text(signature.hex(), encoding="utf-8")

        # Sigstore bundle (structurally valid — verify_sigstore_signature
        # checks cert + sig fields for presence)
        bundle = {
            "cert": "test-certificate-placeholder",
            "sig": signature.hex(),
            "identity": "test@scientificstate.org",
        }
        (pkg_dir / "sigstore.bundle.json").write_text(
            json.dumps(bundle), encoding="utf-8"
        )

    # Write TUF metadata
    target_name = f"{module_name}/{version}/module.tar.gz"
    targets = _make_targets_meta({
        target_name: {"length": tarball_path.stat().st_size, "hashes": {"sha256": tarball_hash}},
    })
    (tuf_dir / "targets.json").write_text(json.dumps(targets), encoding="utf-8")
    (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")

    return registry_dir, tuf_dir, tarball_hash


# ── install_module ───────────────────────────────────────────────────────────


def test_install_module_success():
    """Full install flow: TUF → Ed25519 → Sigstore → extract (all 3 gates)."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(tmp)
        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module", "1.0.0")
        assert result.ok is True
        assert result.module_name == "test_module"
        assert result.version == "1.0.0"

        # Verify extraction happened
        install_path = registry_dir / "installed" / "test_module" / "v1.0.0"
        assert install_path.exists()
        assert (install_path / "module.py").exists()


def test_install_module_no_public_key():
    """Missing public key → hard fail (mandatory since M3)."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(
            tmp, include_trust_chain=False
        )
        # Add sigstore bundle but no public key
        pkg_dir = registry_dir / "packages" / "test_module" / "v1.0.0"
        (pkg_dir / "sigstore.bundle.json").write_text("{}", encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module", "1.0.0")
        assert result.ok is False
        assert "public key" in result.error


def test_install_module_no_sigstore_bundle():
    """Missing Sigstore bundle → hard fail (mandatory since M3)."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(
            tmp, include_trust_chain=False
        )
        # Add a REAL key pair + valid signature, but NO sigstore bundle
        trust_dir = registry_dir / "trust"
        trust_dir.mkdir(parents=True, exist_ok=True)

        private_key = Ed25519PrivateKey.generate()
        public_key_der = private_key.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        (trust_dir / "public_key.der").write_bytes(public_key_der)

        # Sign the manifest
        pkg_dir = registry_dir / "packages" / "test_module" / "v1.0.0"
        manifest_bytes = (pkg_dir / "manifest.json").read_bytes()
        digest = hashlib.sha256(manifest_bytes).digest()
        signature = private_key.sign(digest)
        (pkg_dir / "signature.sig").write_text(signature.hex(), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module", "1.0.0")
        assert result.ok is False
        assert "sigstore" in result.error.lower()


def test_install_module_tuf_fail():
    """TUF hash mismatch → install fails."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(tmp)

        # Tamper targets.json to have wrong hash
        targets = _make_targets_meta({
            "test_module/1.0.0/module.tar.gz": {
                "length": 100,
                "hashes": {"sha256": "badhash"},
            },
        })
        (tuf_dir / "targets.json").write_text(json.dumps(targets), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module", "1.0.0")
        assert result.ok is False
        assert "TUF" in result.error


def test_install_module_not_found():
    """Module not in packages directory → install fails."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(tmp)
        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("nonexistent_module", "1.0.0")
        assert result.ok is False
        assert "not found" in result.error


def test_install_module_no_versions():
    """Module with no versions → install fails."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(tmp)
        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("nonexistent_module")
        assert result.ok is False
        assert "no versions" in result.error


def test_install_module_auto_version():
    """install_module without version → resolves latest."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir, tuf_dir, _ = _setup_registry(tmp, version="2.0.0")
        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module")
        assert result.ok is True
        assert result.version == "2.0.0"


def test_install_with_permissions():
    """Manifest with permissions → _sandbox.json written."""
    with tempfile.TemporaryDirectory() as tmp:
        manifest = {
            "name": "test_module",
            "version": "1.0.0",
            "permissions": {"network": False, "filesystem": ["read"]},
        }
        registry_dir, tuf_dir, _ = _setup_registry(
            tmp, manifest_data=manifest, include_trust_chain=True
        )
        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        result = registry.install_module("test_module", "1.0.0")
        assert result.ok is True

        sandbox_path = registry_dir / "installed" / "test_module" / "v1.0.0" / "_sandbox.json"
        assert sandbox_path.exists()
        sandbox = json.loads(sandbox_path.read_text(encoding="utf-8"))
        assert sandbox["network"] is False


# ── list_available ───────────────────────────────────────────────────────────


def test_list_available():
    """index.json with packages → list returned."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir = Path(tmp) / "registry"
        registry_dir.mkdir()
        index = {
            "packages": [
                {"domain_id": "polymer_science", "versions": [{"version": "1.0.0"}]},
                {"domain_id": "quantum_chem", "versions": [{"version": "2.0.0"}]},
            ]
        }
        (registry_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

        # Minimal TUF dir
        tuf_dir = registry_dir / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")
        (tuf_dir / "targets.json").write_text(json.dumps(_make_targets_meta()), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        packages = registry.list_available()
        assert len(packages) == 2
        assert packages[0]["domain_id"] == "polymer_science"
        assert packages[1]["domain_id"] == "quantum_chem"


def test_list_available_no_index():
    """No index.json → empty list."""
    with tempfile.TemporaryDirectory() as tmp:
        registry_dir = Path(tmp) / "registry"
        registry_dir.mkdir()
        tuf_dir = registry_dir / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")
        (tuf_dir / "targets.json").write_text(json.dumps(_make_targets_meta()), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(registry_dir, verifier)

        assert registry.list_available() == []


# ── verify_integrity ─────────────────────────────────────────────────────────


def test_verify_integrity_valid():
    """Valid MANIFEST.sha256 → True."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp) / "export"
        export_dir.mkdir()

        # Create test files
        (export_dir / "file1.txt").write_text("hello", encoding="utf-8")
        (export_dir / "file2.txt").write_text("world", encoding="utf-8")

        # Generate manifest
        lines = []
        for f in sorted(export_dir.iterdir()):
            if f.name == "MANIFEST.sha256":
                continue
            h = _sha256_file(f)
            lines.append(f"{h}  {f.name}")
        (export_dir / "MANIFEST.sha256").write_text("\n".join(lines), encoding="utf-8")

        # Verify
        tuf_dir = Path(tmp) / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")
        (tuf_dir / "targets.json").write_text(json.dumps(_make_targets_meta()), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(export_dir, verifier)

        assert registry.verify_integrity(export_dir) is True


def test_verify_integrity_tampered():
    """Tampered file → False."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp) / "export"
        export_dir.mkdir()

        (export_dir / "file1.txt").write_text("hello", encoding="utf-8")
        h = _sha256_file(export_dir / "file1.txt")
        (export_dir / "MANIFEST.sha256").write_text(
            f"{h}  file1.txt", encoding="utf-8"
        )

        # Tamper the file
        (export_dir / "file1.txt").write_text("tampered!", encoding="utf-8")

        tuf_dir = Path(tmp) / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")
        (tuf_dir / "targets.json").write_text(json.dumps(_make_targets_meta()), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(export_dir, verifier)

        assert registry.verify_integrity(export_dir) is False


def test_verify_integrity_no_manifest():
    """No MANIFEST.sha256 → False."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp) / "export"
        export_dir.mkdir()

        tuf_dir = Path(tmp) / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(json.dumps(_make_root_meta()), encoding="utf-8")
        (tuf_dir / "targets.json").write_text(json.dumps(_make_targets_meta()), encoding="utf-8")

        verifier = OfflineTUFVerifier(tuf_dir)
        registry = AirGappedRegistry(export_dir, verifier)

        assert registry.verify_integrity(export_dir) is False
