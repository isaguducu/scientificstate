"""Domain discovery endpoints.

GET /domains              — list all registered domains (DomainSummary[])
GET /domains/{domain_id}  — detail for one domain including methods (DomainDetail)

Response shapes match daemon-api.yaml DomainSummary / DomainDetail.
Uses DomainModule.describe() + list_methods() from Core/framework.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(tags=["domains"])


@router.get("/domains", summary="List registered domains")
async def list_domains(request: Request) -> Any:
    """
    Returns the list of domains loaded via framework DomainRegistry.

    Shape is a plain list (not wrapped) — matches daemon-api.yaml DomainSummary[].
    """
    registry = getattr(request.app.state, "domain_registry", None)
    result: list[dict[str, Any]] = []

    if registry is not None:
        for domain_id in registry.list_domains():
            domain = registry.get(domain_id)
            if domain is not None:
                result.append(domain.describe())

    return result


@router.get("/domains/{domain_id}", summary="Get domain module detail")
async def get_domain(domain_id: str, request: Request) -> Any:
    """
    Returns DomainDetail for a single domain including its method manifests.

    Response matches daemon-api.yaml DomainDetail:
      domain_id, domain_name, version, supported_data_types, methods[]
    404 if domain not registered.
    """
    registry = getattr(request.app.state, "domain_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Domain registry not available",
        )

    domain = registry.get(domain_id)
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain not found: {domain_id}",
        )

    return {
        "domain_id": domain.domain_id,
        "domain_name": domain.domain_name,
        "version": domain.version,
        "supported_data_types": domain.supported_data_types,
        "methods": domain.list_methods(),
    }
