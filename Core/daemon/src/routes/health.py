"""GET /health — daemon health endpoint.

Response shape from Execution_Plan_Phase0.md §4.1:
  {"status": "healthy", "version": "0.1.0", "uptime_seconds": ..., "active_runs": 0, "loaded_domains": [...]}
"""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])

_START_TIME = time.monotonic()


class HealthResponse(BaseModel):
    """Matches plan §4.1 /health example exactly."""
    status: Literal["healthy", "degraded", "starting"]
    version: str
    uptime_seconds: float
    active_runs: int
    loaded_domains: list[str]


@router.get("/health", response_model=HealthResponse, summary="Daemon health check")
async def health(request: Request) -> Any:
    """
    Daemon liveness — primary signal for Desktop sidecar manager.
    Shape: Execution_Plan_Phase0.md §4.1
    """
    registry = getattr(request.app.state, "domain_registry", None)
    loaded_domains: list[str] = []
    if registry is not None:
        loaded_domains = registry.list_domains()

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=round(time.monotonic() - _START_TIME, 1),
        active_runs=0,
        loaded_domains=loaded_domains,
    )
