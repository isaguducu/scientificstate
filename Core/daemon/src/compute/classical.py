"""
ClassicalBackend — CPU-based scientific computation.

Phase 0 placeholder implementation. All method dispatch returns a stub result.
Real domain methods (KMD analysis, PCA, HCA, etc.) are wired in subsequent
phases via the domain plugin system.

This class satisfies the ComputeBackend ABC contract so the daemon can start
and report a working backend even before domain methods are implemented.
"""

from __future__ import annotations

import logging
from typing import Any

from src.compute.backend import BackendKind, ComputeBackend, ComputeJob, ComputeResult

logger = logging.getLogger("scientificstate.daemon.compute.classical")


class ClassicalBackend(ComputeBackend):
    """
    CPU/GPU classical compute backend.

    Phase 0: method stubs — returns placeholder results.
    Phase 1+: domain plugins register their methods here.
    """

    def __init__(self) -> None:
        self._registered_methods: dict[str, Any] = {}
        logger.info("ClassicalBackend initialised (Phase 0 stub mode).")

    @property
    def kind(self) -> BackendKind:
        return BackendKind.CLASSICAL

    async def is_available(self) -> bool:
        return True  # Classical compute is always available

    async def execute(self, job: ComputeJob) -> ComputeResult:
        """
        Dispatch a compute job.

        Phase 0: Returns a stub result for any method.
        Phase 1+: Checks _registered_methods and delegates to domain plugin.
        """
        logger.info(
            "ClassicalBackend.execute: domain=%s method=%s job_id=%s",
            job.domain,
            job.method,
            job.job_id,
        )

        # Check if a real method implementation is registered
        method_key = f"{job.domain}.{job.method}"
        if method_key in self._registered_methods:
            handler = self._registered_methods[method_key]
            try:
                outputs = await handler(job.parameters, job.input_refs)
                return ComputeResult(
                    job_id=job.job_id,
                    backend_kind=self.kind,
                    status="success",
                    outputs=outputs,
                    provenance={
                        "backend": "classical",
                        "method_key": method_key,
                        "phase": "production",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Method %s raised: %s", method_key, exc)
                return ComputeResult(
                    job_id=job.job_id,
                    backend_kind=self.kind,
                    status="failed",
                    error=str(exc),
                )

        # Phase 0 stub — method not yet implemented
        logger.warning(
            "No handler registered for %s — returning stub result.", method_key
        )
        return ComputeResult(
            job_id=job.job_id,
            backend_kind=self.kind,
            status="success",
            outputs={
                "stub": True,
                "method": job.method,
                "domain": job.domain,
                "note": "Phase 0 placeholder — real implementation pending.",
            },
            provenance={
                "backend": "classical",
                "method_key": method_key,
                "phase": "stub",
            },
        )

    async def capabilities(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "phase": "0-stub",
            "registered_methods": list(self._registered_methods.keys()),
            "supported_domains": list(
                {k.split(".")[0] for k in self._registered_methods}
            ),
        }

    def register_method(self, domain: str, method: str, handler: Any) -> None:
        """
        Register a domain method handler.

        Called by domain plugins during DomainRegistry.discover_and_register().
        handler must be an async callable: async (params, input_refs) -> dict
        """
        key = f"{domain}.{method}"
        self._registered_methods[key] = handler
        logger.info("Registered method: %s", key)
