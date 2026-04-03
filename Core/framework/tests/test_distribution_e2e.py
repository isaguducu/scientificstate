"""Distribution E2E mock test — sign → install → discover flow."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from scientificstate.modules.manager import ModuleManager
from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient
from scientificstate.modules.signer import generate_keypair, sign_manifest
from scientificstate.modules.verifier import verify_manifest


def _build_signed_manifest(domain_id: str, version: str, package_bytes: bytes) -> tuple[bytes, bytes]:
    """Build a signed manifest.

    Signing convention: signature covers canonical bytes = manifest WITHOUT the
    'signature' field (sort_keys=True). Manager strips 'signature' before verify.

    Returns: (manifest_bytes_with_sig, public_key_bytes)
    """
    checksum = hashlib.sha256(package_bytes).hexdigest()
    canonical = {
        "domain_id": domain_id,
        "version": version,
        "name": domain_id,
        "package_sha256": checksum,
    }
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()
    priv, pub = generate_keypair()
    sig_hex = sign_manifest(canonical_bytes, priv)
    # Schema: signature = {algorithm, public_key_id, value} | null
    sig = {"algorithm": "ed25519", "public_key_id": "test-key-id", "value": sig_hex}
    full = {**canonical, "signature": sig}
    return json.dumps(full, sort_keys=True).encode(), pub


# ── Sign ───────────────────────────────────────────────────────────────────────

def test_e2e_sign_step():
    package = b"polymer domain module code"
    manifest, pub = _build_signed_manifest("polymer_science", "1.0.0", package)
    manifest_dict = json.loads(manifest)
    assert "signature" in manifest_dict
    assert manifest_dict["domain_id"] == "polymer_science"


# ── Verify standalone ──────────────────────────────────────────────────────────

def test_e2e_verify_signed_manifest():
    package = b"module code v2"
    manifest_bytes, pub = _build_signed_manifest("genomics", "2.0.0", package)
    manifest_dict = json.loads(manifest_bytes)
    sig_field = manifest_dict.get("signature")
    # Schema: signature is {algorithm, public_key_id, value} — extract .value for verifier
    sig_hex = sig_field.get("value") if isinstance(sig_field, dict) else sig_field
    # Verify against canonical bytes (without 'signature' field) — matches manager convention
    canonical = {k: v for k, v in manifest_dict.items() if k != "signature"}
    canonical_bytes = json.dumps(canonical, sort_keys=True).encode()
    result = verify_manifest(canonical_bytes, sig_hex, pub)
    assert result.valid is True


# ── Install ────────────────────────────────────────────────────────────────────

def test_e2e_install_signed_module():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        package = b"polymer module v1.0.0"
        manifest_bytes, pub = _build_signed_manifest("polymer_science", "1.0.0", package)
        result = mgr.install(manifest_bytes, package, pub)
        assert result.success is True
        assert result.domain_id == "polymer_science"


# ── List installed ─────────────────────────────────────────────────────────────

def test_e2e_list_installed_after_install():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        package = b"polymer module content"
        manifest_bytes, pub = _build_signed_manifest("polymer_science", "1.0.0", package)
        mgr.install(manifest_bytes, package, pub)
        installed = mgr.list_installed()
        assert len(installed) == 1
        assert installed[0]["domain_id"] == "polymer_science"
        assert installed[0]["version"] == "1.0.0"


# ── Registry mock → download → install ────────────────────────────────────────

def test_e2e_registry_download_then_install():
    """Full flow: registry client returns manifest → install → visible in list."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        package = b"downloaded module content"
        manifest_bytes, pub = _build_signed_manifest("climate", "0.3.0", package)
        manifest_dict = json.loads(manifest_bytes)

        # Mock registry returning the manifest dict
        client = RegistryClient(
            RegistriesConfig(
                registries=[{"name": "official", "url": "http://registry.example", "priority": 1}]
            )
        )

        # Simulate download_manifest returning the manifest dict
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(manifest_dict).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp):
            downloaded = client.download_manifest("climate", "0.3.0")

        assert downloaded is not None
        assert downloaded["domain_id"] == "climate"

        result = mgr.install(manifest_bytes, package, pub)  # use original bytes (same sig)
        assert result.success is True

        installed = mgr.list_installed()
        found = [m for m in installed if m["domain_id"] == "climate"]
        assert len(found) == 1


# ── Unsigned reject in full flow ───────────────────────────────────────────────

def test_e2e_unsigned_manifest_rejected_at_install():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ModuleManager(modules_dir=Path(tmp) / "modules")
        package = b"unsigned module"
        _, pub = generate_keypair()

        unsigned_manifest = json.dumps({
            "domain_id": "malicious", "version": "9.9.9", "signature": ""
        }, sort_keys=True).encode()

        result = mgr.install(unsigned_manifest, package, pub)
        assert result.success is False
        assert "unsigned" in (result.error or "").lower() or "signature" in (result.error or "").lower()
