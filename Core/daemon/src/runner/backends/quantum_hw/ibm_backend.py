"""
IBM Quantum backend — Qiskit Runtime integration.

Main_Source §9A.3: Quantum runs are automatically exploratory.
Requires IBMQ_TOKEN environment variable for real QPU access.
Without the token, raises CredentialError (caller handles fallback).
"""
from __future__ import annotations

import logging
import os
import time
import uuid

from .credential import CredentialError, require_ibmq_token

logger = logging.getLogger("scientificstate.daemon.quantum_hw.ibm")

# ---------------------------------------------------------------------------
# Configurable timeouts & retries via environment
# ---------------------------------------------------------------------------
IBMQ_TIMEOUT = int(os.environ.get("IBMQ_TIMEOUT_SECONDS", "300"))
IBMQ_MAX_RETRIES = int(os.environ.get("IBMQ_MAX_RETRIES", "3"))

# Circuit-breaker settings
_CB_FAILURE_THRESHOLD = 5
_CB_RECOVERY_SECONDS = 300  # 5 minutes


class IBMQuantumBackend:
    """IBM Quantum hardware backend via Qiskit Runtime."""

    def __init__(self) -> None:
        self._token: str | None = None
        # Circuit-breaker state
        self._consecutive_failures: int = 0
        self._circuit_open_until: float = 0.0

    # ------------------------------------------------------------------
    # Circuit-breaker helpers
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self) -> None:
        """Raise RuntimeError if the circuit breaker is open."""
        if self._consecutive_failures >= _CB_FAILURE_THRESHOLD:
            now = time.monotonic()
            if now < self._circuit_open_until:
                remaining = int(self._circuit_open_until - now)
                raise RuntimeError(
                    f"IBM Quantum circuit breaker open — backend unavailable "
                    f"for {remaining}s after {_CB_FAILURE_THRESHOLD} consecutive failures"
                )
            # Recovery window elapsed — half-open: allow one attempt
            logger.info("Circuit breaker half-open — allowing probe request")

    def _record_failure(self) -> None:
        """Record a consecutive failure; open circuit breaker if threshold reached."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= _CB_FAILURE_THRESHOLD:
            self._circuit_open_until = time.monotonic() + _CB_RECOVERY_SECONDS
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures — "
                "backend unavailable for %ds",
                self._consecutive_failures,
                _CB_RECOVERY_SECONDS,
            )

    def _record_success(self) -> None:
        """Reset failure counter on success."""
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if IBM Quantum credentials, SDK, and circuit breaker allow use."""
        # Circuit breaker check (non-raising)
        if self._consecutive_failures >= _CB_FAILURE_THRESHOLD:
            if time.monotonic() < self._circuit_open_until:
                logger.debug("IBM backend unavailable — circuit breaker open")
                return False

        try:
            self._token = require_ibmq_token()
        except CredentialError:
            return False
        try:
            import qiskit_ibm_runtime  # noqa: F401
            return True
        except ImportError:
            logger.warning("qiskit-ibm-runtime not installed")
            return False

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, circuit_qasm: str, shots: int = 1024) -> dict:
        """
        Submit circuit to IBM Quantum hardware and return results.

        Args:
            circuit_qasm: OpenQASM 3.0 circuit string.
            shots: Number of measurement shots.

        Returns:
            Result dict with counts, execution_witness, and exploratory=True.

        Raises:
            CredentialError: If IBMQ_TOKEN is not set.
            RuntimeError: If execution fails after retries or circuit breaker is open.
        """
        run_id = str(uuid.uuid4())

        # Circuit breaker gate
        self._check_circuit_breaker()

        token = require_ibmq_token()
        # Security: log only token length, never the value
        logger.debug("IBMQ token resolved (length=%d)", len(token))

        last_exc: Exception | None = None

        for attempt in range(1, IBMQ_MAX_RETRIES + 1):
            start_time = time.monotonic()
            try:
                from qiskit import QuantumCircuit
                from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

                service = QiskitRuntimeService(
                    channel="ibm_quantum", token=token
                )
                backend = service.least_busy(min_num_qubits=2, operational=True)
                backend_name = backend.name
                logger.info(
                    "Selected backend: %s (attempt %d/%d)",
                    backend_name, attempt, IBMQ_MAX_RETRIES,
                )

                qc = QuantumCircuit.from_qasm_str(circuit_qasm)

                sampler = SamplerV2(backend)
                job = sampler.run([qc], shots=shots)
                result = job.result()

                # Extract counts from SamplerV2 result
                pub_result = result[0]
                counts_raw = pub_result.data.meas.get_counts()
                str_counts = {str(k): v for k, v in counts_raw.items()}

                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                self._record_success()

                return {
                    "run_id": run_id,
                    "status": "succeeded",
                    "counts": str_counts,
                    "compute_class": "quantum_hw",
                    "execution_witness": {
                        "compute_class": "quantum_hw",
                        "backend_id": backend_name,
                        "quantum_metadata": {
                            "provider": "ibm_quantum",
                            "backend_name": backend_name,
                            "shots": shots,
                            "circuit_depth": qc.depth(),
                            "qubit_count": qc.num_qubits,
                            "execution_time_ms": elapsed_ms,
                        },
                    },
                    "exploratory": True,
                }

            except ImportError:
                raise RuntimeError(
                    "qiskit-ibm-runtime is required for IBM Quantum hardware. "
                    "Install with: pip install 'scientificstate-daemon[quantum-hw]'"
                )
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                last_exc = exc
                self._record_failure()
                logger.warning(
                    "IBM Quantum attempt %d/%d failed (%dms): %s",
                    attempt, IBMQ_MAX_RETRIES, elapsed_ms, exc,
                )
                if attempt < IBMQ_MAX_RETRIES:
                    backoff = 2 ** attempt  # 2s, 4s, 8s
                    logger.info("Retrying in %ds…", backoff)
                    time.sleep(backoff)

        # All retries exhausted
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "IBM Quantum execution failed after %d retries: %s",
            IBMQ_MAX_RETRIES, last_exc,
        )
        return {
            "run_id": run_id,
            "status": "error",
            "error_code": "IBM_QUANTUM_EXECUTION_ERROR",
            "error": str(last_exc),
            "compute_class": "quantum_hw",
            "execution_witness": {
                "compute_class": "quantum_hw",
                "backend_id": "unknown",
                "quantum_metadata": {
                    "provider": "ibm_quantum",
                    "execution_time_ms": elapsed_ms,
                },
            },
            "exploratory": True,
        }
