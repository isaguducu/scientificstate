"""Compute run model smoke tests."""
import pytest


def test_run_import():
    from scientificstate.runs.model import ComputeRun, RunStatus
    assert ComputeRun is not None
    assert RunStatus is not None


def test_run_status_has_4_states():
    from scientificstate.runs.model import RunStatus
    states = {s.value for s in RunStatus}
    assert states == {"pending", "running", "succeeded", "failed"}


def test_run_instantiation_defaults_to_pending():
    from scientificstate.runs.model import ComputeRun, RunStatus
    run = ComputeRun(workspace_id="ws-1", domain_id="polymer_science", method_id="mw_distribution")
    assert run.run_id
    assert run.status == RunStatus.PENDING
    assert run.started_at is None
    assert run.finished_at is None
    assert run.result_ref is None


def test_run_has_required_fields():
    from scientificstate.runs.model import ComputeRun
    fields = ComputeRun.model_fields
    for f in ("run_id", "workspace_id", "domain_id", "method_id", "status",
              "started_at", "finished_at", "execution_witness", "result_ref"):
        assert f in fields, f"Missing field: {f}"


def test_run_mark_running():
    from scientificstate.runs.model import ComputeRun, RunStatus
    run = ComputeRun(workspace_id="ws-1", domain_id="d", method_id="m")
    running = run.mark_running()
    assert running.status == RunStatus.RUNNING
    assert running.started_at is not None
    assert running.run_id == run.run_id  # same id


def test_run_mark_succeeded():
    from scientificstate.runs.model import ComputeRun, RunStatus
    run = ComputeRun(workspace_id="ws-1", domain_id="d", method_id="m").mark_running()
    done = run.mark_succeeded(result_ref="ssv-abc-123")
    assert done.status == RunStatus.SUCCEEDED
    assert done.result_ref == "ssv-abc-123"
    assert done.finished_at is not None


def test_run_mark_failed():
    from scientificstate.runs.model import ComputeRun, RunStatus
    run = ComputeRun(workspace_id="ws-1", domain_id="d", method_id="m").mark_running()
    failed = run.mark_failed()
    assert failed.status == RunStatus.FAILED
    assert failed.finished_at is not None


def test_run_immutable():
    from scientificstate.runs.model import ComputeRun
    run = ComputeRun(workspace_id="ws-1", domain_id="d", method_id="m")
    with pytest.raises((TypeError, Exception)):
        run.status = "running"  # type: ignore[misc]
