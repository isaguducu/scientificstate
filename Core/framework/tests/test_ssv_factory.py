"""SSV factory tests — run result → SSV dict mapping."""


def _assumptions():
    return [{"assumption_id": "a1", "description": "linear baseline", "type": "background_model"}]


def _manifest(method_id="mw_distribution"):
    return {"method_id": method_id, "parameters": {"peaks": 3}}


def _full_result(domain_id="polymer_science"):
    return {
        "method_id": "mw_distribution",
        "domain_id": domain_id,
        "status": "ok",
        "result": {"mw": 50000.0, "pdi": 1.2},
        "diagnostics": {
            "uncertainty": {"mw": 500.0, "pdi": 0.05},
            "validity_scope": ["temperature < 200C", "concentration 0.1-10 mg/mL"],
        },
    }


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_factory_import():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    assert create_ssv_from_run_result is not None


def test_happy_path_returns_dict():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert isinstance(ssv, dict)


def test_happy_path_has_required_top_level_keys():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    for key in ("id", "version", "parent_ssv_id", "d", "i", "a", "t", "r", "u", "v", "p"):
        assert key in ssv, f"Missing key: {key}"


def test_happy_path_no_incomplete_flags():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert "incomplete_flags" not in ssv


def test_r_contains_result_quantities():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert ssv["r"]["quantities"]["mw"] == 50000.0


def test_a_contains_caller_assumptions():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert ssv["a"] == _assumptions()


def test_t_chain_uses_method_id():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest("my_method"), _assumptions())
    assert ssv["t"][0]["name"] == "my_method"


def test_p_has_execution_witness():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert "execution_witness" in ssv["p"]
    assert ssv["p"]["execution_witness"]["compute_class"] == "classical"


# ── Missing uncertainty (P4) ───────────────────────────────────────────────────

def test_missing_uncertainty_adds_incomplete_flag():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    result = {**_full_result(), "diagnostics": {"validity_scope": ["T < 200C"]}}
    ssv = create_ssv_from_run_result(result, _manifest(), _assumptions())
    assert "incomplete_flags" in ssv
    assert "missing_uncertainty" in ssv["incomplete_flags"]


def test_missing_uncertainty_still_builds_ssv():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    result = {**_full_result(), "diagnostics": {"validity_scope": ["T < 200C"]}}
    ssv = create_ssv_from_run_result(result, _manifest(), _assumptions())
    assert ssv["id"]
    assert "u" in ssv


# ── Missing validity scope (P5) ────────────────────────────────────────────────

def test_missing_validity_scope_adds_incomplete_flag():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    result = {**_full_result(), "diagnostics": {"uncertainty": {"mw": 100.0}}}
    ssv = create_ssv_from_run_result(result, _manifest(), _assumptions())
    assert "missing_validity_scope" in ssv["incomplete_flags"]


def test_missing_validity_scope_still_builds_ssv():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    result = {**_full_result(), "diagnostics": {"uncertainty": {"mw": 100.0}}}
    ssv = create_ssv_from_run_result(result, _manifest(), _assumptions())
    assert "v" in ssv


def test_both_missing_has_two_flags():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    result = {**_full_result(), "diagnostics": {}}
    ssv = create_ssv_from_run_result(result, _manifest(), _assumptions())
    flags = ssv["incomplete_flags"]
    assert "missing_uncertainty" in flags
    assert "missing_validity_scope" in flags


# ── Empty result ───────────────────────────────────────────────────────────────

def test_empty_result_builds_ssv():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv = create_ssv_from_run_result({}, {}, [])
    assert isinstance(ssv, dict)
    assert ssv["version"] == 1


def test_each_call_produces_unique_id():
    from scientificstate.ssv.factory import create_ssv_from_run_result
    ssv1 = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    ssv2 = create_ssv_from_run_result(_full_result(), _manifest(), _assumptions())
    assert ssv1["id"] != ssv2["id"]
