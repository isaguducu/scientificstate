"""
test_result_adapter.py — Phase 1-A: result adapter + compute-run-result schema validation.

For every method:
  execute_method() → adapt_to_run_result() → jsonschema.validate against
  compute-run-result.schema.json

Also tests error-path adaptation (status="error" → status="failed").
"""
import json
from pathlib import Path
from typing import Dict, List

import jsonschema
import numpy as np
import pytest

SCHEMA_PATH = (
    Path(__file__).parents[3] / "Core" / "contracts" / "jsonschema"
    / "compute-run-result.schema.json"
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def domain():
    from polymer_science import PolymerScienceDomain
    return PolymerScienceDomain()


@pytest.fixture(scope="module")
def adapter():
    from polymer_science.result_adapter import adapt_to_run_result
    return adapt_to_run_result


SAMPLE_RUN_CONTEXT = {
    "run_id": "run-test-001",
    "workspace_id": "ws-test-001",
    "started_at": "2026-04-04T10:00:00+00:00",
}


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


def _validate(result_dict: dict, schema: dict) -> None:
    """jsonschema validate — raises jsonschema.ValidationError on failure."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(result_dict))
    assert not errors, "\n".join(
        f"  {e.json_path}: {e.message}" for e in errors[:5]
    )


# ── PCA ───────────────────────────────────────────────────────────────────────

def test_adapter_pca_schema_valid(domain, adapter, schema):
    """PCA execute_method → adapt → compute-run-result PASS."""
    output = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6), "n_components": 2},
    )
    assert output["status"] == "ok"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "succeeded"


# ── HCA ───────────────────────────────────────────────────────────────────────

def test_adapter_hca_schema_valid(domain, adapter, schema):
    """HCA execute_method → adapt → compute-run-result PASS."""
    output = domain.execute_method(
        "hca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6), "n_clusters": 2},
    )
    assert output["status"] == "ok"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "succeeded"


# ── KMD ───────────────────────────────────────────────────────────────────────

def test_adapter_kmd_schema_valid(domain, adapter, schema):
    """KMD execute_method → adapt → compute-run-result PASS."""
    from polymer_science.methods.hca import compute_hca
    blocks = _synthetic_blocks(6)
    hca_result = compute_hca(blocks, n_clusters=2)
    output = domain.execute_method(
        "kmd_analysis", data_ref="", assumptions=[],
        params={"hca_result": hca_result, "blocks_data": blocks, "polymer": "PS"},
    )
    assert output["status"] == "ok"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "succeeded"


# ── Deisotoping ───────────────────────────────────────────────────────────────

def test_adapter_deisotoping_schema_valid(domain, adapter, schema):
    """Deisotoping execute_method → adapt → compute-run-result PASS."""
    output = domain.execute_method(
        "deisotoping", data_ref="", assumptions=[],
        params={"peaks": _synthetic_peaks(20), "top_n": 10},
    )
    assert output["status"] == "ok"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "succeeded"


# ── Fragment matching ─────────────────────────────────────────────────────────

def test_adapter_fragment_matching_schema_valid(domain, adapter, schema):
    """Fragment matching execute_method → adapt → compute-run-result PASS."""
    db = domain.get_fragment_db()
    ps_frags = db.get("PS", {}).get("fragments", [])
    if not ps_frags:
        pytest.skip("No PS fragments in fragment_db.json")
    peaks = [{"mz": f["mz"] + 0.1, "intensity": 1000.0} for f in ps_frags[:5]]
    output = domain.execute_method(
        "fragment_matching", data_ref="", assumptions=[],
        params={"peaks": peaks, "polymer": "PS", "abs_tol": 0.5},
    )
    assert output["status"] == "ok"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "succeeded"


# ── Error path ────────────────────────────────────────────────────────────────

def test_adapter_error_path_status_failed(adapter, schema):
    """status='error' → adapt → status='failed', error object populated."""
    error_output = {
        "method_id": "pca",
        "domain_id": "polymer_science",
        "status": "error",
        "error_code": "INVALID_PARAMS",
        "error": "params['blocks_data'] is required for pca.",
        "diagnostics": {},
    }
    result = adapter(error_output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "INVALID_PARAMS"
    assert "blocks_data" in result["error"]["message"]


def test_adapter_error_path_unknown_method(adapter, schema):
    """UNKNOWN_METHOD error adapts correctly to compute-run-result."""
    from polymer_science import PolymerScienceDomain
    domain = PolymerScienceDomain()
    output = domain.execute_method("bad_method", data_ref="", assumptions=[], params={})
    assert output["status"] == "error"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "UNKNOWN_METHOD"


def test_adapter_error_path_missing_pca_params(domain, adapter, schema):
    """Missing pca params error adapts to compute-run-result failed."""
    output = domain.execute_method("pca", data_ref="", assumptions=[], params={})
    assert output["status"] == "error"
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate(result, schema)
    assert result["status"] == "failed"


# ── Structure invariants ──────────────────────────────────────────────────────

def test_adapter_succeeded_has_execution_witness(domain, adapter, schema):
    """Succeeded result always has execution_witness with compute_class='classical'."""
    output = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6)},
    )
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    assert result["status"] == "succeeded"
    ew = result["execution_witness"]
    assert ew["compute_class"] == "classical"
    assert ew["backend_id"] == "polymer_science"


def test_adapter_succeeded_ssv_ref_absent(domain, adapter, schema):
    """ssv_ref is absent in adapter output (daemon fills it later; schema type=string, not null)."""
    output = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6)},
    )
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    assert "ssv_ref" not in result, "ssv_ref must be omitted until daemon sets it"


def test_adapter_echoes_run_context(domain, adapter, schema):
    """adapt_to_run_result echoes run_id, workspace_id, started_at."""
    ctx = {
        "run_id": "run-unique-xyz",
        "workspace_id": "ws-unique-abc",
        "started_at": "2026-04-04T12:30:00+00:00",
    }
    output = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6)},
    )
    result = adapter(output, ctx)
    assert result["run_id"] == "run-unique-xyz"
    assert result["workspace_id"] == "ws-unique-abc"
    assert result["started_at"] == "2026-04-04T12:30:00+00:00"


def test_adapter_finished_at_present(domain, adapter, schema):
    """adapt_to_run_result always sets finished_at."""
    output = domain.execute_method(
        "pca", data_ref="", assumptions=[],
        params={"blocks_data": _synthetic_blocks(6)},
    )
    result = adapter(output, SAMPLE_RUN_CONTEXT)
    assert "finished_at" in result
    assert result["finished_at"] is not None
