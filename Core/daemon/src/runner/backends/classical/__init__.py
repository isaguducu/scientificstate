"""
ClassicalBackend — CPU/GPU classical compute substrate.

Phase 0 / M1 implementation. Routes execution through the DomainRegistry
without any domain-specific coupling here.
"""

from __future__ import annotations

from src.runner.orchestrator import ComputeBackend


class ClassicalBackend(ComputeBackend):
    """
    Classical compute backend.

    Delegates execution to the registered domain module via DomainRegistry.
    No direct dependency on any domain — registry is the only coupling.
    """

    def __init__(self, domain_registry: object) -> None:
        self._registry = domain_registry

    def compute_class(self) -> str:
        return "classical"

    def execute(
        self,
        method_id: str,
        dataset_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        """Find the domain in the registry and call execute_method()."""
        if self._registry is None:
            raise ValueError(
                "ClassicalBackend requires a domain_registry — "
                "pass it via constructor"
            )

        domain_id = params.get("domain_id")
        if not domain_id:
            raise ValueError("params must include 'domain_id'")

        domain = self._registry.get(domain_id)
        if domain is None:
            raise ValueError(f"Unknown domain: {domain_id!r}")

        return domain.execute_method(method_id, dataset_ref, assumptions, params)
