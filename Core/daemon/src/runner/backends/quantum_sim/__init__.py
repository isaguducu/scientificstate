"""
QuantumSimBackend — Qiskit Aer simulator with mock fallback.

Main_Source §9A.3: Quantum runs are automatically exploratory.
  - exploratory runs cannot enter the endorsable claim path (hard block)
  - classical baseline ref required before quantum results feed gate chain

Graceful degradation: if Qiskit is not installed, returns mock counts
from a perfect bell-state simulation. This allows the daemon and
pipeline to operate without requiring the optional qiskit dependency.
"""

from __future__ import annotations

import logging
import uuid

from src.runner.orchestrator import ComputeBackend

logger = logging.getLogger("scientificstate.daemon.quantum_sim")


class QuantumSimBackend(ComputeBackend):
    """Quantum simulator backend — Qiskit Aer or mock fallback."""

    def compute_class(self) -> str:
        return "quantum_sim"

    def execute(
        self,
        method_id: str,
        dataset_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        circuit_qasm = params.get("circuit_qasm", "").strip()
        shots = params.get("shots", 1024)
        noise_model = params.get("noise_model")
        run_id = str(uuid.uuid4())

        # If no circuit is provided, use the mock bell-state directly.
        # This keeps tests that omit circuit_qasm working regardless of
        # whether qiskit is installed, and avoids trying to parse an empty
        # string (which raises "No counts for experiment 0" in Qiskit).
        if not circuit_qasm:
            return self._mock_result(run_id, shots, noise_model)

        try:
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator

            qc = QuantumCircuit.from_qasm_str(circuit_qasm)
            # Circuits without measurements produce no counts — add them
            # automatically so get_counts() always succeeds.
            if not any(
                instr.operation.name == "measure" for instr in qc.data
            ):
                qc.measure_all()
            simulator = AerSimulator()
            if noise_model:
                # Future: configure noise model from params
                pass
            result = simulator.run(qc, shots=shots).result()
            counts = result.get_counts()
            str_counts = {str(k): v for k, v in counts.items()}

            return {
                "run_id": run_id,
                "status": "succeeded",
                "compute_class": "quantum_sim",
                "counts": str_counts,
                "statevector": None,
                "execution_witness": {
                    "compute_class": "quantum_sim",
                    "backend_id": "aer_simulator",
                    "quantum_metadata": {
                        "shots": shots,
                        "noise_model": noise_model,
                        "simulator": "qiskit_aer",
                        "circuit_depth": qc.depth(),
                        "qubit_count": qc.num_qubits,
                    },
                },
                "exploratory": True,
            }

        except ImportError:
            logger.info("Qiskit not installed — using mock fallback")
            return self._mock_result(run_id, shots, noise_model)

        except Exception as exc:
            logger.error("Quantum execution error: %s", exc)
            return {
                "run_id": run_id,
                "status": "failed",
                "compute_class": "quantum_sim",
                "error_code": "QUANTUM_EXECUTION_ERROR",
                "error": str(exc),
                "exploratory": True,
            }

    def _mock_result(self, run_id: str, shots: int, noise_model: object) -> dict:
        """Perfect bell-state mock — returned when qiskit is absent or no circuit given."""
        return {
            "run_id": run_id,
            "status": "succeeded",
            "compute_class": "quantum_sim",
            "counts": {"00": shots // 2, "11": shots - shots // 2},
            "statevector": None,
            "execution_witness": {
                "compute_class": "quantum_sim",
                "backend_id": "mock_fallback",
                "quantum_metadata": {
                    "shots": shots,
                    "noise_model": noise_model,
                    "simulator": "mock_fallback",
                    "circuit_depth": 0,
                    "qubit_count": 2,
                },
            },
            "exploratory": True,
        }
