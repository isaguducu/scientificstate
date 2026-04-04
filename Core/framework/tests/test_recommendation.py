"""Tests for gate-driven recommendation engine."""
from __future__ import annotations

import pytest

from scientificstate.discovery.recommendation import RecommendationEngine, RecommendedClaim


@pytest.fixture()
def engine():
    return RecommendationEngine()


# ── weight validation ─────────────────────────────────────────────────


def test_weights_sum_to_one(engine):
    total = (
        engine.W_DOMAIN_RELEVANCE
        + engine.W_METHOD_OVERLAP
        + engine.W_IMPACT
        + engine.W_RECENCY
    )
    assert abs(total - 1.0) < 1e-9


# ── domain relevance ─────────────────────────────────────────────────


def test_domain_relevance_subscribed(engine):
    assert engine._domain_relevance("polymer_science", ["polymer_science", "genomics"]) == 1.0


def test_domain_relevance_not_subscribed(engine):
    assert engine._domain_relevance("chemistry", ["polymer_science", "genomics"]) == 0.0


def test_domain_relevance_empty_subscriptions(engine):
    assert engine._domain_relevance("polymer_science", []) == 0.0


# ── method overlap ────────────────────────────────────────────────────


def test_method_overlap_match(engine):
    assert engine._method_overlap("dsc_tga_onset", ["dsc_tga_onset", "crystallinity_index"]) == 1.0


def test_method_overlap_no_match(engine):
    assert engine._method_overlap("kissinger", ["dsc_tga_onset"]) == 0.0


def test_method_overlap_none(engine):
    assert engine._method_overlap(None, ["dsc_tga_onset"]) == 0.0


def test_method_overlap_empty_methods(engine):
    assert engine._method_overlap("dsc_tga_onset", []) == 0.0


# ── recency score ────────────────────────────────────────────────────


def test_recency_day_zero(engine):
    assert engine._recency_score(0) == 1.0


def test_recency_max_days(engine):
    assert engine._recency_score(90) == 0.0


def test_recency_beyond_max(engine):
    assert engine._recency_score(120) == 0.0


def test_recency_midpoint(engine):
    score = engine._recency_score(45)
    assert abs(score - 0.5) < 0.01


def test_recency_negative_days(engine):
    assert engine._recency_score(-5) == 1.0


def test_recency_linear_decay(engine):
    s30 = engine._recency_score(30)
    s60 = engine._recency_score(60)
    # Linear: s30 should be roughly double s60
    assert abs(s30 - 2 * s60) < 0.02


# ── full recommendation ──────────────────────────────────────────────


def test_recommend_empty_candidates(engine):
    result = engine.recommend(
        researcher_orcid="0000-0001-0000-0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=[],
    )
    assert result == []


