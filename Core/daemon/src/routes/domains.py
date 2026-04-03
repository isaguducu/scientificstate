"""GET /domains — list discovered scientific domains.

Response shape from Execution_Plan_Phase0.md §4.1:
  [{"domain_id": ..., "domain_name": ..., "supported_data_types": [...], "method_count": N}]

Uses DomainModule.describe() from Core/framework (authoritative source).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["domains"])


@router.get("/domains", summary="List registered domains")
async def list_domains(request: Request) -> Any:
    """
    Returns the list of domains loaded via framework DomainRegistry.

    Each entry matches plan §4.1:
      domain_id, domain_name, supported_data_types, method_count

    Shape is a plain list (not wrapped) per plan example.
    """
    registry = getattr(request.app.state, "domain_registry", None)
    result: list[dict[str, Any]] = []

    if registry is not None:
        for domain_id in registry.list_domains():
            domain = registry.get(domain_id)
            if domain is not None:
                result.append(domain.describe())

    return result
