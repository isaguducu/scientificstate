"""
Compute run model — domain-agnostic execution record.

A ComputeRun records a single invocation of a domain method against a workspace.
Status transitions: pending → running → succeeded | failed.

Constitutional rule: run records are evidence — not claims, not verdicts.
W2 schema: Core/contracts/jsonschema/compute-run-request.schema.json
           Core/contracts/jsonschema/compute-run-result.schema.json (pending W2 freeze).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ComputeRun(BaseModel):
    """Record of a single domain method execution.

    run_id: globally unique execution identifier
    workspace_id: owning workspace
    domain_id: which domain module was invoked
    method_id: which method within the domain
    status: current execution state
    started_at: wall-clock start time (set when status → running)
    finished_at: wall-clock finish time (set when status → succeeded | failed)
    execution_witness: compute provenance (backend, class, fidelity metadata)
    result_ref: reference to output artifact or SSV id (None while pending/running)
    """

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str
    domain_id: str
    method_id: str
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    execution_witness: dict[str, Any] = Field(default_factory=dict)
    result_ref: str | None = None

    model_config = {"frozen": True}

    def mark_running(self) -> "ComputeRun":
        """Return a new run with status=RUNNING and started_at set."""
        return self.model_copy(
            update={"status": RunStatus.RUNNING, "started_at": datetime.now(timezone.utc)}
        )

    def mark_succeeded(self, result_ref: str, witness: dict[str, Any] | None = None) -> "ComputeRun":
        """Return a new run with status=SUCCEEDED."""
        return self.model_copy(
            update={
                "status": RunStatus.SUCCEEDED,
                "finished_at": datetime.now(timezone.utc),
                "result_ref": result_ref,
                "execution_witness": witness or self.execution_witness,
            }
        )

    def mark_failed(self, witness: dict[str, Any] | None = None) -> "ComputeRun":
        """Return a new run with status=FAILED."""
        return self.model_copy(
            update={
                "status": RunStatus.FAILED,
                "finished_at": datetime.now(timezone.utc),
                "execution_witness": witness or self.execution_witness,
            }
        )
