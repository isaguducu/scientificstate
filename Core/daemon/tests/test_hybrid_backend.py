"""HybridBackend tests — parallel execution, result aggregation, exploratory flag."""

import os
from unittest.mock import patch


# ── HybridBackend compute_class ───────────────────────────────────────────────

def test_hybrid_compute_class():
    from src.runner.backends.hybrid import HybridBackend

    backend = HybridBackend()
    assert backend.compute_class() == "hybrid"


# ── Hybrid orchestrator unit tests ────────────────────────────────────────────

def test_orchestrator_parallel_execution():
    """Both branches execute and results are aggregated."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {
            "status": "ok",
            "domain_id": "polymer_science",
            "result": {"mw": 50000.0, "pdi": 1.2},
        }

    def quantum_fn(m, d, a, p):
        return {
            "status": "ok",
            "counts": {"00": 512, "11": 512},
            "quantum_metadata": {
                "shots": 1024,
                "simulator": "mock_fallback",
                "backend_name": "mock",
            },
            "exploratory": True,
        }

    result = execute_hybrid(
        classical_fn=classical_fn,
        quantum_fn=quantum_fn,
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={},
    )

    assert result["status"] == "ok"
    assert result["compute_class"] == "hybrid"
    assert result["exploratory"] is True
    assert "execution_witnesses" in result
    assert "classical" in result["execution_witnesses"]
    assert "quantum" in result["execution_witnesses"]


def test_orchestrator_classical_result_preserved():
    """Classical branch result is accessible in aggregated output."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {"mw": 42000.0}, "domain_id": "test"}

    def quantum_fn(m, d, a, p):
        return {
            "status": "ok", "counts": {"0": 1024},
            "quantum_metadata": {"shots": 1024, "simulator": "mock"},
        }

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["classical_result"]["mw"] == 42000.0


def test_orchestrator_quantum_counts_preserved():
    """Quantum branch counts are accessible in aggregated output."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {}, "domain_id": "test"}

    def quantum_fn(m, d, a, p):
        return {
            "status": "ok", "counts": {"00": 500, "11": 524},
            "quantum_metadata": {"shots": 1024, "simulator": "aer"},
        }

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["counts"]["00"] == 500
    assert result["counts"]["11"] == 524


def test_orchestrator_partial_failure():
    """If one branch fails, result is partial with error info."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {"mw": 50000.0}, "domain_id": "test"}

    def quantum_fn(m, d, a, p):
        raise RuntimeError("QPU unavailable")

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["status"] == "partial"
    assert result["exploratory"] is True
    assert "quantum" in result["branch_errors"]
    assert "classical" in result["execution_witnesses"]


def test_orchestrator_both_fail():
    """If both branches fail, result is error."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        raise RuntimeError("Classical failed")

    def quantum_fn(m, d, a, p):
        raise RuntimeError("Quantum failed")

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["status"] == "error"
    assert result["error_code"] == "HYBRID_ALL_BRANCHES_FAILED"
    assert result["exploratory"] is True


def test_orchestrator_always_exploratory():
    """Hybrid results are always exploratory (M3 hard rule)."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {}, "domain_id": "test"}

    def quantum_fn(m, d, a, p):
        return {"status": "ok", "counts": {}, "quantum_metadata": {"shots": 100, "simulator": "m"}}

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["exploratory"] is True


def test_orchestrator_execution_witnesses_separate():
    """Each branch has its own execution witness."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {"x": 1}, "domain_id": "polymer"}

    def quantum_fn(m, d, a, p):
        return {
            "status": "ok",
            "counts": {"0": 1024},
            "quantum_metadata": {
                "shots": 1024,
                "backend_name": "ibm_brisbane",
                "simulator": "qiskit_aer",
            },
            "compute_class": "quantum_sim",
        }

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    witnesses = result["execution_witnesses"]

    assert witnesses["classical"]["compute_class"] == "classical"
    assert witnesses["quantum"]["compute_class"] == "quantum_sim"
    assert witnesses["quantum"]["backend_id"] == "ibm_brisbane"


# ── HybridBackend integration (with fallback quantum) ────────────────────────

def test_hybrid_backend_execute_with_fallback():
    """HybridBackend executes with quantum_sim fallback when no QPU credentials."""
    env = {k: v for k, v in os.environ.items() if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.hybrid import HybridBackend

        backend = HybridBackend()
        result = backend.execute(
            method_id="test",
            dataset_ref="",
            assumptions=[],
            params={"shots": 256},
        )

        assert result["compute_class"] == "hybrid"
        assert result["exploratory"] is True
        assert "execution_witnesses" in result


# ── Quantum metadata in hybrid results ────────────────────────────────────────

def test_hybrid_quantum_metadata_present():
    """Hybrid result includes quantum_metadata from quantum branch."""
    from src.runner.backends.hybrid.orchestrator import execute_hybrid

    def classical_fn(m, d, a, p):
        return {"status": "ok", "result": {}, "domain_id": "test"}

    def quantum_fn(m, d, a, p):
        return {
            "status": "ok",
            "counts": {"0": 512, "1": 512},
            "quantum_metadata": {
                "shots": 1024,
                "simulator": "aer",
                "circuit_depth": 3,
                "qubit_count": 2,
            },
        }

    result = execute_hybrid(classical_fn, quantum_fn, "t", "", [], {})
    assert result["quantum_metadata"]["shots"] == 1024
    assert result["quantum_metadata"]["circuit_depth"] == 3
