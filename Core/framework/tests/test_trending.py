"""Tests for trending field calculator — scientific activity velocity."""
from __future__ import annotations

import pytest

from scientificstate.discovery.trending import TrendingCalculator, TrendingField


@pytest.fixture()
def calc():
    return TrendingCalculator()


# ── weight validation ─────────────────────────────────────────────────


def test_weights_sum_to_one(calc):
    total = calc.W_ENDORSEMENT + calc.W_REPLICATION + calc.W_CITATION
    assert abs(total - 1.0) < 1e-9


def test_weight_values(calc):
    assert calc.W_ENDORSEMENT == 0.40
    assert calc.W_REPLICATION == 0.35
    assert calc.W_CITATION == 0.25


# ── velocity calculation ─────────────────────────────────────────────


def test_velocity_normal(calc):
    assert calc._velocity(10, 5) == 2.0


def test_velocity_avg_zero_count_positive(calc):
    """avg=0 and count>0 → large velocity (new field explosion), capped at 10."""
    v = calc._velocity(5, 0)
    assert v == 5.0  # min(5.0, 10.0)


def test_velocity_avg_zero_count_large(calc):
    """avg=0 and count>10 → capped at 10.0."""
    v = calc._velocity(50, 0)
    assert v == 10.0


def test_velocity_both_zero(calc):
    assert calc._velocity(0, 0) == 0.0


def test_velocity_count_zero(calc):
    assert calc._velocity(0, 5) == 0.0


def test_velocity_equal(calc):
    assert calc._velocity(10, 10) == 1.0


def test_velocity_deceleration(calc):
    """Window count < avg → velocity < 1.0 (field slowing down)."""
    v = calc._velocity(2, 10)
    assert v < 1.0
    assert v == 0.2


# ── trending score calculation ────────────────────────────────────────


def test_trending_single_field(calc):
    stats = [
        {
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "endorsement_window": 10,
            "endorsement_avg": 5.0,
            "replication_window": 8,
            "replication_avg": 4.0,
            "citation_window": 6,
            "citation_avg": 3.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert len(result) == 1
    t = result[0]
    # endorsement: 10/5=2.0, replication: 8/4=2.0, citation: 6/3=2.0
    # score = 0.40*2 + 0.35*2 + 0.25*2 = 2.0
    assert t.trending_score == 2.0
    assert t.endorsement_velocity == 2.0
    assert t.replication_velocity == 2.0
    assert t.citation_velocity == 2.0


def test_trending_weighted_correctly(calc):
    stats = [
        {
            "domain_id": "genomics",
            "method_id": None,
            "endorsement_window": 10,
            "endorsement_avg": 10.0,  # velocity = 1.0
            "replication_window": 0,
            "replication_avg": 5.0,   # velocity = 0.0
            "citation_window": 0,
            "citation_avg": 5.0,      # velocity = 0.0
        },
    ]
    result = calc.get_trending_fields(stats)
    assert len(result) == 1
    # Only endorsement contributes: 0.40 * 1.0 = 0.4
    assert result[0].trending_score == 0.4


def test_trending_sorting(calc):
    stats = [
        {
            "domain_id": "low",
            "method_id": None,
            "endorsement_window": 1,
            "endorsement_avg": 10.0,
            "replication_window": 1,
            "replication_avg": 10.0,
            "citation_window": 1,
            "citation_avg": 10.0,
        },
        {
            "domain_id": "high",
            "method_id": None,
            "endorsement_window": 50,
            "endorsement_avg": 5.0,
            "replication_window": 50,
            "replication_avg": 5.0,
            "citation_window": 50,
            "citation_avg": 5.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert result[0].domain_id == "high"
    assert result[1].domain_id == "low"
    assert result[0].trending_score > result[1].trending_score


def test_trending_limit(calc):
    stats = [
        {
            "domain_id": f"domain_{i}",
            "method_id": None,
            "endorsement_window": 10 - i,
            "endorsement_avg": 5.0,
            "replication_window": 10 - i,
            "replication_avg": 5.0,
            "citation_window": 10 - i,
            "citation_avg": 5.0,
        }
        for i in range(15)
    ]
    result = calc.get_trending_fields(stats, limit=5)
    assert len(result) == 5


def test_trending_default_limit(calc):
    stats = [
        {
            "domain_id": f"domain_{i}",
            "method_id": None,
            "endorsement_window": 5,
            "endorsement_avg": 5.0,
            "replication_window": 5,
            "replication_avg": 5.0,
            "citation_window": 5,
            "citation_avg": 5.0,
        }
        for i in range(15)
    ]
    result = calc.get_trending_fields(stats)
    assert len(result) == 10  # default limit


def test_trending_empty_input(calc):
    assert calc.get_trending_fields([]) == []


# ── new field explosion ──────────────────────────────────────────────


def test_new_field_high_velocity(calc):
    """A brand new field with activity but no history should trend high."""
    stats = [
        {
            "domain_id": "new_field",
            "method_id": "new_method",
            "endorsement_window": 8,
            "endorsement_avg": 0.0,
            "replication_window": 5,
            "replication_avg": 0.0,
            "citation_window": 3,
            "citation_avg": 0.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert len(result) == 1
    t = result[0]
    # endorsement: min(8, 10)=8, replication: min(5, 10)=5, citation: min(3, 10)=3
    # score = 0.40*8 + 0.35*5 + 0.25*3 = 3.2 + 1.75 + 0.75 = 5.7
    assert t.trending_score == 5.7
    assert t.endorsement_velocity == 8.0
    assert t.replication_velocity == 5.0
    assert t.citation_velocity == 3.0


# ── zero activity ────────────────────────────────────────────────────


def test_zero_activity(calc):
    stats = [
        {
            "domain_id": "dead_field",
            "method_id": None,
            "endorsement_window": 0,
            "endorsement_avg": 10.0,
            "replication_window": 0,
            "replication_avg": 10.0,
            "citation_window": 0,
            "citation_avg": 10.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert result[0].trending_score == 0.0


# ── output type ──────────────────────────────────────────────────────


def test_output_is_trending_field(calc):
    stats = [
        {
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "endorsement_window": 5,
            "endorsement_avg": 5.0,
            "replication_window": 5,
            "replication_avg": 5.0,
            "citation_window": 5,
            "citation_avg": 5.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert isinstance(result[0], TrendingField)
    assert hasattr(result[0], "domain_id")
    assert hasattr(result[0], "method_id")
    assert hasattr(result[0], "trending_score")
    assert hasattr(result[0], "endorsement_velocity")
    assert hasattr(result[0], "replication_velocity")
    assert hasattr(result[0], "citation_velocity")


def test_method_id_preserved(calc):
    stats = [
        {
            "domain_id": "polymer_science",
            "method_id": None,
            "endorsement_window": 5,
            "endorsement_avg": 5.0,
            "replication_window": 5,
            "replication_avg": 5.0,
            "citation_window": 5,
            "citation_avg": 5.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert result[0].method_id is None


def test_domain_id_in_output(calc):
    stats = [
        {
            "domain_id": "polymer_science",
            "method_id": "crystallinity_index",
            "endorsement_window": 5,
            "endorsement_avg": 5.0,
            "replication_window": 5,
            "replication_avg": 5.0,
            "citation_window": 5,
            "citation_avg": 5.0,
        },
    ]
    result = calc.get_trending_fields(stats)
    assert result[0].domain_id == "polymer_science"
    assert result[0].method_id == "crystallinity_index"
