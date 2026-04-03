"""Run lifecycle FSM tests — valid + invalid transitions."""
import pytest

from scientificstate.runs.model import ComputeRun, RunStatus


def _run(**kwargs) -> ComputeRun:
    return ComputeRun(workspace_id="ws-1", domain_id="d", method_id="m", **kwargs)


# ── Valid transitions ──────────────────────────────────────────────────────────

def test_pending_to_running():
    from scientificstate.runs.lifecycle import transition
    run = _run()
    assert run.status == RunStatus.PENDING
    result = transition(run, "running")
    assert result.status == RunStatus.RUNNING
    assert result.started_at is not None


def test_running_to_succeeded():
    from scientificstate.runs.lifecycle import transition
    run = transition(_run(), "running")
    result = transition(run, "succeeded")
    assert result.status == RunStatus.SUCCEEDED
    assert result.finished_at is not None


def test_running_to_failed():
    from scientificstate.runs.lifecycle import transition
    run = transition(_run(), "running")
    result = transition(run, "failed")
    assert result.status == RunStatus.FAILED
    assert result.finished_at is not None


def test_transition_returns_new_instance():
    from scientificstate.runs.lifecycle import transition
    run = _run()
    result = transition(run, "running")
    assert result is not run
    assert run.status == RunStatus.PENDING  # original unchanged


# ── Invalid transitions — all must raise ValueError ───────────────────────────

def test_succeeded_to_running_raises():
    from scientificstate.runs.lifecycle import transition
    run = transition(transition(_run(), "running"), "succeeded")
    with pytest.raises(ValueError, match="succeeded"):
        transition(run, "running")


def test_failed_to_pending_raises():
    from scientificstate.runs.lifecycle import transition
    run = transition(transition(_run(), "running"), "failed")
    with pytest.raises(ValueError, match="failed"):
        transition(run, "pending")


def test_pending_to_succeeded_raises():
    from scientificstate.runs.lifecycle import transition
    with pytest.raises(ValueError):
        transition(_run(), "succeeded")


def test_pending_to_failed_raises():
    from scientificstate.runs.lifecycle import transition
    with pytest.raises(ValueError):
        transition(_run(), "failed")


def test_running_to_pending_raises():
    from scientificstate.runs.lifecycle import transition
    run = transition(_run(), "running")
    with pytest.raises(ValueError):
        transition(run, "pending")


def test_unknown_status_raises():
    from scientificstate.runs.lifecycle import transition
    with pytest.raises(ValueError, match="Unknown run status"):
        transition(_run(), "flying")


def test_succeeded_to_failed_raises():
    from scientificstate.runs.lifecycle import transition
    run = transition(transition(_run(), "running"), "succeeded")
    with pytest.raises(ValueError):
        transition(run, "failed")


def test_failed_to_succeeded_raises():
    from scientificstate.runs.lifecycle import transition
    run = transition(transition(_run(), "running"), "failed")
    with pytest.raises(ValueError):
        transition(run, "succeeded")
