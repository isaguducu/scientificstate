"""
OpenLineage export — run events → OpenLineage format.

Generates OpenLineage-compatible RunEvent, DatasetEvent, JobEvent JSON documents
from ScientificState runs and SSVs.

Schema: https://openlineage.io/spec/2-0-2/OpenLineage.json

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations

from datetime import datetime, timezone

_OPENLINEAGE_PRODUCER = "https://scientificstate.org"
_OPENLINEAGE_SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"


def run_to_openlineage(
    run: dict,
    ssv: dict | None = None,
    event_type: str = "COMPLETE",
) -> dict:
    """Convert a ComputeRun dict to an OpenLineage RunEvent.

    Args:
        run: ComputeRun dict (run_id, workspace_id, domain_id, method_id, status, etc.)
        ssv: optional SSV dict (enriches inputs/outputs)
        event_type: one of START, RUNNING, COMPLETE, FAIL, ABORT

    Returns:
        OpenLineage RunEvent dict.
    """
    run_id = run.get("run_id", "unknown")
    domain_id = run.get("domain_id", "unknown")
    method_id = run.get("method_id", "unknown")

    event_time = _resolve_event_time(run, event_type)

    # Build job facets
    job_facets: dict = {}
    if ssv:
        p = ssv.get("p", {})
        ew = p.get("execution_witness", {})
        if ew:
            job_facets["computeClass"] = {
                "_producer": _OPENLINEAGE_PRODUCER,
                "_schemaURL": _OPENLINEAGE_SCHEMA,
                "compute_class": ew.get("compute_class", "classical"),
                "backend_id": ew.get("backend_id", "unknown"),
            }

    # Build run facets
    run_facets: dict = {}
    if run.get("execution_witness"):
        run_facets["executionWitness"] = {
            "_producer": _OPENLINEAGE_PRODUCER,
            "_schemaURL": _OPENLINEAGE_SCHEMA,
            **run["execution_witness"],
        }

    # Build inputs
    inputs: list[dict] = []
    if ssv:
        d = ssv.get("d", {})
        inputs.append({
            "namespace": domain_id,
            "name": d.get("ref", "raw-data"),
            "facets": {},
        })

    # Build outputs
    outputs: list[dict] = []
    if ssv:
        outputs.append({
            "namespace": domain_id,
            "name": f"ssv-{ssv.get('id', 'unknown')}",
            "facets": {},
        })

    return {
        "eventType": event_type,
        "eventTime": event_time,
        "producer": _OPENLINEAGE_PRODUCER,
        "schemaURL": _OPENLINEAGE_SCHEMA,
        "run": {
            "runId": run_id,
            "facets": run_facets,
        },
        "job": {
            "namespace": domain_id,
            "name": method_id,
            "facets": job_facets,
        },
        "inputs": inputs,
        "outputs": outputs,
    }


def run_to_dataset_event(run: dict, ssv: dict) -> dict:
    """Create an OpenLineage DatasetEvent from run + SSV.

    Args:
        run: ComputeRun dict
        ssv: SSV dict

    Returns:
        OpenLineage DatasetEvent dict.
    """
    d = ssv.get("d", {})
    domain_id = run.get("domain_id", d.get("domain", "unknown"))

    return {
        "eventTime": _resolve_event_time(run, "COMPLETE"),
        "producer": _OPENLINEAGE_PRODUCER,
        "schemaURL": _OPENLINEAGE_SCHEMA,
        "dataset": {
            "namespace": domain_id,
            "name": d.get("ref", "raw-data"),
            "facets": {
                "schema": {
                    "_producer": _OPENLINEAGE_PRODUCER,
                    "_schemaURL": _OPENLINEAGE_SCHEMA,
                    "fields": [],
                },
            },
        },
    }


def run_to_job_event(run: dict) -> dict:
    """Create an OpenLineage JobEvent from run.

    Args:
        run: ComputeRun dict

    Returns:
        OpenLineage JobEvent dict.
    """
    domain_id = run.get("domain_id", "unknown")
    method_id = run.get("method_id", "unknown")

    return {
        "eventTime": _resolve_event_time(run, "COMPLETE"),
        "producer": _OPENLINEAGE_PRODUCER,
        "schemaURL": _OPENLINEAGE_SCHEMA,
        "job": {
            "namespace": domain_id,
            "name": method_id,
            "facets": {},
        },
        "inputs": [],
        "outputs": [],
    }


def _resolve_event_time(run: dict, event_type: str) -> str:
    """Determine the event timestamp based on event type and run state."""
    if event_type == "START":
        ts = run.get("started_at")
    elif event_type in ("COMPLETE", "FAIL", "ABORT"):
        ts = run.get("finished_at")
    else:
        ts = None

    if ts:
        return str(ts)
    return datetime.now(timezone.utc).isoformat()
