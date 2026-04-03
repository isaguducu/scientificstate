"""
result_adapter.py — Polymer domain result adapter.

Converts domain execute_method() output to the
compute-run-result.schema.json format consumed by the daemon.

Mapping:
  domain status "ok"    → run status "succeeded"
  domain status "error" → run status "failed"

The daemon is responsible for:
  - setting started_at before execution
  - filling ssv_ref once an SSV is committed

This adapter is computation-only — it must not assert scientific claims
or add validity judgements. It only translates dict shapes.
"""
from __future__ import annotations

from datetime import datetime, timezone


def adapt_to_run_result(method_output: dict, run_context: dict) -> dict:
    """
    Convert a domain execute_method() response to compute-run-result format.

    Parameters
    ----------
    method_output : dict
        Returned by ``PolymerScienceDomain.execute_method()``. Shape::

            {
                "method_id":  str,
                "domain_id":  str,
                "status":     "ok" | "error",
                "result":     dict,           # present when status="ok"
                "diagnostics": dict,          # always present
                "error_code": str,            # present when status="error"
                "error":      str,            # present when status="error" (backward-compat)
            }

    run_context : dict
        Daemon-supplied run metadata::

            {
                "run_id":       str,
                "workspace_id": str,
                "started_at":   str,   # ISO 8601 date-time
            }

    Returns
    -------
    dict
        ``compute-run-result.schema.json``-compliant dict.  Shape for success::

            {
                "run_id":            str,
                "workspace_id":      str,
                "domain_id":         str,
                "method_id":         str,
                "status":            "succeeded",
                "started_at":        str,
                "finished_at":       str,
                "ssv_ref":           None,
                "result":            dict,
                "execution_witness": {"compute_class": "classical", "backend_id": str},
            }

        Shape for failure::

            {
                "run_id":        str,
                "workspace_id":  str,
                "domain_id":     str,
                "method_id":     str,
                "status":        "failed",
                "started_at":    str,
                "finished_at":   str,
                "error": {
                    "error_code": str,
                    "message":    str,
                },
            }
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
        # ssv_ref is omitted (not set to None) — schema type is "string", not nullable.
        # The daemon fills ssv_ref once an SSV has been committed.
        return {
            **base,
            "status": "succeeded",
            "result": method_output.get("result", {}),
            "execution_witness": {
                "compute_class": "classical",
                "backend_id": method_output["domain_id"],
            },
        }

    # status == "error" (or anything unexpected) → failed
    error_code = method_output.get("error_code", "EXECUTION_ERROR")
    # Normalise to plain string (handles MethodErrorCode enum)
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
