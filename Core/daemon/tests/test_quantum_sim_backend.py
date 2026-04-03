"""QuantumSimBackend tests — compute_class, mock fallback, error handling."""

import pytest


def test_quantum_sim_compute_class():
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    assert backend.compute_class() == "quantum_sim"


def test_mock_fallback_returns_counts():
    """Without Qiskit installed, execute() returns mock bell-state counts."""
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    result = backend.execute(
        method_id="bell_state",
        dataset_ref="",
        assumptions=[],
        params={"shots": 1024},
    )
    assert result["status"] == "ok"
    assert "counts" in result
    assert isinstance(result["counts"], dict)
    # Mock splits shots between "00" and "11"
    total = sum(result["counts"].values())
    assert total == 1024


def test_mock_fallback_has_exploratory_true():
    """Quantum runs are automatically exploratory (Main_Source §9A.3)."""
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    result = backend.execute(
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={"shots": 100},
    )
    assert result["exploratory"] is True


def test_quantum_metadata_fields_present():
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    result = backend.execute(
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={"shots": 512, "noise_model": "depolarizing"},
    )
    qm = result["quantum_metadata"]
    assert qm["shots"] == 512
    assert "simulator" in qm
    assert "circuit_depth" in qm
    assert "qubit_count" in qm
    assert qm["noise_model"] == "depolarizing"


def test_mock_fallback_simulator_field():
    """Mock fallback reports simulator='mock_fallback'."""
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    result = backend.execute(
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={},
    )
    assert result["quantum_metadata"]["simulator"] == "mock_fallback"


def test_custom_shots_respected():
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    result = backend.execute(
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={"shots": 2048},
    )
    total = sum(result["counts"].values())
    assert total == 2048


def test_error_case_exploratory_still_true():
    """Even on error, exploratory must be True."""
    from src.runner.backends.quantum_sim import QuantumSimBackend

    backend = QuantumSimBackend()
    # Normally a bad QASM would cause an error if Qiskit is available,
    # but with mock fallback it gracefully returns counts.
    # This test verifies the contract: exploratory=True always present.
    result = backend.execute(
        method_id="test",
        dataset_ref="",
        assumptions=[],
        params={"circuit_qasm": "INVALID QASM"},
    )
    assert result["exploratory"] is True
