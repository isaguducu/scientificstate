"""
Workspace model — domain-agnostic scientific workspace container.

A Workspace groups a set of SSVs and compute runs under a named domain context.
It does NOT contain domain logic — it is a plain data container.

W2 schema: Core/contracts/jsonschema/workspace.schema.json (pending W2 freeze).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Workspace(BaseModel):
    """Scientific workspace container.

    Immutable after creation — all fields required except those with defaults.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    domain_id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {"frozen": True}
