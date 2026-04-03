"""Threshold signing tests — multi-key requirements for TUF metadata."""
import pytest

from scientificstate.modules.signer import generate_keypair
from scientificstate.modules.tuf.root import generate_root
from scientificstate.modules.tuf.threshold import threshold_sign, verify_threshold


def _make_keys(n: int = 3):
    """Generate n keypairs, return (privs, pubs) lists."""
    pairs = [generate_keypair() for _ in range(n)]
    return [p[0] for p in pairs], [p[1] for p in pairs]


# ── threshold_sign ────────────────────────────────────────────────────────────

def test_threshold_sign_adds_signatures():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs[:2], pubs[:2], threshold=2)
    assert len(meta["signatures"]) == 2


def test_threshold_sign_all_three():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs, pubs, threshold=2)
    assert len(meta["signatures"]) == 3


def test_threshold_sign_too_few_keys_raises():
    privs, pubs = _make_keys(1)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    with pytest.raises(ValueError, match="need at least 2"):
        threshold_sign(meta, privs, pubs, threshold=2)


# ── verify_threshold ──────────────────────────────────────────────────────────

def test_verify_threshold_2_of_3_pass():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs[:2], pubs[:2], threshold=2)
    assert verify_threshold(meta, pubs, threshold=2) is True


def test_verify_threshold_1_of_3_fail():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs[:1], pubs[:1], threshold=1)
    # Only 1 valid signature, but threshold is 2
    assert verify_threshold(meta, pubs, threshold=2) is False


def test_verify_threshold_3_of_3_pass():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs, pubs, threshold=2)
    assert verify_threshold(meta, pubs, threshold=2) is True


def test_verify_threshold_3_of_3_with_threshold_3():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs, pubs, threshold=3)
    assert verify_threshold(meta, pubs, threshold=3) is True


def test_verify_threshold_wrong_keys():
    privs, pubs = _make_keys(3)
    _, wrong_pubs_raw = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs[:2], pubs[:2], threshold=2)
    # Verify with completely different public keys
    assert verify_threshold(meta, wrong_pubs_raw, threshold=2) is False


def test_verify_threshold_no_signatures():
    _, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    assert verify_threshold(meta, pubs, threshold=2) is False


def test_verify_threshold_1_required():
    privs, pubs = _make_keys(3)
    _, root_pub = generate_keypair()
    meta = generate_root(root_pub)
    threshold_sign(meta, privs[:1], pubs[:1], threshold=1)
    assert verify_threshold(meta, pubs, threshold=1) is True
