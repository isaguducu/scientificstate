"""
QuantumHWBackend — real quantum hardware dispatcher.

Main_Source §9A.3: Quantum runs are automatically exploratory.
  - exploratory runs cannot enter the endorsable claim path (hard block)
  - classical baseline ref required before quantum results feed gate chain

Dispatch order: IBM Quantum → IonQ → graceful fallback to quantum_sim.
Graceful fallback: if no credentials are available, delegates to
QuantumSimBackend and marks the result with "fallback": true.
"""
from __future__ import annotations

import logging

from src.runner.orchestrator import ComputeBackend

from .credential import CredentialError as CredentialError  # noqa: F401 — public re-export
from .ibm_backend import IBMQuantumBackend
from .ionq_backend import IonQBackend

logger = logging.getLogger("scientificstate.daemon.quantum_hw")


class QuantumHWBackend(ComputeBackend):
    """Quantum hardware backend — dispatches to IBM Quantum or IonQ.

    Falls back to quantum_sim if no hardware credentials are available.
    """

    def __init__(self) -> None:
        self._ibm = IBMQuantumBackend()
        self._ionq = IonQBackend()

    def compute_class(self) -> str:
        return "quantum_hw"

    def execute(
        self,
        method_id: str,
        dataset_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        circuit_qasm = params.get("circuit_qasm", "")
        shots = params.get("shots", 1024)
        target = params.get("ionq_target", "qpu.harmony")

        # Try IBM Quantum first
        if self._ibm.is_available():
            logger.info("Dispatching to IBM Quantum hardware")
            result = self._ibm.execute(circuit_qasm, shots=shots)
            result["compute_class"] = "quantum_hw"
            return result

        # Try IonQ second
        if self._ionq.is_available():
            logger.info("Dispatching to IonQ hardware")
            result = self._ionq.execute(circuit_qasm, shots=shots, target=target)
            result["compute_class"] = "quantum_hw"
            return result

        # Graceful fallback → quantum_sim
        logger.warning(
            "No quantum hardware credentials available — "
            "falling back to quantum_sim"
        )
        from src.runner.backends.quantum_sim import QuantumSimBackend

        sim = QuantumSimBackend()
        result = sim.execute(
            method_id=method_id,
            dataset_ref=dataset_ref,
            assumptions=assumptions,
            params=params,
        )
        result["fallback"] = True
        result["fallback_reason"] = "no_hardware_credentials"
        result["compute_class"] = "quantum_hw"
        return result
