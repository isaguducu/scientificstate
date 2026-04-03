"""
test_execute_method_smoke.py — Phase 1-A smoke tests for execute_method().

Verifies:
  - status == 'ok' for all methods
  - result key present
  - diagnostics key present (Phase 1 new field)
  - method_id and domain_id echo in response
"""
import json
import tempfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _synthetic_blocks(n: int = 6) -> List[Dict]:
    rng = np.random.default_rng(42)
    return [
        {
            "block_id": i + 1,
            "mz": np.arange(40.0, 200.0, 1.0),
            "intensity": rng.random(160) * 1000 + 10,
            "temperature": 60.0 + i * 10,
        }
        for i in range(n)
    ]


def _synthetic_peaks(n: int = 20) -> List[Dict]:
    rng = np.random.default_rng(0)
    return [
        {"mz": 100.0 + i * 10.0 + rng.random() * 0.5, "intensity": float(1000 - i * 30)}
        for i in range(n)
    ]


@pytest.fixture
def domain():
    from polymer_science import PolymerScienceDomain
    return PolymerScienceDomain()


# ── Shared response shape assertion ──────────────────────────────────────────

def _assert_ok_shape(resp: dict, expected_method_id: str) -> None:
    """Assert that a successful execute_method() response has correct shape."""
    assert resp["status"] == "ok", f"status != ok: {resp.get('error')}"
    assert "result" in resp, "response missing 'result'"
    assert "diagnostics" in resp, "response missing 'diagnostics' (Phase 1 new field)"
    assert resp["method_id"] == expected_method_id
    assert resp["domain_id"] == "polymer_science"


# ── PCA ───────────────────────────────────────────────────────────────────────

def test_execute_pca_smoke(domain):
    """execute_method('pca') returns ok with result.scores and diagnostics."""
    resp = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6), "n_components": 2},
    )
    _assert_ok_shape(resp, "pca")
    assert "scores" in resp["result"]


def test_execute_pca_diagnostics_is_dict(domain):
    """diagnostics field must be a dict."""
    resp = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6)},
    )
    assert isinstance(resp["diagnostics"], dict)


# ── HCA ───────────────────────────────────────────────────────────────────────

def test_execute_hca_smoke(domain):
    """execute_method('hca') returns ok with result.labels and diagnostics."""
    resp = domain.execute_method(
        "hca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6), "n_clusters": 2},
    )
    _assert_ok_shape(resp, "hca")
    assert "labels" in resp["result"]


# ── KMD ───────────────────────────────────────────────────────────────────────

def test_execute_kmd_smoke(domain):
    """execute_method('kmd_analysis') returns ok with cluster_relations."""
    from polymer_science.methods.hca import compute_hca
    blocks = _synthetic_blocks(6)
    hca_result = compute_hca(blocks, n_clusters=2)
    resp = domain.execute_method(
        "kmd_analysis", data_ref="", assumptions=[],
        params={"hca_result": hca_result, "blocks_data": blocks, "polymer": "PS"},
    )
    _assert_ok_shape(resp, "kmd_analysis")
    assert "cluster_relations" in resp["result"]


# ── Deisotoping ───────────────────────────────────────────────────────────────

def test_execute_deisotoping_smoke(domain):
    """execute_method('deisotoping') returns ok with envelopes and diagnostics."""
    resp = domain.execute_method(
        "deisotoping", data_ref="", assumptions=[],
        params={"peaks": _synthetic_peaks(20), "top_n": 10},
    )
    _assert_ok_shape(resp, "deisotoping")
    assert "envelopes" in resp["result"]


# ── Fragment matching ─────────────────────────────────────────────────────────

def test_execute_fragment_matching_smoke(domain):
    """execute_method('fragment_matching') returns ok with matches list."""
    db = domain.get_fragment_db()
    ps_frags = db.get("PS", {}).get("fragments", [])
    if not ps_frags:
        pytest.skip("No PS fragments in fragment_db.json")
    peaks = [{"mz": f["mz"] + 0.1, "intensity": 1000.0} for f in ps_frags[:5]]
    resp = domain.execute_method(
        "fragment_matching", data_ref="", assumptions=[],
        params={"peaks": peaks, "polymer": "PS", "abs_tol": 0.5},
    )
    _assert_ok_shape(resp, "fragment_matching")
    assert isinstance(resp["result"]["matches"], list)


# ── data_ref (JSON) ───────────────────────────────────────────────────────────

def test_execute_pca_data_ref_json(domain):
    """execute_method('pca') loads blocks_data from a JSON data_ref."""
    blocks = _synthetic_blocks(4)
    # Serialize numpy arrays to lists for JSON
    json_blocks = [
        {**b, "mz": b["mz"].tolist(), "intensity": b["intensity"].tolist()}
        for b in blocks
    ]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(json_blocks, f)
        tmp_path = f.name

    try:
        resp = domain.execute_method(
            "pca", data_ref=tmp_path, assumptions=[],
            params={"n_components": 2},  # blocks_data absent — loaded from data_ref
        )
        _assert_ok_shape(resp, "pca")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_execute_deisotoping_data_ref_json(domain):
    """execute_method('deisotoping') loads peaks from a JSON data_ref."""
    peaks = _synthetic_peaks(15)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(peaks, f)
        tmp_path = f.name

    try:
        resp = domain.execute_method(
            "deisotoping", data_ref=tmp_path, assumptions=[],
            params={"top_n": 5},  # peaks absent — loaded from data_ref
        )
        _assert_ok_shape(resp, "deisotoping")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_execute_method_params_take_precedence_over_data_ref(domain):
    """params['blocks_data'] takes precedence over data_ref when both are provided."""
    # data_ref points to a non-existent file — should not matter since params wins
    blocks = _synthetic_blocks(6)
    resp = domain.execute_method(
        "pca", data_ref="/nonexistent/path.json", assumptions=[],
        params={"blocks_data": blocks, "n_components": 2},
    )
    _assert_ok_shape(resp, "pca")
