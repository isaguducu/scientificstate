"""Scientific question endpoints.

POST /workspaces/{workspace_id}/questions  — create a new question
GET  /workspaces/{workspace_id}/questions  — list questions in workspace
GET  /questions/{question_id}              — question detail + linked runs
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

router = APIRouter(tags=["questions"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateQuestionRequest(BaseModel):
    text: str = Field(..., min_length=5)
    domain_id: str | None = None
    assumptions: list[dict[str, Any]] = Field(default_factory=list)


class QuestionSummary(BaseModel):
    question_id: str
    workspace_id: str
    text: str
    domain_id: str | None
    status: str
    created_at: str
    run_count: int = 0


class QuestionDetail(QuestionSummary):
    assumptions: list[dict[str, Any]]
    runs: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/questions",
    response_model=QuestionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(workspace_id: str, body: CreateQuestionRequest) -> Any:
    """Create a new scientific question inside a workspace."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (workspace_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace not found: {workspace_id}",
            )

        question_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        assumptions_json = json.dumps(body.assumptions)

        await db.execute(
            """
            INSERT INTO questions
                (question_id, workspace_id, text, domain_id, assumptions,
                 status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                question_id,
                workspace_id,
                body.text,
                body.domain_id,
                assumptions_json,
                now,
                now,
            ),
        )
        await db.commit()

    return {
        "question_id": question_id,
        "workspace_id": workspace_id,
        "text": body.text,
        "domain_id": body.domain_id,
        "status": "open",
        "created_at": now,
        "run_count": 0,
        "assumptions": body.assumptions,
        "runs": [],
    }


@router.get(
    "/workspaces/{workspace_id}/questions",
    response_model=list[QuestionSummary],
)
async def list_questions(workspace_id: str) -> Any:
    """List all questions for a workspace, most recent first."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (workspace_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace not found: {workspace_id}",
            )

        cur = await db.execute(
            """
            SELECT question_id, workspace_id, text, domain_id, status, created_at
            FROM questions
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            """,
            (workspace_id,),
        )
        rows = await cur.fetchall()

    return [
        {
            "question_id": r["question_id"],
            "workspace_id": r["workspace_id"],
            "text": r["text"],
            "domain_id": r["domain_id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "run_count": 0,
        }
        for r in rows
    ]


@router.get("/questions/{question_id}", response_model=QuestionDetail)
async def get_question(question_id: str) -> Any:
    """Return question detail. Linked runs are not yet joinable (no FK in runs table)."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM questions WHERE question_id = ?", (question_id,)
        )
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {question_id}",
        )

    assumptions = json.loads(row["assumptions"] or "[]")
    return {
        "question_id": row["question_id"],
        "workspace_id": row["workspace_id"],
        "text": row["text"],
        "domain_id": row["domain_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "run_count": 0,
        "assumptions": assumptions,
        "runs": [],
    }
