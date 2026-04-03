"""
Run lifecycle FSM — deterministic state transitions.

Valid transitions:
  pending  → running
  running  → succeeded
  running  → failed

All other transitions are invalid and raise ValueError.
This is a pure function module: no I/O, no side effects.
"""
from __future__ import annotations

from scientificstate.runs.model import ComputeRun, RunStatus

_VALID_TRANSITIONS: dict[RunStatus, list[RunStatus]] = {
    RunStatus.PENDING: [RunStatus.RUNNING],
    RunStatus.RUNNING: [RunStatus.SUCCEEDED, RunStatus.FAILED],
    RunStatus.SUCCEEDED: [],
    RunStatus.FAILED: [],
}


def transition(run: ComputeRun, new_status: str) -> ComputeRun:
    """Apply a state transition to a ComputeRun.

    Args:
        run: current ComputeRun instance (frozen)
        new_status: target status string ("pending" | "running" | "succeeded" | "failed")

    Returns:
        New ComputeRun with updated status (and timestamps as appropriate).

    Raises:
        ValueError: if the transition is not valid from the current state.
    """
    try:
        target = RunStatus(new_status)
    except ValueError:
        raise ValueError(
            f"Unknown run status: {new_status!r}. "
            f"Must be one of {[s.value for s in RunStatus]}"
        )

    allowed = _VALID_TRANSITIONS.get(run.status, [])
    if target not in allowed:
        raise ValueError(
            f"Invalid run transition: {run.status.value!r} → {target.value!r}. "
            f"Allowed from {run.status.value!r}: "
            f"{[s.value for s in allowed] or 'none (terminal state)'}"
        )

    if target == RunStatus.RUNNING:
        return run.mark_running()
    if target == RunStatus.SUCCEEDED:
        # result_ref must be set by caller via mark_succeeded; here we use a sentinel
        # so the FSM can be tested independently of result content.
        return run.mark_succeeded(result_ref=run.result_ref or "")
    if target == RunStatus.FAILED:
        return run.mark_failed()

    # Unreachable — guard
    raise ValueError(f"Unhandled target status: {target}")  # pragma: no cover
