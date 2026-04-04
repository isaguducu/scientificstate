"""Deterministic impact score calculator.

Impact is NOT a popularity metric.  There are no likes, upvotes, or shares.
The score is a weighted function of four verifiable scientific signals:

  score = W_r * replication_ratio
        + W_c * citation_depth
        + W_g * gate_completeness
        + W_d * institutional_diversity

Each component is normalized to [0, 1].  Weights sum to 1.0.
"""
from __future__ import annotations


class ImpactCalculator:
    """Deterministic, gate-driven impact scoring."""

    W_REPLICATION = 0.35
    W_CITATION = 0.25
    W_GATE = 0.25
    W_DIVERSITY = 0.15

    MAX_CITATION_NORM = 50

    def calculate(
        self,
        claim_id: str,
        replication_count: int,
        total_replication_requests: int,
        citation_count: int,
        passed_gates: int,
        total_gates: int,
        unique_institutions: int,
    ) -> dict:
        """Calculate the impact score for an endorsed claim.

        Args:
            claim_id: The endorsed claim identifier.
            replication_count: Number of successful replications.
            total_replication_requests: Total replication requests made.
            citation_count: Number of times this claim is cited.
            passed_gates: Number of verification gates passed.
            total_gates: Total verification gates for this claim type.
            unique_institutions: Number of distinct institutions involved.

        Returns:
            Dict with ``score``, ``breakdown``, and ``weights``.
        """
        replication_ratio = (
            replication_count / max(total_replication_requests, 1)
            if total_replication_requests > 0
            else 0.0
        )
        citation_depth = min(citation_count / self.MAX_CITATION_NORM, 1.0)
        gate_completeness = passed_gates / max(total_gates, 1)
        institutional_diversity = min(unique_institutions / 3, 1.0)

        score = (
            self.W_REPLICATION * replication_ratio
            + self.W_CITATION * citation_depth
            + self.W_GATE * gate_completeness
            + self.W_DIVERSITY * institutional_diversity
        )

        return {
            "claim_id": claim_id,
            "score": round(score, 3),
            "breakdown": {
                "replication_ratio": round(replication_ratio, 3),
                "citation_depth": round(citation_depth, 3),
                "gate_completeness": round(gate_completeness, 3),
                "institutional_diversity": round(institutional_diversity, 3),
            },
            "weights": {
                "replication": self.W_REPLICATION,
                "citation": self.W_CITATION,
                "gate": self.W_GATE,
                "diversity": self.W_DIVERSITY,
            },
        }