def test_recommend_scores_four_components(engine):
    candidates = [
        {
            "claim_id": "c1",
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "impact_score": 0.8,
            "days_since_endorsement": 10,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=candidates,
    )
    assert len(result) == 1
    rec = result[0]
    assert rec.claim_id == "c1"
    assert rec.domain_relevance == 1.0
    assert rec.method_overlap == 1.0
    assert rec.impact == 0.8
    assert rec.recency > 0.8  # 10 days out of 90 → ~0.89


def test_recommend_perfect_match(engine):
    candidates = [
        {
            "claim_id": "perfect",
            "domain_id": "genomics",
            "method_id": "variant_calling",
            "impact_score": 1.0,
            "days_since_endorsement": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["genomics"],
        past_methods=["variant_calling"],
        candidate_claims=candidates,
    )
    assert len(result) == 1
    assert result[0].score == 1.0


def test_recommend_no_match(engine):
    candidates = [
        {
            "claim_id": "nomatch",
            "domain_id": "chemistry",
            "method_id": "spectrometry",
            "impact_score": 0.0,
            "days_since_endorsement": 100,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=candidates,
    )
    assert len(result) == 1
    assert result[0].score == 0.0


def test_recommend_sorting_by_score(engine):
    candidates = [
        {
            "claim_id": "low",
            "domain_id": "chemistry",
            "method_id": None,
            "impact_score": 0.1,
            "days_since_endorsement": 80,
        },
        {
            "claim_id": "high",
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "impact_score": 0.9,
            "days_since_endorsement": 5,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=candidates,
    )
    assert result[0].claim_id == "high"
    assert result[1].claim_id == "low"
    assert result[0].score > result[1].score


def test_recommend_limit(engine):
    candidates = [
        {
            "claim_id": f"c{i}",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": i,
        }
        for i in range(30)
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=[],
        candidate_claims=candidates,
        limit=5,
    )
    assert len(result) == 5


def test_recommend_default_limit(engine):
    candidates = [
        {
            "claim_id": f"c{i}",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": i,
        }
        for i in range(25)
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=[],
        candidate_claims=candidates,
    )
    assert len(result) == 20  # default limit


# ── NO implicit signals ──────────────────────────────────────────────


def test_no_view_count_field(engine):
    """Verify that view_count is NOT used in scoring."""
    candidates = [
        {
            "claim_id": "c1",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": 10,
            "view_count": 999999,
        },
        {
            "claim_id": "c2",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": 10,
            "view_count": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=[],
        candidate_claims=candidates,
    )
    # Both should have the same score — view_count is ignored
    assert result[0].score == result[1].score


def test_no_click_field(engine):
    """Verify that click_count is NOT used in scoring."""
    candidates = [
        {
            "claim_id": "a",
            "domain_id": "genomics",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": 10,
            "click_count": 10000,
        },
        {
            "claim_id": "b",
            "domain_id": "genomics",
            "method_id": None,
            "impact_score": 0.5,
            "days_since_endorsement": 10,
            "click_count": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["genomics"],
        past_methods=[],
        candidate_claims=candidates,
    )
    assert result[0].score == result[1].score


def test_no_dwell_time_field(engine):
    """Verify that dwell_time is NOT used in scoring."""
    candidates = [
        {
            "claim_id": "x",
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "impact_score": 0.7,
            "days_since_endorsement": 5,
            "dwell_time_seconds": 3600,
        },
        {
            "claim_id": "y",
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "impact_score": 0.7,
            "days_since_endorsement": 5,
            "dwell_time_seconds": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=candidates,
    )
    assert result[0].score == result[1].score


# ── output type ──────────────────────────────────────────────────────


def test_output_is_recommended_claim(engine):
    candidates = [
        {
            "claim_id": "typed",
            "domain_id": "polymer_science",
            "method_id": "dsc_tga_onset",
            "impact_score": 0.5,
            "days_since_endorsement": 10,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=["dsc_tga_onset"],
        candidate_claims=candidates,
    )
    assert isinstance(result[0], RecommendedClaim)
    assert hasattr(result[0], "score")
    assert hasattr(result[0], "domain_relevance")
    assert hasattr(result[0], "method_overlap")
    assert hasattr(result[0], "impact")
    assert hasattr(result[0], "recency")


# ── impact clamping ──────────────────────────────────────────────────


def test_impact_clamped_to_one(engine):
    candidates = [
        {
            "claim_id": "over",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": 5.0,
            "days_since_endorsement": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=[],
        candidate_claims=candidates,
    )
    assert result[0].impact == 1.0


def test_impact_clamped_to_zero(engine):
    candidates = [
        {
            "claim_id": "under",
            "domain_id": "polymer_science",
            "method_id": None,
            "impact_score": -1.0,
            "days_since_endorsement": 0,
        },
    ]
    result = engine.recommend(
        researcher_orcid="0000",
        subscribed_domains=["polymer_science"],
        past_methods=[],
        candidate_claims=candidates,
    )
    assert result[0].impact == 0.0
