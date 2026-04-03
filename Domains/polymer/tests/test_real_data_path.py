"""
test_real_data_path.py — Phase 1-A: data_ref file path tests.

Exercises _load_data_ref() / _merge_data_ref() with fixtures/sample_data.csv and
edge-case inputs (empty dict, single-row, missing file).
"""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_data.csv"


@pytest.fixture
def domain():
    from polymer_science import PolymerScienceDomain
    return PolymerScienceDomain()


# ── _load_data_ref direct ─────────────────────────────────────────────────────

def test_load_data_ref_csv_returns_list_of_dicts(domain):
    """_load_data_ref on sample_data.csv returns a list of row dicts."""
    result = domain._load_data_ref(str(SAMPLE_CSV))
    assert isinstance(result, list)
    assert len(result) == 10
    assert "mz" in result[0]
    assert "intensity" in result[0]


def test_load_data_ref_nonexistent_returns_none(domain):
    """_load_data_ref on a nonexistent path returns None (no crash)."""
    result = domain._load_data_ref("/nonexistent/path/data.csv")
    assert result is None


def test_load_data_ref_unsupported_extension_returns_none(domain, tmp_path):
    """_load_data_ref on an unsupported extension (.txt) returns None."""
    f = tmp_path / "data.txt"
    f.write_text("some text")
    result = domain._load_data_ref(str(f))
    assert result is None


def test_load_data_ref_json_returns_list(domain, tmp_path):
    """_load_data_ref on a JSON array returns a list."""
    import json
    data = [{"mz": 100.0, "intensity": 1500.0}]
    f = tmp_path / "peaks.json"
    f.write_text(json.dumps(data))
    result = domain._load_data_ref(str(f))
    assert isinstance(result, list)
    assert result[0]["mz"] == 100.0


# ── Deisotoping via data_ref CSV ──────────────────────────────────────────────

def test_deisotoping_via_data_ref_csv(domain):
    """
    deisotoping with data_ref=sample_data.csv and peaks absent in params
    → merges CSV rows as peaks → returns status='ok' or 'error' (no crash).
    """
    resp = domain.execute_method(
        "deisotoping",
        data_ref=str(SAMPLE_CSV),
        assumptions=[],
        params={"top_n": 5},
    )
    # CSV rows have mz/intensity — should be treated as peaks
    assert "status" in resp
    assert resp["method_id"] == "deisotoping"
    assert resp["domain_id"] == "polymer_science"
    assert "diagnostics" in resp
    # No crash: either ok or a known error code
    if resp["status"] == "error":
        assert resp["error_code"] in ("INVALID_PARAMS", "EXECUTION_ERROR")


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_execute_method_empty_dict_params_no_crash(domain):
    """execute_method with empty params (all methods) must not crash."""
    for method_id in ["pca", "hca", "kmd_analysis", "deisotoping", "fragment_matching"]:
        resp = domain.execute_method(method_id, data_ref="", assumptions=[], params={})
        assert "status" in resp, f"{method_id}: no status in response"
        assert "diagnostics" in resp, f"{method_id}: no diagnostics in response"
        # Must be error (missing required params) — never a crash
        assert resp["status"] == "error", (
            f"{method_id}: expected status='error' for empty params, got {resp['status']!r}"
        )


def test_execute_method_single_row_peaks_no_crash(domain):
    """Single-row peaks input must not crash (ok or known error)."""
    resp = domain.execute_method(
        "deisotoping", data_ref="", assumptions=[],
        params={"peaks": [{"mz": 100.0, "intensity": 1000.0}]},
    )
    assert "status" in resp
    assert resp["domain_id"] == "polymer_science"
    assert "diagnostics" in resp


def test_execute_method_single_row_blocks_no_crash(domain):
    """Single-block input must not crash (ok or known error)."""
    import numpy as np
    rng = np.random.default_rng(0)
    single_block = [{
        "block_id": 1,
        "mz": np.arange(40.0, 100.0, 1.0),
        "intensity": rng.random(60) * 1000,
        "temperature": 60.0,
    }]
    for method_id in ["pca", "hca"]:
        resp = domain.execute_method(
            method_id, data_ref="", assumptions=[],
            params={"blocks_data": single_block, "n_components": 1, "n_clusters": 1},
        )
        assert "status" in resp, f"{method_id}: no status in response"
        assert "diagnostics" in resp, f"{method_id}: no diagnostics in response"


def test_execute_method_empty_peaks_list_no_crash(domain):
    """Empty peaks list must not crash."""
    resp = domain.execute_method(
        "deisotoping", data_ref="", assumptions=[],
        params={"peaks": []},
    )
    assert "status" in resp
    assert resp["domain_id"] == "polymer_science"


def test_execute_method_empty_blocks_list_no_crash(domain):
    """Empty blocks list must not crash."""
    resp = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": []},
    )
    assert "status" in resp
    assert resp["domain_id"] == "polymer_science"


# ── data_ref takes no effect when params already has the key ─────────────────

def test_data_ref_ignored_when_params_has_key(domain):
    """
    When params already has 'peaks', data_ref pointing to a different file
    should have no effect — params takes precedence.
    """
    import numpy as np
    rng = np.random.default_rng(7)
    explicit_peaks = [
        {"mz": 100.0 + i * 5, "intensity": float(rng.random() * 1000)}
        for i in range(20)
    ]
    resp = domain.execute_method(
        "deisotoping",
        data_ref=str(SAMPLE_CSV),  # different data — should be ignored
        assumptions=[],
        params={"peaks": explicit_peaks, "top_n": 5},
    )
    assert resp["status"] == "ok"
    assert resp["method_id"] == "deisotoping"
