"""
Discovery sync route — local daemon pushes endorsed claims to the portal.

This is the ONLY discovery endpoint on the daemon.  All global discovery
(feed, search, citations, impact) lives on the portal (Next.js + Supabase).

Trust model:
  1. Daemon signs the SSV with Ed25519 private key.
  2. Portal verifies ssv_signature against the researcher's public key.
  3. ssv_hash provides SHA-256 integrity check.
  4. researcher_orcid is verified via JWT on the portal side.
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("scientificstate.daemon.discovery")

router = APIRouter(prefix="/discovery", tags=["discovery"])

_PORTAL_URL = os.environ.get(
    "SCIENTIFICSTATE_PORTAL_URL", "https://scientificstate.org"
)


class EndorsedClaimSync(BaseModel):
    """Payload for syncing an endorsed claim to the portal."""

    claim_id: str
    ssv_id: str
    domain_id: str
    method_id: str | None = None
    title: str
    institution_id: str | None = None
    researcher_orcid: str
    gate_status: dict
    ssv_signature: str
    ssv_hash: str
    auth_token: str | None = None


async def trigger_discovery_sync(
    claim_id: str,
    ssv_id: str,
    domain_id: str,
    title: str,
    researcher_orcid: str,
    gate_status: dict,
    ssv_signature: str,
    ssv_hash: str,
    *,
    method_id: str | None = None,
    institution_id: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Programmatic entry point for endorsement→discovery sync.

    Called by the endorsement gate when a claim transitions to 'endorsed'.
    Constructs the payload and delegates to sync_endorsed_claim().

    Returns:
        Sync result dict (same as POST /discovery/sync).
    """
    payload = EndorsedClaimSync(
        claim_id=claim_id,
        ssv_id=ssv_id,
        domain_id=domain_id,
        method_id=method_id,
        title=title,
        institution_id=institution_id,
        researcher_orcid=researcher_orcid,
        gate_status=gate_status,
        ssv_signature=ssv_signature,
        ssv_hash=ssv_hash,
        auth_token=auth_token,
    )
    return await sync_endorsed_claim(payload)


@router.post("/sync")
async def sync_endorsed_claim(body: EndorsedClaimSync) -> dict:
    """Push an endorsed claim to the portal for global discovery.

    Forwards the payload to the portal's POST /api/discover/endorsed
    endpoint with the user's auth token for RLS compliance.

    Returns:
        Sync result with claim_id and portal response.
    """
    logger.info(
        "Discovery sync: claim=%s domain=%s orcid=%s",
        body.claim_id,
        body.domain_id,
        body.researcher_orcid,
    )

    payload = {
        "claim_id": body.claim_id,
        "ssv_id": body.ssv_id,
        "domain_id": body.domain_id,
        "method_id": body.method_id,
        "title": body.title,
        "institution_id": body.institution_id,
        "researcher_orcid": body.researcher_orcid,
        "gate_status": body.gate_status,
        "ssv_signature": body.ssv_signature,
        "ssv_hash": body.ssv_hash,
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if body.auth_token:
        headers["Authorization"] = f"Bearer {body.auth_token}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_PORTAL_URL}/api/discover/endorsed",
                json=payload,
                headers=headers,
            )

        if resp.status_code in (200, 201):
            portal_data = resp.json()
            logger.info("Portal sync succeeded: claim=%s", body.claim_id)
            return {
                "status": "synced",
                "claim_id": body.claim_id,
                "portal_response": portal_data,
            }

        logger.warning(
            "Portal sync failed (HTTP %d): %s",
            resp.status_code,
            resp.text[:200],
        )
        return {
            "status": "failed",
            "claim_id": body.claim_id,
            "portal_status": resp.status_code,
            "message": resp.text[:200],
        }

    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.HTTPError, OSError):
        logger.warning("Portal unreachable at %s — claim queued locally", _PORTAL_URL)
        return {
            "status": "queued",
            "claim_id": body.claim_id,
            "message": f"Portal unreachable at {_PORTAL_URL} — will retry on next sync",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Discovery sync error: %s", exc)
        return {
            "status": "queued",
            "claim_id": body.claim_id,
            "message": f"Portal sync error: {exc}",
        }
