"""
Replication Engine — manages replication requests and result submission.

Main_Source §9A.5 M3-G: Quantum claims require independent institutional
replication before endorsement.

Pure logic: uses in-memory stores for M1. Production would back this with
a database, but the engine interface remains the same.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .comparison import SSVComparison


class ReplicationEngine:
    """Manages replication request lifecycle and SSV comparison."""

    def __init__(self) -> None:
        self._requests: dict[str, dict] = {}
        self._ssv_store: dict[str, dict] = {}

    def register_ssv(self, ssv_id: str, ssv: dict) -> None:
        """Register an SSV in the engine's store for lookup during comparison."""
        self._ssv_store[ssv_id] = ssv

    def create_request(
        self,
        claim_id: str,
        source_institution_id: str,
        target_institution_id: str,
        method_id: str,
        dataset_ref: str = "",
        compute_class: str = "classical",
        tolerance: dict | None = None,
        source_ssv_id: str | None = None,
    ) -> dict:
        """Create a replication request.

        Args:
            claim_id: ID of the claim to replicate.
            source_institution_id: Institution that produced the original.
            target_institution_id: Institution performing the replication.
            method_id: Method to use for replication.
            dataset_ref: Reference to the dataset.
            compute_class: Compute class for the replication run.
            tolerance: Tolerance parameters for comparison.
            source_ssv_id: SSV ID backing the original claim. Required for
                result comparison. If omitted, must be registered before
                submit_result() via register_ssv().

        Returns:
            Replication request dict with request_id and status=pending.
        """
        request_id = str(uuid.uuid4())
        request = {
            "request_id": request_id,
            "claim_id": claim_id,
            "source_ssv_id": source_ssv_id,
            "source_institution_id": source_institution_id,
            "target_institution_id": target_institution_id,
            "method_id": method_id,
            "dataset_ref": dataset_ref,
            "compute_class": compute_class,
            "tolerance": tolerance or {},
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._requests[request_id] = request
        return request

    def get_request(self, request_id: str) -> dict | None:
        """Look up a replication request by ID."""
        return self._requests.get(request_id)

    def submit_result(
        self,
        request_id: str,
        target_ssv_id: str,
        target_ssv: dict | None = None,
    ) -> dict:
        """Submit a replication result and compare against the source SSV.

        Args:
            request_id: ID of the replication request.
            target_ssv_id: SSV ID from the replication run.
            target_ssv: SSV dict from the replication run (optional if pre-registered).

        Returns:
            Replication result dict with comparison report.

        Raises:
            ValueError: If request_id is unknown or source SSV not found.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise ValueError(f"Unknown replication request: {request_id}")

        # Register target SSV if provided
        if target_ssv is not None:
            self._ssv_store[target_ssv_id] = target_ssv

        # Resolve source SSV — use explicit source_ssv_id from request
        source_ssv_id = request.get("source_ssv_id")
        if not source_ssv_id:
            raise ValueError(
                f"Replication request {request_id} missing source_ssv_id "
                f"(claim_id={request['claim_id']})"
            )
        source_ssv = self._ssv_store.get(source_ssv_id)
        if source_ssv is None:
            raise ValueError(f"Source SSV not found: {source_ssv_id}")

        target = self._ssv_store.get(target_ssv_id)
        if target is None:
            raise ValueError(f"Target SSV not found: {target_ssv_id}")

        # Compare SSVs
        comparison = SSVComparison(request.get("tolerance"))
        report = comparison.compare(source_ssv, target)

        # Update request status
        request["status"] = report["status"]

        result = {
            "request_id": request_id,
            "status": report["status"],
            "source_ssv_id": source_ssv_id,
            "target_ssv_id": target_ssv_id,
            "comparison_report": report,
            "replicated_at": datetime.now(timezone.utc).isoformat(),
        }
        return result

    def get_history(self, claim_id: str) -> list[dict]:
        """Get all replication requests for a given claim."""
        return [
            req for req in self._requests.values()
            if req["claim_id"] == claim_id
        ]
