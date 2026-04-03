"""TUF root metadata tests — generation, signing, verification."""
import json
from datetime import datetime, timezone

from scientificstate.modules.signer import generate_keypair
from scientificstate.modules.tuf.root import (
    _key_id,
    _raw_pub_hex,
    generate_root,
    sign_root,
    verify_root,
)


# ── Key helpers ───────────────────────────────────────────────────────────────

def test_raw_pub_hex_is_64_chars():
    _, pub = generate_keypair()
    hex_str = _raw_pub_hex(pub)
    assert len(hex_str) == 64  # 32 bytes = 64 hex chars


def test_key_id_deterministic():
    _, pub = generate_keypair()
    kid1 = _key_id(pub)
    kid2 = _key_id(pub)
    assert kid1 == kid2
    assert len(kid1) == 64  # SHA-256 hex


def test_key_id_different_keys():
    _, pub1 = generate_keypair()
    _, pub2 = generate_keypair()
    assert _key_id(pub1) != _key_id(pub2)


# ── Generation ────────────────────────────────────────────────────────────────

def test_generate_root_structure():
    _, pub = generate_keypair()
    root = generate_root(pub)
    signed = root["signed"]
    assert signed["_type"] == "root"
    assert signed["spec_version"] == "1.0.0"
    assert signed["version"] == 1
    assert "expires" in signed
    assert "keys" in signed
    assert "roles" in signed
    assert root["signatures"] == []


def test_generate_root_has_correct_key():
    _, pub = generate_keypair()
    root = generate_root(pub)
    kid = _key_id(pub)
    keys = root["signed"]["keys"]
    assert kid in keys
    assert keys[kid]["keytype"] == "ed25519"
    assert keys[kid]["keyval"]["public"] == _raw_pub_hex(pub)


def test_generate_root_roles():
    _, pub = generate_keypair()
    root = generate_root(pub)
    kid = _key_id(pub)
    roles = root["signed"]["roles"]
    assert roles["root"]["threshold"] == 1
    assert kid in roles["root"]["keyids"]
    assert roles["targets"]["threshold"] == 1
    assert kid in roles["targets"]["keyids"]


def test_generate_root_custom_version():
    _, pub = generate_keypair()
    root = generate_root(pub, version=5)
    assert root["signed"]["version"] == 5


def test_generate_root_expiry():
    _, pub = generate_keypair()
    root = generate_root(pub, expiry_days=30)
    expires = datetime.fromisoformat(root["signed"]["expires"])
    now = datetime.now(tz=timezone.utc)
    delta = (expires - now).days
    assert 29 <= delta <= 30


def test_generate_root_zero_expiry_in_past():
    _, pub = generate_keypair()
    root = generate_root(pub, expiry_days=0)
    expires = datetime.fromisoformat(root["signed"]["expires"])
    now = datetime.now(tz=timezone.utc)
    # expiry_days=0 means expires ~now (within seconds)
    assert abs((expires - now).total_seconds()) < 5


# ── Signing ───────────────────────────────────────────────────────────────────

def test_sign_root_adds_signature():
    priv, pub = generate_keypair()
    root = generate_root(pub)
    sign_root(root, priv, pub)
    assert len(root["signatures"]) == 1
    sig = root["signatures"][0]
    assert sig["keyid"] == _key_id(pub)
    assert len(sig["sig"]) == 128  # 64 bytes hex


def test_sign_root_multiple_signatures():
    priv, pub = generate_keypair()
    root = generate_root(pub)
    sign_root(root, priv, pub)
    sign_root(root, priv, pub)
    assert len(root["signatures"]) == 2


# ── Verification ──────────────────────────────────────────────────────────────

def test_verify_root_valid():
    priv, pub = generate_keypair()
    root = generate_root(pub)
    sign_root(root, priv, pub)
    assert verify_root(root, [pub]) is True


def test_verify_root_wrong_key():
    priv, pub = generate_keypair()
    _, wrong_pub = generate_keypair()
    root = generate_root(pub)
    sign_root(root, priv, pub)
    assert verify_root(root, [wrong_pub]) is False


def test_verify_root_no_signatures():
    _, pub = generate_keypair()
    root = generate_root(pub)
    assert verify_root(root, [pub]) is False


def test_verify_root_canonical_stability():
    """Signing and verification use the same canonical form."""
    priv, pub = generate_keypair()
    root = generate_root(pub)
    sign_root(root, priv, pub)
    # Re-serialize signed payload — should still verify
    canonical = json.dumps(root["signed"], sort_keys=True)
    root["signed"] = json.loads(canonical)
    assert verify_root(root, [pub]) is True
