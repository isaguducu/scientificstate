"""SSV completeness validator tests — P3/P4/P5 gate checks."""


def test_validator_import():
    from scientificstate.ssv.validator import validate_ssv, ValidationResult
    assert validate_ssv is not None
    assert ValidationResult is not None


def test_empty_dict_fails_with_missing_fields():
    from scientificstate.ssv.validator import validate_ssv
    result = validate_ssv({})
    assert result.passed is False
    assert len(result.missing_fields) > 0


def test_complete_ssv_dict_passes():
    """A structurally complete SSV dict must pass all P3/P4/P5 checks."""
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "test-id",
        "version": 1,
        "d": {"ref": "file://sample.csv"},
        "i": {"instrument_id": "GC-MS-001"},
        "a": [{"assumption_id": "a1", "description": "linear baseline", "type": "background_model"}],
        "t": [{"step_id": 1, "operation": "baseline_correction", "parameters": {}}],
        "r": {"quantities": [{"name": "mw", "value": 50000.0, "unit": "g/mol"}]},
        "u": {"measurement_error": {"mw": 500.0}},
        "v": {"conditions": ["temperature < 200C"]},
        "p": {"user_id": "researcher-1", "created_at": "2026-04-03T00:00:00Z", "software_stack": [{"name": "ss", "version": "0.1.0"}]},
    }
    result = validate_ssv(ssv)
    assert result.passed is True
    assert result.missing_fields == []


def test_p3_fails_when_assumptions_empty_list():
    """P3: assumptions list must not be empty."""
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "x", "version": 1,
        "d": {"ref": "file://d.csv"},
        "i": {"instrument_id": "inst-1"},
        "a": [],  # P3 violation
        "t": [{}],
        "r": {"quantities": [{"name": "mw", "value": 1.0, "unit": "g/mol"}]},
        "u": {"measurement_error": {"mw": 0.1}},
        "v": {"conditions": ["T < 200"]},
        "p": {},
    }
    result = validate_ssv(ssv)
    assert result.passed is False
    assert any("P3" in f for f in result.missing_fields)


def test_p4_fails_when_uncertainty_missing():
    """P4: uncertainty model is mandatory."""
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "x", "version": 1,
        "d": {"ref": "file://d.csv"},
        "i": {"instrument_id": "inst-1"},
        "a": [{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        "t": [{}],
        "r": {"quantities": [{"name": "mw", "value": 1.0, "unit": "g/mol"}]},
        "u": None,  # P4 violation
        "v": {"conditions": ["T < 200"]},
        "p": {},
    }
    result = validate_ssv(ssv)
    assert result.passed is False
    assert any("P4" in f for f in result.missing_fields)


def test_p5_fails_when_validity_missing():
    """P5: validity domain is mandatory."""
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "x", "version": 1,
        "d": {"ref": "file://d.csv"},
        "i": {"instrument_id": "inst-1"},
        "a": [{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        "t": [{}],
        "r": {"quantities": [{"name": "mw", "value": 1.0, "unit": "g/mol"}]},
        "u": {"measurement_error": {"mw": 0.1}},
        "v": None,  # P5 violation
        "p": {},
    }
    result = validate_ssv(ssv)
    assert result.passed is False
    assert any("P5" in f for f in result.missing_fields)


def test_p4_passes_with_unquantifiable_reason():
    """P4 alternative: unquantifiable_with_reason is valid."""
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "x", "version": 1,
        "d": {"ref": "file://d.csv"},
        "i": {"instrument_id": "inst-1"},
        "a": [{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        "t": [{}],
        "r": {"quantities": [{"name": "mw", "value": 1.0, "unit": "g/mol"}]},
        "u": {"reason_if_unquantifiable": "insufficient replicates for propagation"},
        "v": {"conditions": ["T < 200"]},
        "p": {},
    }
    result = validate_ssv(ssv)
    assert result.passed is True


def test_validation_result_is_frozen():
    from scientificstate.ssv.validator import ValidationResult
    import pytest
    vr = ValidationResult(passed=True, missing_fields=[])
    with pytest.raises((AttributeError, TypeError)):
        vr.passed = False  # type: ignore[misc]


def test_missing_d_ref_is_reported():
    from scientificstate.ssv.validator import validate_ssv
    ssv = {
        "id": "x", "version": 1,
        "d": {},  # no ref
        "i": {"instrument_id": "inst-1"},
        "a": [{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        "t": [{}],
        "r": {"quantities": [{"name": "mw", "value": 1.0, "unit": "g/mol"}]},
        "u": {"measurement_error": {"mw": 0.1}},
        "v": {"conditions": ["T < 200"]},
        "p": {},
    }
    result = validate_ssv(ssv)
    assert result.passed is False
    assert "d.ref" in result.missing_fields
