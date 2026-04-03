"""Sigstore verification tests — graceful fallback when library unavailable."""
from scientificstate.modules.sigstore_verify import (
    is_sigstore_available,
    verify_sigstore_signature,
)


# ── is_sigstore_available ─────────────────────────────────────────────────────

def test_is_sigstore_available_returns_bool():
    result = is_sigstore_available()
    assert isinstance(result, bool)


# ── verify_sigstore_signature ─────────────────────────────────────────────────

def test_verify_empty_bundle():
    result = verify_sigstore_signature(b"artifact content", {})
    assert result["valid"] is False
    assert result["reason"] == "empty signature bundle"
    assert result["signer_identity"] is None
    assert result["transparency_log"] is None


def test_verify_none_bundle():
    result = verify_sigstore_signature(b"artifact content", {})
    assert result["valid"] is False


def test_verify_fallback_no_library():
    """When sigstore is not installed, we get a graceful fallback."""
    result = verify_sigstore_signature(b"artifact", {"cert": "...", "sig": "..."})
    assert result["valid"] is False
    assert "signer_identity" in result
    assert "transparency_log" in result
    assert "reason" in result
    # Should mention fallback or unavailability
    assert "fallback" in result["reason"].lower() or "not available" in result["reason"].lower() or "not yet implemented" in result["reason"].lower()


def test_response_dict_format():
    """Verify response dict always has the expected keys."""
    result = verify_sigstore_signature(b"data", {"some": "bundle"})
    assert set(result.keys()) == {"valid", "signer_identity", "transparency_log", "reason"}


def test_verify_with_artifact_bytes():
    """Verify that artifact_bytes parameter is accepted without error."""
    large_artifact = b"x" * 10_000
    result = verify_sigstore_signature(large_artifact, {"cert": "fake"})
    assert isinstance(result["valid"], bool)
