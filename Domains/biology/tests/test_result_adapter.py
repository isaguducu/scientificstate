"""Result adapter tests -- SSV shape, run-result adaptation, lowercase fields."""

from biology.result_adapter import adapt_to_run_result, to_ssv


SAMPLE_RUN_CONTEXT = {
    "run_id": "run-bio-001",
    "workspace_id": "ws-bio-001",
    "started_at": "2026-04-04T10:00:00+00:00",
}


# -- adapt_to_run_result -----------------------------------------------------


def test_adapter_success_status():
    output = {
        "method_id": "pcr_amplification",
        "domain_id": "biology",
        "status": "ok",
        "result": {"ct_value": 20.5},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["status"] == "succeeded"


def test_adapter_success_has_execution_witness():
    output = {
        "method_id": "pcr_amplification",
        "domain_id": "biology",
        "status": "ok",
        "result": {"ct_value": 20.5},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    ew = result["execution_witness"]
    assert ew["compute_class"] == "classical"
    assert ew["backend_id"] == "biology"


def test_adapter_error_status_failed():
    output = {
        "method_id": "pcr_amplification",
        "domain_id": "biology",
        "status": "error",
        "error_code": "INVALID_PARAMS",
        "error": "missing cycles",
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "INVALID_PARAMS"
    assert "cycles" in result["error"]["message"]


def test_adapter_echoes_run_context():
    output = {
        "method_id": "pcr_amplification",
        "domain_id": "biology",
        "status": "ok",
        "result": {},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["run_id"] == "run-bio-001"
    assert result["workspace_id"] == "ws-bio-001"
    assert result["started_at"] == "2026-04-04T10:00:00+00:00"


def test_adapter_has_finished_at():
    output = {
        "method_id": "pcr_amplification",
        "domain_id": "biology",
        "status": "ok",
        "result": {},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert "finished_at" in result


# -- to_ssv (SSV 7-tuple) ---------------------------------------------------


def test_ssv_has_all_lowercase_fields():
    """SSV must have all 8 lowercase fields."""
    method_result = {"result": {"ct_value": 20.5}}
    ssv = to_ssv(method_result, "pcr_amplification")
    for key in ("d", "i", "a", "t", "r", "u", "v", "p"):
        assert key in ssv, f"Missing SSV field: {key}"


def test_ssv_no_uppercase_fields():
    """SSV fields must be lowercase -- no D, I, A, T, R, U, V, P."""
    method_result = {}
    ssv = to_ssv(method_result, "pcr_amplification")
    for key in ("D", "I", "A", "T", "R", "U", "V", "P"):
        assert key not in ssv, f"Uppercase field found: {key}"


def test_ssv_assumptions_is_list():
    method_result = {"assumptions": [{"type": "bg", "description": "test"}]}
    ssv = to_ssv(method_result, "pcr_amplification")
    assert isinstance(ssv["a"], list)


def test_ssv_provenance_is_dict():
    method_result = {"provenance": {"researcher": "test"}}
    ssv = to_ssv(method_result, "pcr_amplification")
    assert isinstance(ssv["p"], dict)


def test_ssv_missing_data_graceful():
    """Missing keys -> None (not KeyError)."""
    ssv = to_ssv({}, "pcr_amplification")
    assert ssv["d"] is None
    assert ssv["i"] is None
    assert ssv["u"] is None
    assert ssv["v"] is None
