"""ReplicationEngine tests — create_request, submit_result, get_history."""


def _make_ssv(quantities: dict) -> dict:
    """Minimal SSV dict for testing."""
    return {
        "r": {"quantities": quantities, "method": "test", "notes": ""},
        "t": [{"algorithm": "test_method", "parameters": {}}],
    }


# ── create_request ──────────────────────────────────────────────────────────


def test_create_request_returns_pending():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request(
        claim_id="claim-1",
        source_institution_id="inst-A",
        target_institution_id="inst-B",
        method_id="bell_state",
    )
    assert req["status"] == "pending"
    assert req["claim_id"] == "claim-1"
    assert req["source_institution_id"] == "inst-A"
    assert req["target_institution_id"] == "inst-B"
    assert "request_id" in req
    assert "created_at" in req


def test_create_request_with_tolerance():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request(
        claim_id="claim-2",
        source_institution_id="inst-A",
        target_institution_id="inst-C",
        method_id="test",
        tolerance={"absolute": 0.01, "relative": 0.05},
    )
    assert req["tolerance"]["absolute"] == 0.01
    assert req["tolerance"]["relative"] == 0.05


def test_create_request_with_compute_class():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request(
        claim_id="claim-3",
        source_institution_id="inst-A",
        target_institution_id="inst-B",
        method_id="test",
        compute_class="quantum_hw",
    )
    assert req["compute_class"] == "quantum_hw"


def test_create_request_unique_ids():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    r1 = engine.create_request("c1", "a", "b", "m")
    r2 = engine.create_request("c2", "a", "c", "m")
    assert r1["request_id"] != r2["request_id"]


# ── get_request ──────────────────────────────────────────────────────────────


def test_get_request_found():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request("c1", "a", "b", "m")
    found = engine.get_request(req["request_id"])
    assert found is not None
    assert found["claim_id"] == "c1"


def test_get_request_not_found():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    assert engine.get_request("nonexistent") is None


# ── submit_result ────────────────────────────────────────────────────────────


def test_submit_result_confirmed():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    source = _make_ssv({"mw": 50000.0, "pdi": 1.2})
    target = _make_ssv({"mw": 50000.0, "pdi": 1.2})

    engine.register_ssv("ssv-source-1", source)
    req = engine.create_request(
        "claim-1", "inst-A", "inst-B", "test", source_ssv_id="ssv-source-1"
    )
    result = engine.submit_result(req["request_id"], "target-1", target)

    assert result["status"] == "confirmed"
    assert result["source_ssv_id"] == "ssv-source-1"
    assert result["target_ssv_id"] == "target-1"
    assert result["comparison_report"]["result_match"] is True
    assert "replicated_at" in result


def test_submit_result_not_confirmed():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    source = _make_ssv({"mw": 50000.0, "pdi": 1.2})
    target = _make_ssv({"mw": 99999.0, "pdi": 9.9})

    engine.register_ssv("ssv-source-2", source)
    req = engine.create_request(
        "claim-2", "inst-A", "inst-B", "test", source_ssv_id="ssv-source-2"
    )
    result = engine.submit_result(req["request_id"], "target-2", target)

    assert result["status"] == "not_confirmed"
    assert result["comparison_report"]["result_match"] is False


def test_submit_result_updates_request_status():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    source = _make_ssv({"x": 1.0})
    target = _make_ssv({"x": 1.0})

    engine.register_ssv("ssv-c1", source)
    req = engine.create_request("c1", "a", "b", "m", source_ssv_id="ssv-c1")
    assert req["status"] == "pending"

    engine.submit_result(req["request_id"], "t1", target)
    updated = engine.get_request(req["request_id"])
    assert updated["status"] == "confirmed"


def test_submit_result_unknown_request():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    try:
        engine.submit_result("nonexistent", "t1")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Unknown replication request" in str(e)


def test_submit_result_missing_source_ssv():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request(
        "missing-claim", "a", "b", "m", source_ssv_id="ssv-missing"
    )
    try:
        engine.submit_result(req["request_id"], "t1", _make_ssv({"x": 1}))
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Source SSV not found" in str(e)


def test_submit_result_missing_source_ssv_id():
    """Request without source_ssv_id → ValueError."""
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    req = engine.create_request("claim-no-ssv", "a", "b", "m")
    try:
        engine.submit_result(req["request_id"], "t1", _make_ssv({"x": 1}))
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "missing source_ssv_id" in str(e)


# ── get_history ──────────────────────────────────────────────────────────────


def test_get_history_returns_matching():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    engine.create_request("claim-A", "a", "b", "m1")
    engine.create_request("claim-A", "a", "c", "m2")
    engine.create_request("claim-B", "a", "d", "m3")

    history = engine.get_history("claim-A")
    assert len(history) == 2
    assert all(r["claim_id"] == "claim-A" for r in history)


def test_get_history_empty():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    assert engine.get_history("nonexistent") == []


# ── register_ssv ─────────────────────────────────────────────────────────────


def test_register_ssv_then_submit():
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    source = _make_ssv({"val": 42.0})
    target = _make_ssv({"val": 42.0})

    engine.register_ssv("ssv-c1", source)
    engine.register_ssv("t1", target)

    req = engine.create_request("c1", "a", "b", "m", source_ssv_id="ssv-c1")
    result = engine.submit_result(req["request_id"], "t1")
    assert result["status"] == "confirmed"
