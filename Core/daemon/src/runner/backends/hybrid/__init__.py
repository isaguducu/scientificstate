"""
HybridBackend — classical + quantum parallel execution.

Main_Source §9A.3: Any run containing a quantum branch is automatically
exploratory. Classical baseline results are captured separately for
downstream comparison (M3 requirement: classical baseline ref).

Graceful degradation: uses quantum_sim if no hardware credentials.
"""
from __future__ import annotations

import logging

from src.runner.orchestrator import ComputeBackend

logger = logging.getLogger("scientificstate.daemon.hybrid")


class HybridBackend(ComputeBackend):
    """Hybrid backend — runs classical and quantum branches in parallel."""

    def __init__(self, domain_registry: object | None = None) -> None:
        self._domain_registry = domain_registry

    def compute_class(self) -> str:
        return "hybrid"

    def execute(
        self,
        method_id: str,
        dataset_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        from src.runner.backends.classical import ClassicalBackend
        from src.runner.backends.quantum_hw import QuantumHWBackend
        from .orchestrator import execute_hybrid

        if self._domain_registry is None:
            logger.warning(
                "HybridBackend created without domain_registry — "
                "classical branch will fail if it needs domain lookup"
            )

        classical_backend = ClassicalBackend(domain_registry=self._domain_registry)
        quantum_backend = QuantumHWBackend()

        def classical_fn(m_id: str, d_ref: str, assumptions: list, p: dict) -> dict:
            return classical_backend.execute(m_id, d_ref, assumptions, p)

        def quantum_fn(m_id: str, d_ref: str, assumptions: list, p: dict) -> dict:
            return quantum_backend.execute(m_id, d_ref, assumptions, p)

        result = execute_hybrid(
            classical_fn=classical_fn,
            quantum_fn=quantum_fn,
            method_id=method_id,
            dataset_ref=dataset_ref,
            assumptions=assumptions,
            params=params,
        )

        return result
