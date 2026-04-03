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
        circuit_qasm = params.get("circuit_qasm", "")
        shots = params.get("shots", 1024)
        noise_model = params.get("noise_model")

        try:
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator

            qc = QuantumCircuit.from_qasm_str(circuit_qasm)
            simulator = AerSimulator()
            if noise_model:
                # Future: configure noise model from params
                pass
            result = simulator.run(qc, shots=shots).result()
            counts = result.get_counts()
            str_counts = {str(k): v for k, v in counts.items()}

            return {
                "status": "ok",
                "counts": str_counts,
                "quantum_metadata": {
                    "shots": shots,
                    "noise_model": noise_model,
                    "simulator": "qiskit_aer",
                    "circuit_depth": qc.depth(),
                    "qubit_count": qc.num_qubits,
                },
                "exploratory": True,
            }

        except ImportError:
            logger.info("Qiskit not installed — using mock fallback")
            return {
                "status": "ok",
                "counts": {"00": shots // 2, "11": shots // 2},
                "quantum_metadata": {
                    "shots": shots,
                    "noise_model": noise_model,
                    "simulator": "mock_fallback",
                    "circuit_depth": 0,
                    "qubit_count": 2,
                },
                "exploratory": True,
            }

        except Exception as exc:
            logger.error("Quantum execution error: %s", exc)
            return {
                "status": "error",
                "error_code": "QUANTUM_EXECUTION_ERROR",
                "error": str(exc),
                "exploratory": True,
            }
