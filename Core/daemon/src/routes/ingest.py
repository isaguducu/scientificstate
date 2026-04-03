"""POST /datasets/ingest — immutable raw data ingest stub.

Request/response shape matches daemon-api.yaml IngestRequest / IngestResponse.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.storage.schema import record_ingest_event

logger = logging.getLogger("scientificstate.daemon.ingest")

router = APIRouter(prefix="/datasets", tags=["datasets"])


class IngestRequest(BaseModel):
    """Matches IngestRequest in daemon-api.yaml."""
    data_path: str = Field(..., description="Absolute local file path to raw data")
    acquisition_timestamp: str = Field(..., description="ISO-8601 datetime")
    instrument_id: str = Field(..., description="Instrument identifier")
    domain_id: str = Field(..., description="Which domain this data belongs to")
    sample_id: str = Field(..., description="Sample identifier")
    signal_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Units, dynamic range, additional annotations",
    )


class IngestResponse(BaseModel):
    """Matches IngestResponse in daemon-api.yaml."""
    raw_data_id: str = Field(..., description="Permanent identifier — never reused, never deleted")
    content_hash: str = Field(..., description="SHA-256 content hash for integrity verification")
    stored_at: str = Field(..., description="ISO-8601 datetime when stored")


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a dataset (immutable, append-only)",
)
async def ingest_dataset(body: IngestRequest) -> Any:
    """
    Accepts a dataset ingest request and records it immutably in the local
    SQLite store.

    Constitutional constraint (P1 — immutability):
    - Raw data is NEVER mutated once ingested.
    - Each call produces a new immutable record.
    - Source file on disk is not moved or modified by the daemon.

    Phase 0 stub: records the event, returns raw_data_id + content_hash.
    Actual domain-specific parsing is wired in subsequent phases.
    """
    raw_data_id = str(uuid.uuid4())
    stored_at = datetime.now(tz=timezone.utc).isoformat()

    # Content hash: file MUST be locally accessible (immutability requires real content hash)
    data_path = Path(body.data_path)
    if not data_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"data_path not found on daemon host: {body.data_path}",
        )
    h = hashlib.sha256()
    with data_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    content_hash = h.hexdigest()

    try:
        await record_ingest_event(
            ingest_id=raw_data_id,
            domain=body.domain_id,
            dataset_name=body.sample_id,
            format="raw",
            source_path=body.data_path,
            metadata={
                "instrument_id": body.instrument_id,
                "acquisition_timestamp": body.acquisition_timestamp,
                "signal_metadata": body.signal_metadata,
                "content_hash": content_hash,
            },
            timestamp=stored_at,
        )
        logger.info(
            "Ingest recorded: domain=%s sample=%s raw_data_id=%s",
            body.domain_id, body.sample_id, raw_data_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to record ingest event: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record ingest event.",
        ) from exc

    return IngestResponse(
        raw_data_id=raw_data_id,
        content_hash=content_hash,
        stored_at=stored_at,
    )
