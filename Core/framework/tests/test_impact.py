"""Tests for deterministic impact score calculator."""
from __future__ import annotations

import pytest

from scientificstate.discovery.impact import ImpactCalculator


@pytest.fixture()
def calc():
    return ImpactCalculator()


# ── weight validation ──────────────────────────────────────────────────


def test_weights_sum_to_one(calc):
    total = calc.W_REPLICATION + calc.W_CITATION + calc.W_GATE + calc.W_DIVERSITY
    assert abs(total - 1.0) < 1e-9


# ── zero inputs ────────────────────────────────────────────────────────


def test_zero_everything(calc):
    result = calc.calculate("c1", 0, 0, 0, 0, 0, 0)
    assert result["score"] == 0.0
    assert result["claim_id"] == "c1"
    for v in result["breakdown"].values():
        assert v == 0.0


def test_zero_replication_requests(calc):
    result = calc.calculate("c2", 0, 0, 5, 3, 5, 1)
    assert result["breakdown"]["replication_ratio"] == 0.0


# ── full score ─────────────────────────────────────────────────────────


def test_perfect_score(calc):
    result = calc.calculate(
        "perfect", replication_count=10, total_replication_requests=10,
        citation_count=50, passed_gates=5, total_gates=5, unique_institutions=3,
    )
    assert result["score"] == 1.0


def test_perfect_score_components(calc):
    result = calc.calculate("p", 10, 10, 50, 5, 5, 3)
    b = result["breakdown"]
    assert b["replication_ratio"] == 1.0
    assert b["citation_depth"] == 1.0
    assert b["gate_completeness"] == 1.0
    assert b["institutional_diversity"] == 1.0


# ── individual components ──────────────────────────────────────────────


def test_replication_only(calc):
    result = calc.calculate("r", 5, 10, 0, 0, 0, 0)
    expected = 0.35 * 0.5
    assert result["score"] == round(expected, 3)


def test_citation_only(calc):
    result = calc.calculate("c", 0, 0, 25, 0, 0, 0)
    expected = 0.25 * (25 / 50)
    assert result["score"] == round(expected, 3)


def test_gate_only(calc):
    result = calc.calculate("g", 0, 0, 0, 3, 4, 0)
    expected = 0.25 * (3 / 4)
    assert result["score"] == round(expected, 3)


def test_diversity_only(calc):
    result = calc.calculate("d", 0, 0, 0, 0, 0, 2)
    expected = 0.15 * (2 / 3)
    assert result["score"] == round(expected, 3)


# ── normalization caps ─────────────────────────────────────────────────


def test_citation_capped_at_max(calc):
    result = calc.calculate("cap", 0, 0, 100, 0, 0, 0)
    assert result["breakdown"]["citation_depth"] == 1.0


def test_diversity_capped_at_3(calc):
    result = calc.calculate("cap", 0, 0, 0, 0, 0, 10)
    assert result["breakdown"]["institutional_diversity"] == 1.0


# ── output structure ───────────────────────────────────────────────────


def test_output_has_required_keys(calc):
    result = calc.calculate("s", 1, 2, 3, 4, 5, 1)
    assert set(result.keys()) == {"claim_id", "score", "breakdown", "weights"}
    assert set(result["breakdown"].keys()) == {
        "replication_ratio", "citation_depth", "gate_completeness",
        "institutional_diversity",
    }
    assert set(result["weights"].keys()) == {
        "replication", "citation", "gate", "diversity",
    }


def test_weights_in_output(calc):
    result = calc.calculate("w", 0, 0, 0, 0, 0, 0)
    assert result["weights"]["replication"] == 0.35
    assert result["weights"]["citation"] == 0.25
    assert result["weights"]["gate"] == 0.25
    assert result["weights"]["diversity"] == 0.15


# ── edge cases ─────────────────────────────────────────────────────────


def test_more_replications_than_requests(calc):
    """Replication ratio can exceed 1.0 (extra confirmations)."""
    result = calc.calculate("e", 5, 3, 0, 0, 0, 0)
    assert result["breakdown"]["replication_ratio"] > 1.0


def test_single_gate(calc):
    result = calc.calculate("sg", 0, 0, 0, 1, 1, 0)
    assert result["breakdown"]["gate_completeness"] == 1.0


def test_score_is_rounded(calc):
    result = calc.calculate("round", 1, 3, 7, 2, 3, 1)
    # score is rounded to 3 decimal places
    score_str = str(result["score"])
    if "." in score_str:
        decimals = len(score_str.split(".")[1])
        assert decimals <= 3
