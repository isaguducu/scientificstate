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


# ---------------------------------------------------------------------------
# Backend registry — compute-substrate-neutral dispatch (Main_Source §9A.2)
# ---------------------------------------------------------------------------

_BACKENDS: dict[str, ComputeBackend] = {}


def register_backend(backend: ComputeBackend) -> None:
    """Register a compute backend by its compute_class."""
    _BACKENDS[backend.compute_class()] = backend


def get_backend(compute_class: str) -> ComputeBackend | None:
    """Look up a registered backend by compute_class."""
    return _BACKENDS.get(compute_class)


def list_backends() -> list[str]:
    """Return the list of registered compute_class identifiers."""
    return list(_BACKENDS.keys())


# ---------------------------------------------------------------------------
# Auto-register quantum_sim backend (M2 — additive)
# ---------------------------------------------------------------------------

def _register_quantum_sim_backend() -> None:
    try:
        from src.runner.backends.quantum_sim import QuantumSimBackend

        if "quantum_sim" not in _BACKENDS:
            _BACKENDS["quantum_sim"] = QuantumSimBackend()
    except ImportError:
        pass


_register_quantum_sim_backend()
