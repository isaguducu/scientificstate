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
            SELECT q.question_id, q.workspace_id, q.text, q.domain_id,
                   q.status, q.created_at,
                   COUNT(r.run_id) AS run_count
            FROM questions q
            LEFT JOIN runs r ON r.question_id = q.question_id
            WHERE q.workspace_id = ?
            GROUP BY q.question_id
            ORDER BY q.created_at DESC
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
            "run_count": r["run_count"],
        }
        for r in rows
    ]


@router.get("/questions/{question_id}", response_model=QuestionDetail)
async def get_question(question_id: str) -> Any:
    """Return question detail with linked runs."""
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

        # Fetch linked runs (question_id FK added Phase 9)
        cur = await db.execute(
            """
            SELECT run_id, domain_id, method_id, status, started_at, finished_at
            FROM runs
            WHERE question_id = ?
            ORDER BY started_at DESC
            """,
            (question_id,),
        )
        run_rows = await cur.fetchall()

    assumptions = json.loads(row["assumptions"] or "[]")
    runs = [
        {
            "run_id": r["run_id"],
            "domain_id": r["domain_id"],
            "method_id": r["method_id"],
            "status": r["status"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
        }
        for r in run_rows
    ]
    return {
        "question_id": row["question_id"],
        "workspace_id": row["workspace_id"],
        "text": row["text"],
        "domain_id": row["domain_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "run_count": len(runs),
        "assumptions": assumptions,
        "runs": runs,
    }
