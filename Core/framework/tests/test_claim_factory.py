"""Claim factory tests — SSV → draft claim creation."""


def _ssv(id_="ssv-test-123"):
    return {
        "id": id_, "version": 1, "parent_ssv_id": None,
        "d": {}, "i": {}, "a": [], "t": [], "r": {}, "u": {}, "v": {}, "p": {},
    }


# ── Import ─────────────────────────────────────────────────────────────────────

def test_claim_factory_import():
    from scientificstate.claims.factory import create_claim_from_ssv
    assert create_claim_from_ssv is not None


# ── Creation ───────────────────────────────────────────────────────────────────

def test_claim_creation_succeeds():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Is MW > 40 kDa?")
    assert isinstance(claim, dict)


def test_initial_status_is_draft():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q1")
    assert claim["status"] == "draft"


def test_ssv_reference_is_linked():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv("my-ssv-id"), question_ref="Q1")
    assert claim["ssv_id"] == "my-ssv-id"


def test_question_ref_preserved():
    from scientificstate.claims.factory import create_claim_from_ssv
    q = "Does MW increase with temperature?"
    claim = create_claim_from_ssv(_ssv(), question_ref=q)
    assert claim["question_ref"] == q


def test_all_gate_fields_are_false():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q")
    for gate in ("gate_e1", "gate_u1", "gate_v1", "gate_c1", "gate_h1"):
        assert claim[gate] is False, f"{gate} must be False at creation"


def test_evidence_paths_empty():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q")
    assert claim["evidence_paths"] == []


def test_contradictions_empty():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q")
    assert claim["contradictions"] == []


def test_endorsement_record_is_none():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q")
    assert claim["endorsement_record"] is None


def test_each_claim_has_unique_id():
    from scientificstate.claims.factory import create_claim_from_ssv
    c1 = create_claim_from_ssv(_ssv(), question_ref="Q")
    c2 = create_claim_from_ssv(_ssv(), question_ref="Q")
    assert c1["claim_id"] != c2["claim_id"]


def test_uncertainty_and_validity_flags_false():
    from scientificstate.claims.factory import create_claim_from_ssv
    claim = create_claim_from_ssv(_ssv(), question_ref="Q")
    assert claim["uncertainty_present"] is False
    assert claim["validity_scope_present"] is False
