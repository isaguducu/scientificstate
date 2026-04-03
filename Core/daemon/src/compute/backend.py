"""
ComputeBackend — Abstract Base Class.

All compute backends (classical, quantum sim, quantum hw, hybrid) implement
this interface. The daemon dispatches scientific computation jobs through
the registered backend without caring which substrate executes them.

This is the compute-substrate-neutral abstraction described in Main_Source §9A.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BackendKind(str, Enum):
    CLASSICAL = "classical"
    QUANTUM_SIM = "quantum_sim"
    QUANTUM_HW = "quantum_hw"
    HYBRID = "hybrid"


@dataclass
class ComputeJob:
    """Represents a single unit of work submitted to a backend."""

    job_id: str
    domain: str
    method: str
    parameters: dict[str, Any] = field(default_factory=dict)
    input_refs: list[str] = field(default_factory=list)  # ingest_ids
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeResult:
    """Result returned from a backend after executing a job."""

    job_id: str
    backend_kind: BackendKind
    status: str  # "success" | "failed" | "partial"
    outputs: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ComputeBackend(ABC):
    """
    Abstract compute backend.

    Implementations:
    - ClassicalBackend  (M1 — CPU/GPU, numpy/scipy)
    - QuantumSimBackend (M2 — Qiskit/Cirq simulator)
    - QuantumHWBackend  (M3 — real QPU via cloud provider API)
    - HybridBackend     (M3+ — quantum+classical orchestrator)
    """

    @property
    @abstractmethod
    def kind(self) -> BackendKind:
        """Identity of this backend substrate."""

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check whether this backend is currently usable.

        ClassicalBackend always returns True.
        QuantumHWBackend may return False if QPU is offline.
        """

    @abstractmethod
    async def execute(self, job: ComputeJob) -> ComputeResult:
        """
        Execute a compute job and return the result.

        MUST be idempotent with respect to the job_id — re-submitting the
        same job_id should either return the cached result or be a no-op.
        """

    @abstractmethod
    async def capabilities(self) -> dict[str, Any]:
        """
        Return a dict describing what this backend can do.

        Example keys: max_qubits, supported_methods, hardware_id, etc.
        """
