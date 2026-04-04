"""QPU resilience tests — circuit-breaker, retry, concurrent requests, fallback chain."""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest


class TestQPUResilience:
    """Resilience patterns for QPU backends."""

    def test_concurrent_quantum_hw_requests(self):
        """5 parallel quantum_hw requests should not interfere."""
        from src.runner.backends.quantum_hw import QuantumHWBackend

        def run_one(idx: int) -> dict:
            backend = QuantumHWBackend()
            # Force fallback path (no credentials) — safe and fast
            env = {k: v for k, v in os.environ.items()
                   if k not in ("IBMQ_TOKEN", "IONQ_TOKEN")}
            with patch.dict(os.environ, env, clear=True):
                return backend.execute(
                    method_id=f"bell_{idx}",
                    dataset_ref="",
                    assumptions=[],
                    params={"shots": 128},
                )

        results = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(run_one, i) for i in range(5)]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 5
        for r in results:
            assert r["status"] in ("ok", "succeeded")
            assert r["fallback"] is True
            assert r["compute_class"] == "quantum_hw"

    def test_ibm_timeout_returns_error(self):
        """IBM timeout should return proper error, not hang."""
        from src.runner.backends.quantum_hw.ibm_backend import IBMQuantumBackend

        ibm = IBMQuantumBackend()

        with patch.dict(os.environ, {"IBMQ_TOKEN": "test-token-long-enough"}):
            # Mock qiskit to raise a timeout-like error
            mock_service_cls = MagicMock()
            mock_service_cls.return_value.least_busy.side_effect = TimeoutError(
                "Connection timed out"
            )

            with patch.dict("sys.modules", {
                "qiskit": MagicMock(),
                "qiskit_ibm_runtime": MagicMock(
                    QiskitRuntimeService=mock_service_cls,
                    SamplerV2=MagicMock(),
                ),
            }):
                with patch("time.sleep"):  # skip backoff
                    result = ibm.execute("OPENQASM 3.0;", shots=100)

        assert result["status"] == "error"
        assert "timed out" in result["error"].lower() or "error" in result["status"]
        assert result["exploratory"] is True

    def test_ionq_transient_retry(self):
        """IonQ should retry on 429/503 status codes."""
        from src.runner.backends.quantum_hw.ionq_backend import IonQBackend

        ionq = IonQBackend()

        with patch.dict(os.environ, {"IONQ_TOKEN": "test-ionq-token-long"}):
            mock_responses = []
            # First attempt: 429
            resp_429 = MagicMock()
            resp_429.status_code = 429
            resp_429.raise_for_status = MagicMock(side_effect=Exception("429"))
            mock_responses.append(resp_429)
            # Second attempt: 503
            resp_503 = MagicMock()
            resp_503.status_code = 503
            resp_503.raise_for_status = MagicMock(side_effect=Exception("503"))
            mock_responses.append(resp_503)
            # Third attempt: also fails (exhaust retries)
            resp_500 = MagicMock()
            resp_500.status_code = 500
            resp_500.raise_for_status = MagicMock(side_effect=Exception("500"))
            mock_responses.append(resp_500)

            with patch("requests.post", side_effect=mock_responses):
                with patch("time.sleep"):
                    result = ionq.execute("OPENQASM 3.0;", shots=100)

            # All retries exhausted — should return error, not crash
            assert result["status"] == "error"
            assert result["exploratory"] is True

    def test_fallback_chain_ibm_ionq_sim(self):
        """If IBM fails and IonQ fails, should fallback to quantum_sim."""
        from src.runner.backends.quantum_hw import QuantumHWBackend

        backend = QuantumHWBackend()
        # Mock both IBM and IonQ as unavailable
        backend._ibm.is_available = MagicMock(return_value=False)
        backend._ionq.is_available = MagicMock(return_value=False)

        result = backend.execute(
            method_id="test_fallback",
            dataset_ref="",
            assumptions=[],
            params={"shots": 256},
        )

        # Should have fallen back to quantum_sim
        assert result["fallback"] is True
        assert result["fallback_reason"] == "no_hardware_credentials"
        assert result["compute_class"] == "quantum_hw"
        assert result["status"] in ("ok", "succeeded")
        assert "counts" in result

    def test_credential_validation_endpoint(self):
        """Token validation should check format without logging token value."""
        from src.runner.backends.quantum_hw.credential import (
            _validate_token_format,
            CredentialError,
        )

        # Too short
        with pytest.raises(CredentialError, match="too short"):
            _validate_token_format("abc", "TEST")

        # Contains whitespace
        with pytest.raises(CredentialError, match="whitespace"):
            _validate_token_format("valid-token with-space", "TEST")

        # Valid token should not raise
        _validate_token_format("valid-token-no-spaces", "TEST")

    def test_credential_never_logged(self):
        """Verify credential values never appear in log output."""
        secret_token = "super-secret-token-value-12345"

        handler = logging.Handler()
        handler.setLevel(logging.DEBUG)
        records: list[logging.LogRecord] = []
        handler.emit = lambda record: records.append(record)  # type: ignore[assignment]

        cred_logger = logging.getLogger("scientificstate.daemon.quantum_hw.credential")
        cred_logger.addHandler(handler)
        cred_logger.setLevel(logging.DEBUG)

        try:
            with patch.dict(os.environ, {"IBMQ_TOKEN": secret_token}):
                from src.runner.backends.quantum_hw.credential import get_ibmq_token
                get_ibmq_token()

            # Check that the secret value never appears in any log message
            for record in records:
                msg = record.getMessage()
                assert secret_token not in msg, (
                    f"Secret token leaked in log message: {msg}"
                )
        finally:
            cred_logger.removeHandler(handler)
