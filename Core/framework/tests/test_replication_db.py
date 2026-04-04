"""Tests for replication engine with store injection and protocol endorsement.

All tests are SYNC — no async, no aiosqlite. Framework layer only.
"""
import pytest


# ── Engine: SYNC in-memory ────────────────────────────────────────────────────


def test_create_request_sync():
    """engine.create_request works SYNC and returns a dict with request_id."""
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    result = engine.create_request(
        claim_id="claim-1",
        source_institution_id="inst-A",
        target_institution_id="inst-B",
        method_id="dft-pw",
        compute_class="quantum_hw",
        source_ssv_id="ssv-1",
    )
    assert "request_id" in result
    assert result["status"] == "pending"
    assert result["claim_id"] == "claim-1"


def test_create_request_self_replication_fail():
    """source == target raises ValueError."""
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()
    with pytest.raises(ValueError, match="Self-replication not allowed"):
        engine.create_request(
            claim_id="claim-1",
            source_institution_id="inst-A",
            target_institution_id="inst-A",
            method_id="dft-pw",
        )


# ── Engine: store injection ───────────────────────────────────────────────────


class MockStore:
    """In-memory mock that satisfies ReplicationStore protocol."""

    def __init__(self):
        self.saved_requests: list[dict] = []
        self.saved_results: list[dict] = []

    def save_request(self, request: dict) -> str:
        self.saved_requests.append(request)
        return request["request_id"]

    def save_result(self, result: dict) -> str:
        self.saved_results.append(result)
        return "result-mock-id"

    def get_requests_by_claim(self, claim_id: str) -> list[dict]:
        return [r for r in self.saved_requests if r["claim_id"] == claim_id]

    def get_results_by_request(self, request_id: str) -> list[dict]:
        return [r for r in self.saved_results if r["request_id"] == request_id]

    def update_request_status(self, request_id: str, status: str) -> None:
        for r in self.saved_requests:
            if r["request_id"] == request_id:
                r["status"] = status


def test_store_injection():
    """Engine with mock store saves to store, not in-memory dict."""
    from scientificstate.replication.engine import ReplicationEngine

    store = MockStore()
    engine = ReplicationEngine(store=store)
    result = engine.create_request(
        claim_id="claim-2",
        source_institution_id="inst-X",
        target_institution_id="inst-Y",
        method_id="md-sim",
        compute_class="quantum_hw",
        source_ssv_id="ssv-2",
    )
    assert result["status"] == "pending"
    assert len(store.saved_requests) == 1
    assert store.saved_requests[0]["claim_id"] == "claim-2"

    # get_history should go through store
    history = engine.get_history("claim-2")
    assert len(history) == 1


def test_in_memory_fallback():
    """Engine without store uses in-memory dict."""
    from scientificstate.replication.engine import ReplicationEngine

    engine = ReplicationEngine()  # no store
    result = engine.create_request(
        claim_id="claim-3",
        source_institution_id="inst-A",
        target_institution_id="inst-B",
        method_id="dft",
        source_ssv_id="ssv-3",
    )
    assert result["status"] == "pending"
    history = engine.get_history("claim-3")
    assert len(history) == 1
    assert history[0]["request_id"] == result["request_id"]


# ── Protocol: endorsement validation ─────────────────────────────────────────


def test_endorsement_requires_confirmed():
    """Protocol returns not endorsable without confirmed replication."""
    from scientificstate.replication.protocol import validate_replication_for_endorsement

    claim = {"compute_class": "quantum_hw"}
    result = validate_replication_for_endorsement(
        claim,
        replication_history=[
            {
                "request_id": "r1",
                "status": "pending",
                "source_institution_id": "inst-A",
                "target_institution_id": "inst-B",
            }
        ],
    )
    assert result["endorsable"] is False


def test_endorsement_with_confirmed():
    """Protocol returns endorsable with confirmed cross-institutional replication."""
    from scientificstate.replication.protocol import validate_replication_for_endorsement

    claim = {"compute_class": "quantum_hw"}
    result = validate_replication_for_endorsement(
        claim,
        replication_history=[
            {
                "request_id": "r1",
                "status": "confirmed",
                "source_institution_id": "inst-A",
                "target_institution_id": "inst-B",
            }
        ],
    )
    assert result["endorsable"] is True
    assert "1 confirmed" in result["reason"]


def test_endorsement_self_replication_not_counted():
    """Confirmed replication from same institution should not count."""
    from scientificstate.replication.protocol import validate_replication_for_endorsement

    claim = {"compute_class": "quantum_hw"}
    result = validate_replication_for_endorsement(
        claim,
        replication_history=[
            {
                "request_id": "r1",
                "status": "confirmed",
                "source_institution_id": "inst-A",
                "target_institution_id": "inst-A",
            }
        ],
    )
    assert result["endorsable"] is False


def test_endorsement_classical_no_replication_needed():
    """Classical claims do not require replication."""
    from scientificstate.replication.protocol import validate_replication_for_endorsement

    claim = {"compute_class": "classical"}
    result = validate_replication_for_endorsement(claim, replication_history=[])
    assert result["endorsable"] is True
