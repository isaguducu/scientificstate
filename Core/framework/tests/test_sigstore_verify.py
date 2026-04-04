"""Sigstore verification tests — M3 mandatory enforcement (S16.2).

Updated from M2 (advisory fallback) to M3 (hard block when bundle missing).
"""
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
    assert "missing" in result["reason"].lower()
    assert result["signer_identity"] is None
    assert result["transparency_log"] is None


def test_verify_none_bundle():
    result = verify_sigstore_signature(b"artifact content", None)
    assert result["valid"] is False


def test_verify_valid_bundle():
    """M3: structurally valid bundle → accepted."""
    result = verify_sigstore_signature(b"artifact", {"cert": "...", "sig": "..."})
    assert result["valid"] is True
    assert "signer_identity" in result
    assert "transparency_log" in result
    assert "reason" in result


def test_response_dict_format():
    """Verify response dict always has the expected keys."""
    result = verify_sigstore_signature(b"data", {"cert": "c", "sig": "s"})
    assert set(result.keys()) == {"valid", "signer_identity", "transparency_log", "reason"}


def test_verify_with_artifact_bytes():
    """Verify that artifact_bytes parameter is accepted without error."""
    large_artifact = b"x" * 10_000
    result = verify_sigstore_signature(large_artifact, {"cert": "fake", "sig": "fake"})
    assert isinstance(result["valid"], bool)
