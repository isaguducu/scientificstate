"""Export endpoints — standards-compliant scientific data export.

GET /export/rocrate/{run_id}      → RO-Crate v2 metadata JSON
GET /export/prov/{run_id}         → W3C PROV-JSON
GET /export/openlineage/{run_id}  → OpenLineage RunEvent
GET /export/cwl/{run_id}          → CWL Workflow YAML
GET /export/parquet/{run_id}      → Parquet file download
GET /export/zarr/{run_id}         → Zarr archive download

All endpoints read from the immutable ssvs / runs tables.
No mutation — export is read-only.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from src.storage.schema import get_db_path

logger = logging.getLogger("scientificstate.daemon.export")

router = APIRouter(prefix="/export", tags=["export"])

# W3 framework imports
_FRAMEWORK_PATH = str(Path(__file__).parents[4] / "Core" / "framework")
if _FRAMEWORK_PATH not in sys.path:
    sys.path.insert(0, _FRAMEWORK_PATH)

try:
    from scientificstate.standards.rocrate import ssv_to_rocrate
    from scientificstate.standards.prov import ssv_to_prov_json
    from scientificstate.standards.openlineage import run_to_openlineage
    from scientificstate.standards.cwl import pipeline_to_cwl_yaml
    from scientificstate.standards.output_formats import result_to_parquet, result_to_zarr

    _STANDARDS_AVAILABLE = True
except ImportError:
    _STANDARDS_AVAILABLE = False
    logger.warning("Standards module not available — export endpoints disabled")


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------


async def _load_run_and_ssv(run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load run + ssv for a given run_id.

    Returns:
        (run_dict, ssv_dict) — both as plain dicts.

    Raises:
        HTTPException 404 if run or SSV not found.
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        )
        run_row = await cur.fetchone()
        if run_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )
        run_dict = dict(run_row)

        ssv_id = run_dict.get("ssv_id")
        if not ssv_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No SSV found for run: {run_id}",
            )

        cur = await db.execute(
            "SELECT ssv_json FROM ssvs WHERE ssv_id = ?", (ssv_id,)
        )
        ssv_row = await cur.fetchone()
        if ssv_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SSV record not found: {ssv_id}",
            )

        ssv = json.loads(ssv_row["ssv_json"])
        return run_dict, ssv


def _check_standards() -> None:
    if not _STANDARDS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Standards module not available",
        )


# ---------------------------------------------------------------------------
# GET /export/rocrate/{run_id}
# ---------------------------------------------------------------------------


@router.get("/rocrate/{run_id}")
async def export_rocrate(run_id: str) -> Any:
    """Export RO-Crate v2 metadata JSON for a completed run."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)
    return ssv_to_rocrate(ssv, run=run_dict)


# ---------------------------------------------------------------------------
# GET /export/prov/{run_id}
# ---------------------------------------------------------------------------


@router.get("/prov/{run_id}")
async def export_prov(run_id: str) -> Any:
    """Export W3C PROV-JSON for a completed run."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)
    return ssv_to_prov_json(ssv, run=run_dict)


# ---------------------------------------------------------------------------
# GET /export/openlineage/{run_id}
# ---------------------------------------------------------------------------


@router.get("/openlineage/{run_id}")
async def export_openlineage(run_id: str) -> Any:
    """Export OpenLineage RunEvent for a completed run."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)
    return run_to_openlineage(run_dict, ssv=ssv)


# ---------------------------------------------------------------------------
# GET /export/cwl/{run_id}
# ---------------------------------------------------------------------------


@router.get("/cwl/{run_id}")
async def export_cwl(run_id: str) -> Response:
    """Export CWL Workflow YAML for a completed run."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)

    yaml_str = pipeline_to_cwl_yaml(
        domain_id=run_dict.get("domain_id", "unknown"),
        method_id=run_dict.get("method_id", "unknown"),
        ssv=ssv,
    )
    return Response(content=yaml_str, media_type="application/x-yaml")


# ---------------------------------------------------------------------------
# GET /export/parquet/{run_id}
# ---------------------------------------------------------------------------


@router.get("/parquet/{run_id}")
async def export_parquet(run_id: str) -> FileResponse:
    """Export Parquet file for a completed run's result data."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)

    result = ssv.get("r", {}).get("quantities", {})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result data to export",
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="ss_export_"))
    parquet_path = tmp_dir / f"run_{run_id}.parquet"

    try:
        result_to_parquet(result, parquet_path)
    except ImportError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="pyarrow not installed — Parquet export unavailable",
        )

    return FileResponse(
        path=str(parquet_path),
        media_type="application/octet-stream",
        filename=f"run_{run_id}.parquet",
    )


# ---------------------------------------------------------------------------
# GET /export/zarr/{run_id}
# ---------------------------------------------------------------------------


@router.get("/zarr/{run_id}")
async def export_zarr(run_id: str) -> FileResponse:
    """Export Zarr archive for a completed run's result data."""
    _check_standards()
    run_dict, ssv = await _load_run_and_ssv(run_id)

    result = ssv.get("r", {}).get("quantities", {})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result data to export",
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="ss_export_"))
    zarr_path = tmp_dir / f"run_{run_id}.zarr"

    try:
        result_to_zarr(result, zarr_path)
    except ImportError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="zarr not installed — Zarr export unavailable",
        )

    # Zarr is a directory — zip it for download
    zip_path = tmp_dir / f"run_{run_id}_zarr"
    shutil.make_archive(str(zip_path), "zip", str(zarr_path))

    return FileResponse(
        path=f"{zip_path}.zip",
        media_type="application/zip",
        filename=f"run_{run_id}.zarr.zip",
    )


# ---------------------------------------------------------------------------
# POST /export/air-gapped
# ---------------------------------------------------------------------------

_EXPORT_SCRIPT = Path(__file__).parents[4] / "scripts" / "air-gapped-export.sh"


class AirGappedExportRequest(BaseModel):
    output_dir: str


@router.post("/air-gapped")
async def export_air_gapped(body: AirGappedExportRequest) -> Any:
    """Trigger air-gapped export via the shell script.

    Runs scripts/air-gapped-export.sh as a subprocess and returns
    the result. The script copies registry data, TUF metadata,
    trust chain, and packages to the output directory.
    """
    import asyncio

    if not _EXPORT_SCRIPT.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="air-gapped-export.sh not found",
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", str(_EXPORT_SCRIPT), body.output_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(
                "Air-gapped export failed (rc=%d): %s",
                proc.returncode,
                stderr.decode("utf-8", errors="replace"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export script failed: {stderr.decode('utf-8', errors='replace')[:500]}",
            )

        return {
            "status": "completed",
            "output_dir": body.output_dir,
            "message": stdout.decode("utf-8", errors="replace").strip().split("\n")[-1],
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="bash not available on this system",
        )
