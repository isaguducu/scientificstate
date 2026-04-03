"""
ComputeBackend ABC — compute-substrate-neutral abstraction.

Main_Source §9A.2: The daemon dispatches scientific computation jobs through
a registered backend without coupling to any specific substrate.

Phase 0 scope (classical only). M2+ adds quantum backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ComputeBackend(ABC):
    """Compute-substrate-neutral backend interface — Main_Source §9A.2."""

    @abstractmethod
    def compute_class(self) -> str:
        """Return the compute substrate class: 'classical' | 'quantum_sim' | 'quantum_hw' | 'hybrid'."""

    @abstractmethod
    def execute(
        self,
        method_id: str,
        dataset_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        """
        Execute a domain method and return a result dict.

        Constitutional constraint (P7 — non-delegation of scientific authority):
        This method performs computation only. It must not assert scientific
        claims or validity — those belong to the gate layer and the researcher.
        """
