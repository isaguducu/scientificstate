"""
result_adapter.py — Materials science domain result adapter.

Converts domain execute_method() output to the
compute-run-result.schema.json format consumed by the daemon.

Also provides to_ssv() for SSV 7-tuple conversion (lowercase fields).

Mapping:
  domain status "ok"    → run status "succeeded"
  domain status "error" → run status "failed"
"""
from __future__ import annotations

from datetime import datetime, timezone


def adapt_to_run_result(method_output: dict, run_context: dict) -> dict:
    """Convert a domain execute_method() response to compute-run-result format.

    Parameters
    ----------
    method_output : dict
        Returned by MaterialsScienceDomain.execute_method().

    run_context : dict
        Daemon-supplied run metadata (run_id, workspace_id, started_at).

    Returns
    -------
    dict
        compute-run-result.schema.json-compliant dict.
    """
    finished_at = datetime.now(tz=timezone.utc).isoformat()

    base = {
        "run_id": run_context["run_id"],
        "workspace_id": run_context["workspace_id"],
        "domain_id": method_output["domain_id"],
        "method_id": method_output["method_id"],
        "started_at": run_context["started_at"],
        "finished_at": finished_at,
    }

    if method_output.get("status") == "ok":
        return {
            **base,
            "status": "succeeded",
            "result": method_output.get("result", {}),
            "execution_witness": {
                "compute_class": "classical",
                "backend_id": method_output["domain_id"],
            },
        }

    # status == "error" → failed
    error_code = method_output.get("error_code", "EXECUTION_ERROR")
    if hasattr(error_code, "value"):
        error_code = error_code.value

    message = method_output.get("error", method_output.get("message", "Unknown error"))

    return {
        **base,
        "status": "failed",
        "error": {
            "error_code": str(error_code),
            "message": str(message),
        },
    }


def to_ssv(method_result: dict, method_id: str) -> dict:
    """Convert a method result to SSV 7-tuple format (lowercase fields).

    Args:
        method_result: The 'result' dict from execute_method() output.
        method_id: The method that produced the result.

    Returns:
        Dict with lowercase SSV fields: d, i, a, t, r, u, v, p.
    """
    return {
        "d": method_result.get("raw_data_ref"),
        "i": method_result.get("instrument_info"),
        "a": method_result.get("assumptions", []),
        "t": method_result.get("transformations", []),
        "r": method_result.get("result", method_result),
        "u": method_result.get("uncertainty"),
        "v": method_result.get("validity_domain"),
        "p": method_result.get("provenance", {}),
    }
