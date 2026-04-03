"""
test_backend_integration.py — Phase 1-A integration test.

Tests the full chain:
  ClassicalBackend → DomainRegistry → PolymerScienceDomain → result_adapter

conftest.py adds Core/daemon to sys.path so ClassicalBackend is importable.
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

SAMPLE_RUN_CONTEXT = {
    "run_id": "integration-run-001",
    "workspace_id": "integration-ws-001",
    "started_at": "2026-04-04T10:00:00+00:00",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def registry():
    """DomainRegistry with PolymerScienceDomain registered."""
    from scientificstate.domain_registry.registry import DomainRegistry
    from polymer_science import PolymerScienceDomain
    reg = DomainRegistry()
    reg.register(PolymerScienceDomain())
    return reg


@pytest.fixture(scope="module")
def backend(registry):
    """ClassicalBackend wired to the polymer registry."""
    from src.runner.backends.classical import ClassicalBackend
    return ClassicalBackend(domain_registry=registry)


@pytest.fixture(scope="module")
def adapter():
    from polymer_science.result_adapter import adapt_to_run_result
    return adapt_to_run_result


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


def _validate_schema(result_dict: dict, schema: dict) -> None:
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(result_dict))
    assert not errors, "\n".join(
        f"  {e.json_path}: {e.message}" for e in errors[:5]
    )


# ── Registry setup tests ──────────────────────────────────────────────────────

def test_registry_contains_polymer_science(registry):
    """DomainRegistry must contain polymer_science after manual register."""
    assert "polymer_science" in registry


def test_backend_compute_class(backend):
    """ClassicalBackend.compute_class() must return 'classical'."""
    assert backend.compute_class() == "classical"


# ── PCA full chain ─────────────────────────────────────────────────────────────

def test_classical_backend_pca(backend, adapter, schema):
    """ClassicalBackend → polymer_science pca → adapt → schema PASS."""
    params = {
        "domain_id": "polymer_science",
        "blocks_data": _synthetic_blocks(6),
        "n_components": 2,
    }
    output = backend.execute("pca", dataset_ref="", assumptions=[], params=params)
    assert output["domain_id"] == "polymer_science"
    assert output["status"] == "ok"
    run_result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate_schema(run_result, schema)
    assert run_result["status"] == "succeeded"


# ── HCA full chain ─────────────────────────────────────────────────────────────

def test_classical_backend_hca(backend, adapter, schema):
    """ClassicalBackend → polymer_science hca → adapt → schema PASS."""
    params = {
        "domain_id": "polymer_science",
        "blocks_data": _synthetic_blocks(6),
        "n_clusters": 2,
    }
    output = backend.execute("hca", dataset_ref="", assumptions=[], params=params)
    assert output["domain_id"] == "polymer_science"
    assert output["status"] == "ok"
    run_result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate_schema(run_result, schema)
    assert run_result["status"] == "succeeded"


# ── KMD full chain ─────────────────────────────────────────────────────────────

def test_classical_backend_kmd(backend, adapter, schema):
    """ClassicalBackend → polymer_science kmd_analysis → adapt → schema PASS."""
    from polymer_science.methods.hca import compute_hca
    blocks = _synthetic_blocks(6)
    hca_result = compute_hca(blocks, n_clusters=2)
    params = {
        "domain_id": "polymer_science",
        "hca_result": hca_result,
        "blocks_data": blocks,
        "polymer": "PS",
    }
    output = backend.execute("kmd_analysis", dataset_ref="", assumptions=[], params=params)
    assert output["domain_id"] == "polymer_science"
    assert output["status"] == "ok"
    run_result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate_schema(run_result, schema)
    assert run_result["status"] == "succeeded"


# ── Deisotoping full chain ────────────────────────────────────────────────────

def test_classical_backend_deisotoping(backend, adapter, schema):
    """ClassicalBackend → polymer_science deisotoping → adapt → schema PASS."""
    params = {
        "domain_id": "polymer_science",
        "peaks": _synthetic_peaks(20),
        "top_n": 10,
    }
    output = backend.execute("deisotoping", dataset_ref="", assumptions=[], params=params)
    assert output["domain_id"] == "polymer_science"
    assert output["status"] == "ok"
    run_result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate_schema(run_result, schema)
    assert run_result["status"] == "succeeded"


# ── Fragment matching full chain ──────────────────────────────────────────────

def test_classical_backend_fragment_matching(backend, adapter, schema, registry):
    """ClassicalBackend → polymer_science fragment_matching → adapt → schema PASS."""
    domain = registry.get("polymer_science")
    db = domain.get_fragment_db()
    ps_frags = db.get("PS", {}).get("fragments", [])
    if not ps_frags:
        pytest.skip("No PS fragments in fragment_db.json")
    peaks = [{"mz": f["mz"] + 0.1, "intensity": 1000.0} for f in ps_frags[:5]]
    params = {
        "domain_id": "polymer_science",
        "peaks": peaks,
        "polymer": "PS",
        "abs_tol": 0.5,
    }
    output = backend.execute(
        "fragment_matching", dataset_ref="", assumptions=[], params=params
    )
    assert output["domain_id"] == "polymer_science"
    assert output["status"] == "ok"
    run_result = adapter(output, SAMPLE_RUN_CONTEXT)
    _validate_schema(run_result, schema)
    assert run_result["status"] == "succeeded"


# ── Unknown domain raises ValueError ─────────────────────────────────────────

def test_classical_backend_unknown_domain_raises(backend):
    """ClassicalBackend raises ValueError for unregistered domain."""
    with pytest.raises(ValueError, match="Unknown domain"):
        backend.execute(
            "pca", dataset_ref="", assumptions=[],
            params={"domain_id": "nonexistent_domain"},
        )


def test_classical_backend_missing_domain_id_raises(backend):
    """ClassicalBackend raises ValueError when domain_id is absent from params."""
    with pytest.raises(ValueError, match="domain_id"):
        backend.execute("pca", dataset_ref="", assumptions=[], params={})
