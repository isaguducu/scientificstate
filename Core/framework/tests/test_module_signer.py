"""Module signer tests — Ed25519 keypair generation and sign round-trip."""


def test_signer_import():
    from scientificstate.modules.signer import generate_keypair, sign_manifest
    assert generate_keypair is not None
    assert sign_manifest is not None


def test_keypair_generation_returns_two_byte_strings():
    from scientificstate.modules.signer import generate_keypair
    priv, pub = generate_keypair()
    assert isinstance(priv, bytes)
    assert isinstance(pub, bytes)
    assert len(priv) > 0
    assert len(pub) > 0


def test_keypair_each_call_is_unique():
    from scientificstate.modules.signer import generate_keypair
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()
    assert priv1 != priv2
    assert pub1 != pub2


def test_sign_returns_hex_string():
    from scientificstate.modules.signer import generate_keypair, sign_manifest
    priv, _ = generate_keypair()
    sig = sign_manifest(b"test manifest", priv)
    assert isinstance(sig, str)
    assert len(sig) == 128  # 64 bytes = 128 hex chars


def test_sign_different_content_different_signature():
    from scientificstate.modules.signer import generate_keypair, sign_manifest
    priv, _ = generate_keypair()
    sig1 = sign_manifest(b"manifest A", priv)
    sig2 = sign_manifest(b"manifest B", priv)
    assert sig1 != sig2


def test_sign_verify_round_trip():
    from scientificstate.modules.signer import generate_keypair, sign_manifest
    from scientificstate.modules.verifier import verify_manifest
    manifest = b'{"domain_id": "test", "version": "0.1.0"}'
    priv, pub = generate_keypair()
    sig = sign_manifest(manifest, priv)
    result = verify_manifest(manifest, sig, pub)
    assert result.valid is True


def test_wrong_key_verify_fails():
    from scientificstate.modules.signer import generate_keypair, sign_manifest
    from scientificstate.modules.verifier import verify_manifest
    manifest = b'{"domain_id": "test", "version": "0.1.0"}'
    priv, _ = generate_keypair()
    _, other_pub = generate_keypair()
    sig = sign_manifest(manifest, priv)
    result = verify_manifest(manifest, sig, other_pub)
    assert result.valid is False
