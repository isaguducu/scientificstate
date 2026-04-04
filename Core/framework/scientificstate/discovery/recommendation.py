"""Gate-driven recommendation engine.

This is NOT collaborative filtering.  No implicit signals (view count,
click-through, dwell time) are used.  Recommendations are based on four
explicit, verifiable dimensions:

  score = W_domain * domain_relevance
        + W_method * method_overlap
        + W_impact * impact_score
        + W_recency * recency_score

Each component is 0.0 or 1.0 (binary match) except impact (continuous
[0,1]) and recency (linear decay).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendedClaim:
    """A claim with its recommendation score and breakdown."""

    claim_id: str
    score: float
    domain_relevance: float
    method_overlap: float
    impact: float
    recency: float


class RecommendationEngine:
    """Gate-driven recommendation — explicit signals only."""

    W_DOMAIN_RELEVANCE = 0.30
    W_METHOD_OVERLAP = 0.25
    W_IMPACT = 0.25
    W_RECENCY = 0.20

    MAX_RECENCY_DAYS = 90

    def recommend(
        self,
        researcher_orcid: str,
        subscribed_domains: list[str],
        past_methods: list[str],
        candidate_claims: list[dict],
        limit: int = 20,
    ) -> list[RecommendedClaim]:
        """Score and rank candidate claims for a researcher.

        Args:
            researcher_orcid: The researcher's ORCID (for audit trail).
            subscribed_domains: Domain IDs the researcher subscribes to.
            past_methods: Method IDs the researcher has used before.
            candidate_claims: List of dicts, each with keys:
                - claim_id (str)
                - domain_id (str)
                - method_id (str | None)
                - impact_score (float, 0-1)
                - days_since_endorsement (int)
            limit: Maximum number of results to return.

        Returns:
            Sorted list of RecommendedClaim (highest score first).
        """
        if not candidate_claims:
            return []

        scored: list[RecommendedClaim] = []

        for claim in candidate_claims:
            domain_rel = self._domain_relevance(
                claim.get("domain_id", ""), subscribed_domains,
            )
            method_ovl = self._method_overlap(
                claim.get("method_id"), past_methods,
            )
            impact = min(max(claim.get("impact_score", 0.0), 0.0), 1.0)
            recency = self._recency_score(
                claim.get("days_since_endorsement", self.MAX_RECENCY_DAYS),
            )

            total = (
                self.W_DOMAIN_RELEVANCE * domain_rel
                + self.W_METHOD_OVERLAP * method_ovl
                + self.W_IMPACT * impact
                + self.W_RECENCY * recency
            )

            scored.append(
                RecommendedClaim(
                    claim_id=claim["claim_id"],
                    score=round(total, 4),
                    domain_relevance=domain_rel,
                    method_overlap=method_ovl,
                    impact=round(impact, 4),
                    recency=round(recency, 4),
                ),
            )

        scored.sort(key=lambda r: (-r.score, r.claim_id))
        return scored[:limit]

    # ── component helpers ─────────────────────────────────────────────

    def _domain_relevance(
        self, claim_domain: str, subscribed: list[str],
    ) -> float:
        """1.0 if claim domain in subscribed, else 0.0."""
        return 1.0 if claim_domain in subscribed else 0.0

    def _method_overlap(
        self, claim_method: str | None, past_methods: list[str],
    ) -> float:
        """1.0 if claim method in past methods, else 0.0."""
        if claim_method is None:
            return 0.0
        return 1.0 if claim_method in past_methods else 0.0

    def _recency_score(self, days_since: int) -> float:
        """Linear decay: 1.0 at day 0, 0.0 at MAX_RECENCY_DAYS."""
        if days_since <= 0:
            return 1.0
        if days_since >= self.MAX_RECENCY_DAYS:
            return 0.0
        return round(1.0 - (days_since / self.MAX_RECENCY_DAYS), 4)
