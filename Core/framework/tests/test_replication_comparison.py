"""SSVComparison tests — confirmed, partially_confirmed, not_confirmed, tolerance edge cases."""


def _ssv(quantities: dict, method: str = "test") -> dict:
    """Minimal SSV for comparison testing."""
    return {
        "r": {"quantities": quantities, "method": method, "notes": ""},
        "t": [{"algorithm": method, "parameters": {}}],
    }


# ── Exact match ──────────────────────────────────────────────────────────────


def test_exact_match_confirmed():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"mw": 50000.0, "pdi": 1.2}),
        _ssv({"mw": 50000.0, "pdi": 1.2}),
    )
    assert report["status"] == "confirmed"
    assert report["result_match"] is True
    assert report["confidence"] == 1.0
    assert report["differences"] == []


def test_empty_quantities_confirmed():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(_ssv({}), _ssv({}))
    assert report["status"] == "confirmed"


# ── Within tolerance ─────────────────────────────────────────────────────────


def test_within_absolute_tolerance():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.01})
    report = comp.compare(
        _ssv({"mw": 50000.0}),
        _ssv({"mw": 50000.005}),
    )
    assert report["status"] == "confirmed"
    assert report["result_match"] is True


def test_within_relative_tolerance():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"relative": 0.01})
    report = comp.compare(
        _ssv({"mw": 50000.0}),
        _ssv({"mw": 50200.0}),  # 0.4% difference
    )
    assert report["status"] == "confirmed"


def test_outside_tolerance_not_confirmed():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.001, "relative": 0.001})
    report = comp.compare(
        _ssv({"mw": 50000.0}),
        _ssv({"mw": 60000.0}),  # 20% difference
    )
    assert report["status"] == "not_confirmed"
    assert report["result_match"] is False
    assert len(report["differences"]) >= 1


# ── Partially confirmed ─────────────────────────────────────────────────────


def test_partially_confirmed():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.01})
    # 3 fields, 1 differs → confidence = 1 - 1/3 ≈ 0.67 → partially_confirmed
    report = comp.compare(
        _ssv({"a": 1.0, "b": 2.0, "c": 3.0}),
        _ssv({"a": 1.0, "b": 2.0, "c": 999.0}),
    )
    assert report["status"] == "partially_confirmed"
    assert 0.5 <= report["confidence"] < 1.0


def test_all_different_not_confirmed():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.001})
    report = comp.compare(
        _ssv({"a": 1.0, "b": 2.0}),
        _ssv({"a": 999.0, "b": 999.0}),
    )
    assert report["status"] == "not_confirmed"
    assert report["confidence"] == 0.0


# ── Missing fields ───────────────────────────────────────────────────────────


def test_missing_field_in_target():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"a": 1.0, "b": 2.0}),
        _ssv({"a": 1.0}),
    )
    assert report["result_match"] is False
    diff_fields = [d["field"] for d in report["differences"]]
    assert any("b" in f for f in diff_fields)


def test_missing_field_in_source():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"a": 1.0}),
        _ssv({"a": 1.0, "b": 2.0}),
    )
    assert report["result_match"] is False


# ── Method mismatch ──────────────────────────────────────────────────────────


def test_method_mismatch_recorded():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"x": 1.0}, method="method_a"),
        _ssv({"x": 1.0}, method="method_b"),
    )
    method_diffs = [d for d in report["differences"] if d["type"] == "method_mismatch"]
    assert len(method_diffs) == 1


# ── Tolerance defaults ───────────────────────────────────────────────────────


def test_default_tolerance_values():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(_ssv({"x": 1.0}), _ssv({"x": 1.0}))
    assert report["tolerance_used"]["absolute"] == 1e-6
    assert report["tolerance_used"]["relative"] == 1e-4


def test_custom_tolerance_in_report():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.5, "relative": 0.1})
    report = comp.compare(_ssv({"x": 1.0}), _ssv({"x": 1.0}))
    assert report["tolerance_used"]["absolute"] == 0.5
    assert report["tolerance_used"]["relative"] == 0.1


# ── Nested dict comparison ──────────────────────────────────────────────────


def test_nested_dict_comparison():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"outer": {"inner": 1.0}}),
        _ssv({"outer": {"inner": 1.0}}),
    )
    assert report["status"] == "confirmed"


def test_nested_dict_difference():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 0.001})
    report = comp.compare(
        _ssv({"outer": {"inner": 1.0}}),
        _ssv({"outer": {"inner": 999.0}}),
    )
    assert report["result_match"] is False
    assert any("inner" in d["field"] for d in report["differences"])


# ── String value comparison ──────────────────────────────────────────────────


def test_string_value_mismatch():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"label": "alpha"}),
        _ssv({"label": "beta"}),
    )
    assert report["result_match"] is False
    assert report["differences"][0]["type"] == "value_mismatch"


def test_string_value_match():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison()
    report = comp.compare(
        _ssv({"label": "same"}),
        _ssv({"label": "same"}),
    )
    assert report["status"] == "confirmed"


# ── Edge: zero values ───────────────────────────────────────────────────────


def test_zero_tolerance_check():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 1e-6})
    report = comp.compare(
        _ssv({"val": 0.0}),
        _ssv({"val": 0.0}),
    )
    assert report["status"] == "confirmed"


def test_near_zero_within_tolerance():
    from scientificstate.replication.comparison import SSVComparison

    comp = SSVComparison({"absolute": 1e-4})
    report = comp.compare(
        _ssv({"val": 0.0}),
        _ssv({"val": 1e-5}),
    )
    assert report["status"] == "confirmed"
