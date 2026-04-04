"""Result adapter tests -- SSV shape, run-result adaptation, lowercase fields."""

from chemistry.result_adapter import adapt_to_run_result, to_ssv


SAMPLE_RUN_CONTEXT = {
    "run_id": "run-chem-001",
    "workspace_id": "ws-chem-001",
    "started_at": "2026-04-04T10:00:00+00:00",
}


# -- adapt_to_run_result -----------------------------------------------------


def test_adapter_success_status():
    output = {
        "method_id": "uv_vis_spectroscopy",
        "domain_id": "chemistry",
        "status": "ok",
        "result": {"lambda_max_nm": 450.0},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["status"] == "succeeded"


def test_adapter_success_has_execution_witness():
    output = {
        "method_id": "uv_vis_spectroscopy",
        "domain_id": "chemistry",
        "status": "ok",
        "result": {"lambda_max_nm": 450.0},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    ew = result["execution_witness"]
    assert ew["compute_class"] == "classical"
    assert ew["backend_id"] == "chemistry"


def test_adapter_error_status_failed():
    output = {
        "method_id": "uv_vis_spectroscopy",
        "domain_id": "chemistry",
        "status": "error",
        "error_code": "INVALID_PARAMS",
        "error": "missing wavelength",
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "INVALID_PARAMS"
    assert "wavelength" in result["error"]["message"]


def test_adapter_echoes_run_context():
    output = {
        "method_id": "uv_vis_spectroscopy",
        "domain_id": "chemistry",
        "status": "ok",
        "result": {},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert result["run_id"] == "run-chem-001"
    assert result["workspace_id"] == "ws-chem-001"
    assert result["started_at"] == "2026-04-04T10:00:00+00:00"


def test_adapter_has_finished_at():
    output = {
        "method_id": "uv_vis_spectroscopy",
        "domain_id": "chemistry",
        "status": "ok",
        "result": {},
        "diagnostics": {},
    }
    result = adapt_to_run_result(output, SAMPLE_RUN_CONTEXT)
    assert "finished_at" in result


# -- to_ssv (SSV 7-tuple) ---------------------------------------------------


def test_ssv_has_all_lowercase_fields():
    """SSV must have all 8 lowercase fields."""
    method_result = {"result": {"lambda_max_nm": 450.0}}
    ssv = to_ssv(method_result, "uv_vis_spectroscopy")
    for key in ("d", "i", "a", "t", "r", "u", "v", "p"):
        assert key in ssv, f"Missing SSV field: {key}"


def test_ssv_no_uppercase_fields():
    """SSV fields must be lowercase -- no D, I, A, T, R, U, V, P."""
    method_result = {}
    ssv = to_ssv(method_result, "uv_vis_spectroscopy")
    for key in ("D", "I", "A", "T", "R", "U", "V", "P"):
        assert key not in ssv, f"Uppercase field found: {key}"


def test_ssv_assumptions_is_list():
    method_result = {"assumptions": [{"type": "bg", "description": "test"}]}
    ssv = to_ssv(method_result, "uv_vis_spectroscopy")
    assert isinstance(ssv["a"], list)


def test_ssv_provenance_is_dict():
    method_result = {"provenance": {"researcher": "test"}}
    ssv = to_ssv(method_result, "uv_vis_spectroscopy")
    assert isinstance(ssv["p"], dict)


def test_ssv_missing_data_graceful():
    """Missing keys -> None (not KeyError)."""
    ssv = to_ssv({}, "uv_vis_spectroscopy")
    assert ssv["d"] is None
    assert ssv["i"] is None
    assert ssv["u"] is None
    assert ssv["v"] is None
