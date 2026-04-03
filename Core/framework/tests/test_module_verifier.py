"""Module verifier tests — Ed25519 signature verification rules."""


def _keypair():
    from scientificstate.modules.signer import generate_keypair
    return generate_keypair()


def _sign(manifest_bytes, priv):
    from scientificstate.modules.signer import sign_manifest
    return sign_manifest(manifest_bytes, priv)


def _verify(manifest_bytes, sig, pub):
    from scientificstate.modules.verifier import verify_manifest
    return verify_manifest(manifest_bytes, sig, pub)


MANIFEST = b'{"domain_id": "polymer_science", "version": "1.0.0"}'


def test_verifier_import():
    from scientificstate.modules.verifier import verify_manifest, VerifyResult
    assert verify_manifest is not None
    assert VerifyResult is not None


def test_valid_signature_passes():
    priv, pub = _keypair()
    sig = _sign(MANIFEST, priv)
    result = _verify(MANIFEST, sig, pub)
    assert result.valid is True
    assert result.reason == "signature valid"


def test_invalid_signature_fails():
    _, pub = _keypair()
    # Wrong key was used to sign
    priv2, _ = _keypair()
    sig = _sign(MANIFEST, priv2)
    result = _verify(MANIFEST, sig, pub)
    assert result.valid is False
    assert result.reason != "signature valid"


def test_unsigned_none_is_hard_rejected():
    """None signature must unconditionally reject — no override."""
    _, pub = _keypair()
    result = _verify(MANIFEST, None, pub)
    assert result.valid is False
    assert "unsigned" in result.reason.lower()


def test_unsigned_empty_string_is_hard_rejected():
    """Empty string signature must unconditionally reject."""
    _, pub = _keypair()
    result = _verify(MANIFEST, "", pub)
    assert result.valid is False
    assert "unsigned" in result.reason.lower()


def test_hash_mismatch_fails():
    """Signature on different content must not verify against different content."""
    priv, pub = _keypair()
    sig = _sign(b"original manifest", priv)
    result = _verify(b"tampered manifest", sig, pub)
    assert result.valid is False


def test_corrupted_signature_hex_fails():
    """Malformed hex string should return valid=False, not raise."""
    _, pub = _keypair()
    result = _verify(MANIFEST, "not-hex-!@#$", pub)
    assert result.valid is False


def test_verify_result_has_reason():
    _, pub = _keypair()
    result = _verify(MANIFEST, None, pub)
    assert isinstance(result.reason, str)
    assert len(result.reason) > 0
