"""
test_execute_method_invalid_input.py — Phase 1-A invalid-input tests for execute_method().

Verifies:
  - status == 'error' for missing required params
  - error_code is the correct MethodErrorCode enum value
  - diagnostics key always present (even on error)
  - legacy 'error' key preserved for backward-compat
"""
import pytest


@pytest.fixture
def domain():
    from polymer_science import PolymerScienceDomain
    return PolymerScienceDomain()


# ── Shared error-response assertion ──────────────────────────────────────────

def _assert_error_shape(resp: dict, expected_error_code: str) -> None:
    """Assert that an error execute_method() response has correct shape."""
    assert resp["status"] == "error", f"Expected status='error', got {resp['status']!r}"
    assert "error_code" in resp, "response missing 'error_code'"
    assert "diagnostics" in resp, "response missing 'diagnostics'"
    assert "error" in resp, "response missing 'error' (backward-compat field)"
    assert resp["error_code"] == expected_error_code, (
        f"expected error_code={expected_error_code!r}, got {resp['error_code']!r}"
    )


# ── Unknown method ────────────────────────────────────────────────────────────

def test_unknown_method_returns_error(domain):
    """Unknown method_id returns UNKNOWN_METHOD error_code."""
    resp = domain.execute_method("nonexistent", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "UNKNOWN_METHOD")
    assert "nonexistent" in resp["error"]


def test_unknown_method_domain_id_echo(domain):
    """Unknown method response still echoes domain_id."""
    resp = domain.execute_method("bad_method", data_ref="", assumptions=[], params={})
    assert resp["domain_id"] == "polymer_science"
    assert resp["method_id"] == "bad_method"


# ── PCA invalid input ─────────────────────────────────────────────────────────

def test_pca_missing_blocks_data(domain):
    """pca without blocks_data returns INVALID_PARAMS."""
    resp = domain.execute_method("pca", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "INVALID_PARAMS")


def test_pca_empty_params(domain):
    """pca with empty params returns INVALID_PARAMS."""
    resp = domain.execute_method("pca", data_ref="", assumptions=[], params={})
    assert resp["status"] == "error"
    assert resp["error_code"] == "INVALID_PARAMS"


# ── HCA invalid input ─────────────────────────────────────────────────────────

def test_hca_missing_blocks_data(domain):
    """hca without blocks_data returns INVALID_PARAMS."""
    resp = domain.execute_method("hca", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "INVALID_PARAMS")


# ── KMD invalid input ─────────────────────────────────────────────────────────

def test_kmd_missing_hca_result(domain):
    """kmd_analysis without hca_result returns INVALID_PARAMS."""
    resp = domain.execute_method(
        "kmd_analysis", data_ref="", assumptions=[],
        params={"blocks_data": []},  # hca_result absent
    )
    _assert_error_shape(resp, "INVALID_PARAMS")


def test_kmd_missing_blocks_data(domain):
    """kmd_analysis without blocks_data returns INVALID_PARAMS."""
    resp = domain.execute_method(
        "kmd_analysis", data_ref="", assumptions=[],
        params={"hca_result": {}},  # blocks_data absent
    )
    _assert_error_shape(resp, "INVALID_PARAMS")


def test_kmd_missing_both_required(domain):
    """kmd_analysis without hca_result and blocks_data returns INVALID_PARAMS."""
    resp = domain.execute_method("kmd_analysis", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "INVALID_PARAMS")


# ── Deisotoping invalid input ─────────────────────────────────────────────────

def test_deisotoping_missing_peaks(domain):
    """deisotoping without peaks returns INVALID_PARAMS."""
    resp = domain.execute_method("deisotoping", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "INVALID_PARAMS")


# ── Fragment matching invalid input ───────────────────────────────────────────

def test_fragment_matching_missing_peaks(domain):
    """fragment_matching without peaks returns INVALID_PARAMS."""
    resp = domain.execute_method("fragment_matching", data_ref="", assumptions=[], params={})
    _assert_error_shape(resp, "INVALID_PARAMS")


# ── Error response structure invariants ──────────────────────────────────────

@pytest.mark.parametrize("method_id,params", [
    ("pca", {}),
    ("hca", {}),
    ("kmd_analysis", {}),
    ("deisotoping", {}),
    ("fragment_matching", {}),
])
def test_error_response_always_has_diagnostics(method_id, params, domain):
    """Every error response (missing params) includes a diagnostics dict."""
    resp = domain.execute_method(method_id, data_ref="", assumptions=[], params=params)
    assert resp["status"] == "error"
    assert isinstance(resp.get("diagnostics"), dict), (
        f"{method_id}: diagnostics must be a dict even on error"
    )


@pytest.mark.parametrize("method_id,params", [
    ("pca", {}),
    ("hca", {}),
    ("kmd_analysis", {}),
    ("deisotoping", {}),
    ("fragment_matching", {}),
])
def test_error_response_echoes_method_and_domain_id(method_id, params, domain):
    """Every error response echoes method_id and domain_id."""
    resp = domain.execute_method(method_id, data_ref="", assumptions=[], params=params)
    assert resp["method_id"] == method_id
    assert resp["domain_id"] == "polymer_science"
