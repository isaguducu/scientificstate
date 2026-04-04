"""OpenLineage export tests — RunEvent format, eventType control."""

from scientificstate.standards.openlineage import (
    run_to_openlineage,
    run_to_dataset_event,
    run_to_job_event,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_run(**overrides) -> dict:
    run = {
        "run_id": "run-ol-001",
        "workspace_id": "ws-1",
        "domain_id": "polymer_science",
        "method_id": "kmd_analysis",
        "status": "succeeded",
        "started_at": "2026-04-04T12:00:00+00:00",
        "finished_at": "2026-04-04T12:00:05+00:00",
    }
    run.update(overrides)
    return run


def _make_ssv() -> dict:
    return {
        "id": "ssv-ol-001",
        "d": {"ref": "data-ref-1", "domain": "polymer_science"},
        "r": {"quantities": {"mw": 50000.0}},
        "p": {
            "execution_witness": {"compute_class": "classical", "backend_id": "polymer_science"},
        },
    }


# ── RunEvent format ──────────────────────────────────────────────────────────

def test_run_event_has_required_fields():
    event = run_to_openlineage(_make_run(), ssv=_make_ssv())
    for field in ("eventType", "eventTime", "producer", "run", "job", "inputs", "outputs"):
        assert field in event


def test_run_event_default_complete():
    event = run_to_openlineage(_make_run())
    assert event["eventType"] == "COMPLETE"


def test_run_event_start():
    event = run_to_openlineage(_make_run(), event_type="START")
    assert event["eventType"] == "START"
    assert event["eventTime"] == "2026-04-04T12:00:00+00:00"


def test_run_event_fail():
    event = run_to_openlineage(_make_run(status="failed"), event_type="FAIL")
    assert event["eventType"] == "FAIL"


def test_run_event_producer():
    event = run_to_openlineage(_make_run())
    assert event["producer"] == "https://scientificstate.org"


def test_run_event_run_id():
    event = run_to_openlineage(_make_run())
    assert event["run"]["runId"] == "run-ol-001"


def test_run_event_job():
    event = run_to_openlineage(_make_run())
    assert event["job"]["namespace"] == "polymer_science"
    assert event["job"]["name"] == "kmd_analysis"


def test_run_event_inputs_with_ssv():
    event = run_to_openlineage(_make_run(), ssv=_make_ssv())
    assert len(event["inputs"]) == 1
    assert event["inputs"][0]["namespace"] == "polymer_science"
    assert event["inputs"][0]["name"] == "data-ref-1"


def test_run_event_outputs_with_ssv():
    event = run_to_openlineage(_make_run(), ssv=_make_ssv())
    assert len(event["outputs"]) == 1
    assert "ssv-ssv-ol-001" in event["outputs"][0]["name"]


def test_run_event_no_ssv():
    event = run_to_openlineage(_make_run())
    assert event["inputs"] == []
    assert event["outputs"] == []


def test_run_event_job_facets_with_ssv():
    event = run_to_openlineage(_make_run(), ssv=_make_ssv())
    facets = event["job"]["facets"]
    assert "computeClass" in facets
    assert facets["computeClass"]["compute_class"] == "classical"


# ── DatasetEvent ─────────────────────────────────────────────────────────────

def test_dataset_event_format():
    event = run_to_dataset_event(_make_run(), _make_ssv())
    assert "dataset" in event
    assert event["dataset"]["namespace"] == "polymer_science"
    assert event["dataset"]["name"] == "data-ref-1"
    assert "eventTime" in event
    assert "producer" in event


def test_dataset_event_has_schema_facet():
    event = run_to_dataset_event(_make_run(), _make_ssv())
    assert "schema" in event["dataset"]["facets"]


# ── JobEvent ─────────────────────────────────────────────────────────────────

def test_job_event_format():
    event = run_to_job_event(_make_run())
    assert "job" in event
    assert event["job"]["namespace"] == "polymer_science"
    assert event["job"]["name"] == "kmd_analysis"
    assert "eventTime" in event
    assert "producer" in event
