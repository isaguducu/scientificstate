"""
IBM Quantum backend — Qiskit Runtime integration.

Main_Source §9A.3: Quantum runs are automatically exploratory.
Requires IBMQ_TOKEN environment variable for real QPU access.
Without the token, raises CredentialError (caller handles fallback).
"""
from __future__ import annotations

import logging
import time

from .credential import CredentialError, require_ibmq_token

logger = logging.getLogger("scientificstate.daemon.quantum_hw.ibm")


class IBMQuantumBackend:
    """IBM Quantum hardware backend via Qiskit Runtime."""

    def __init__(self) -> None:
        self._token: str | None = None

    def is_available(self) -> bool:
        """Check if IBM Quantum credentials and SDK are available."""
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

    def execute(self, circuit_qasm: str, shots: int = 1024) -> dict:
        """
        Submit circuit to IBM Quantum hardware and return results.

        Args:
            circuit_qasm: OpenQASM 3.0 circuit string.
            shots: Number of measurement shots.

        Returns:
            Result dict with counts, quantum_metadata, and exploratory=True.

        Raises:
            CredentialError: If IBMQ_TOKEN is not set.
            RuntimeError: If execution fails after retries.
        """
        token = require_ibmq_token()
        start_time = time.monotonic()

        try:
            from qiskit import QuantumCircuit
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

            service = QiskitRuntimeService(
                channel="ibm_quantum", token=token
            )
            backend = service.least_busy(min_num_qubits=2, operational=True)
            logger.info("Selected backend: %s", backend.name)

            qc = QuantumCircuit.from_qasm_str(circuit_qasm)

            sampler = SamplerV2(backend)
            job = sampler.run([qc], shots=shots)
            result = job.result()

            # Extract counts from SamplerV2 result
            pub_result = result[0]
            counts_raw = pub_result.data.meas.get_counts()
            str_counts = {str(k): v for k, v in counts_raw.items()}

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            return {
                "status": "ok",
                "counts": str_counts,
                "quantum_metadata": {
                    "backend_name": backend.name,
                    "shots": shots,
                    "execution_time_ms": elapsed_ms,
                    "circuit_depth": qc.depth(),
                    "qubit_count": qc.num_qubits,
                    "provider": "ibm_quantum",
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
            logger.error("IBM Quantum execution failed: %s", exc)
            return {
                "status": "error",
                "error_code": "IBM_QUANTUM_EXECUTION_ERROR",
                "error": str(exc),
                "quantum_metadata": {
                    "provider": "ibm_quantum",
                    "execution_time_ms": elapsed_ms,
                },
                "exploratory": True,
            }
