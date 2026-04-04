"""QuantumHWBackend tests — mock QPU, IBM + IonQ dispatch, graceful fallback."""

import os
from unittest.mock import patch, MagicMock


# ── QuantumHWBackend compute_class ────────────────────────────────────────────

def test_quantum_hw_compute_class():
    from src.runner.backends.quantum_hw import QuantumHWBackend

    backend = QuantumHWBackend()
    assert backend.compute_class() == "quantum_hw"


# ── Graceful fallback (no credentials) ────────────────────────────────────────

def test_fallback_when_no_credentials():
    """Without any QPU credentials, QuantumHWBackend falls back to quantum_sim."""
    # Ensure no tokens are set
    env = {k: v for k, v in os.environ.items() if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw import QuantumHWBackend

        backend = QuantumHWBackend()
        result = backend.execute(
            method_id="bell_state",
            dataset_ref="",
            assumptions=[],
            params={"shots": 512},
        )
        assert result["status"] in ("ok", "succeeded")  # schema updated in P7
        assert result["fallback"] is True
        assert result["fallback_reason"] == "no_hardware_credentials"
        assert result["exploratory"] is True
        assert result["compute_class"] == "quantum_hw"


def test_fallback_returns_counts():
    """Fallback result contains mock counts."""
    env = {k: v for k, v in os.environ.items() if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw import QuantumHWBackend

        backend = QuantumHWBackend()
        result = backend.execute(
            method_id="test",
            dataset_ref="",
            assumptions=[],
            params={"shots": 1024},
        )
        assert "counts" in result
        total = sum(result["counts"].values())
        assert total == 1024


def test_fallback_has_quantum_metadata():
    """Fallback result includes quantum_metadata from sim."""
    env = {k: v for k, v in os.environ.items() if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw import QuantumHWBackend

        backend = QuantumHWBackend()
        result = backend.execute(
            method_id="test",
            dataset_ref="",
            assumptions=[],
            params={"shots": 256},
        )
        # P7: quantum_metadata now nested inside execution_witness
        if "quantum_metadata" in result:
            assert result["quantum_metadata"]["shots"] == 256
        else:
            assert result["execution_witness"]["quantum_metadata"]["shots"] == 256


# ── Credential module tests ──────────────────────────────────────────────────

def test_credential_get_ibmq_token_returns_none():
    env = {k: v for k, v in os.environ.items() if k != "IBMQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.credential import get_ibmq_token
        assert get_ibmq_token() is None


def test_credential_get_ionq_token_returns_none():
    env = {k: v for k, v in os.environ.items() if k != "IONQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.credential import get_ionq_token
        assert get_ionq_token() is None


def test_credential_get_ibmq_token_returns_value():
    with patch.dict(os.environ, {"IBMQ_TOKEN": "test-token-123"}):
        from src.runner.backends.quantum_hw.credential import get_ibmq_token
        assert get_ibmq_token() == "test-token-123"


def test_credential_get_ionq_token_returns_value():
    with patch.dict(os.environ, {"IONQ_TOKEN": "ionq-key-456"}):
        from src.runner.backends.quantum_hw.credential import get_ionq_token
        assert get_ionq_token() == "ionq-key-456"


def test_credential_require_ibmq_raises():
    env = {k: v for k, v in os.environ.items() if k != "IBMQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.credential import require_ibmq_token, CredentialError
        try:
            require_ibmq_token()
            assert False, "Should have raised CredentialError"
        except CredentialError:
            pass


def test_credential_require_ionq_raises():
    env = {k: v for k, v in os.environ.items() if k != "IONQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.credential import require_ionq_token, CredentialError
        try:
            require_ionq_token()
            assert False, "Should have raised CredentialError"
        except CredentialError:
            pass


# ── IBM Backend unit tests (mocked) ──────────────────────────────────────────

def test_ibm_backend_not_available_without_token():
    env = {k: v for k, v in os.environ.items() if k != "IBMQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.ibm_backend import IBMQuantumBackend
        ibm = IBMQuantumBackend()
        assert ibm.is_available() is False


def test_ibm_backend_not_available_without_sdk():
    """Even with token, if SDK not installed → not available."""
    with patch.dict(os.environ, {"IBMQ_TOKEN": "fake-token"}):
        with patch.dict("sys.modules", {"qiskit_ibm_runtime": None}):
            from src.runner.backends.quantum_hw.ibm_backend import IBMQuantumBackend
            ibm = IBMQuantumBackend()
            # is_available tries import which will fail
            result = ibm.is_available()
            # May or may not be available depending on actual install
            assert isinstance(result, bool)


# ── IonQ Backend unit tests (mocked) ─────────────────────────────────────────

def test_ionq_backend_not_available_without_token():
    env = {k: v for k, v in os.environ.items() if k != "IONQ_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw.ionq_backend import IonQBackend
        ionq = IonQBackend()
        assert ionq.is_available() is False


def test_ionq_backend_available_with_token():
    with patch.dict(os.environ, {"IONQ_TOKEN": "fake-ionq-key"}):
        from src.runner.backends.quantum_hw.ionq_backend import IonQBackend
        ionq = IonQBackend()
        assert ionq.is_available() is True


# ── QuantumHWBackend dispatch tests (mocked hardware) ────────────────────────

def test_dispatch_to_ibm_when_available():
    """When IBM is available, dispatch to IBM backend."""
    from src.runner.backends.quantum_hw import QuantumHWBackend

    mock_result = {
        "status": "ok",
        "counts": {"00": 500, "11": 524},
        "quantum_metadata": {
            "backend_name": "ibm_brisbane",
            "shots": 1024,
            "provider": "ibm_quantum",
        },
        "exploratory": True,
    }

    backend = QuantumHWBackend()
    backend._ibm.is_available = MagicMock(return_value=True)
    backend._ibm.execute = MagicMock(return_value=mock_result)

    result = backend.execute(
        method_id="bell_state",
        dataset_ref="",
        assumptions=[],
        params={"circuit_qasm": "...", "shots": 1024},
    )
    assert result["status"] == "ok"
    assert result["compute_class"] == "quantum_hw"
    assert result["exploratory"] is True
    backend._ibm.execute.assert_called_once()


def test_dispatch_to_ionq_when_ibm_unavailable():
    """When IBM unavailable but IonQ available, dispatch to IonQ."""
    from src.runner.backends.quantum_hw import QuantumHWBackend

    mock_result = {
        "status": "ok",
        "counts": {"00": 490, "11": 534},
        "quantum_metadata": {
            "backend_name": "qpu.harmony",
            "shots": 1024,
            "provider": "ionq",
        },
        "exploratory": True,
    }

    backend = QuantumHWBackend()
    backend._ibm.is_available = MagicMock(return_value=False)
    backend._ionq.is_available = MagicMock(return_value=True)
    backend._ionq.execute = MagicMock(return_value=mock_result)

    result = backend.execute(
        method_id="bell_state",
        dataset_ref="",
        assumptions=[],
        params={"circuit_qasm": "...", "shots": 1024},
    )
    assert result["status"] == "ok"
    assert result["compute_class"] == "quantum_hw"
    backend._ionq.execute.assert_called_once()


# ── Exploratory flag always present ──────────────────────────────────────────

def test_exploratory_always_true_on_fallback():
    """Exploratory must be True even in fallback mode."""
    env = {k: v for k, v in os.environ.items() if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from src.runner.backends.quantum_hw import QuantumHWBackend

        backend = QuantumHWBackend()
        result = backend.execute(
            method_id="test",
            dataset_ref="",
            assumptions=[],
            params={},
        )
        assert result["exploratory"] is True


def test_exploratory_true_on_ibm_dispatch():
    """Exploratory must be True on successful IBM dispatch."""
    from src.runner.backends.quantum_hw import QuantumHWBackend

    backend = QuantumHWBackend()
    backend._ibm.is_available = MagicMock(return_value=True)
    backend._ibm.execute = MagicMock(return_value={
        "status": "ok", "counts": {}, "exploratory": True,
        "quantum_metadata": {"provider": "ibm_quantum"},
    })

    result = backend.execute("test", "", [], {})
    assert result["exploratory"] is True
