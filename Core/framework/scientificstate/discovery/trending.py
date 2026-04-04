"""Trending field calculator — scientific activity velocity.

Trending does NOT mean popular.  There are no view counts, clicks, or
download rankings.  Trending measures the *rate of scientific activity*
across three verifiable signals:

  trending_score = W_e * endorsement_velocity
                 + W_r * replication_velocity
                 + W_c * citation_velocity

Velocity = window_count / avg_count (rolling 6-month average).
A velocity > 1.0 means the field is accelerating.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TrendingField:
    """A domain/method pair with its trending score and velocity breakdown."""

    domain_id: str
    method_id: str | None
    trending_score: float
    endorsement_velocity: float
    replication_velocity: float
    citation_velocity: float


class TrendingCalculator:
    """Trending = scientific activity velocity, NOT popularity."""

    W_ENDORSEMENT = 0.40
    W_REPLICATION = 0.35
    W_CITATION = 0.25

    def get_trending_fields(
        self,
        field_stats: list[dict],
        window_days: int = 30,
        limit: int = 10,
    ) -> list[TrendingField]:
        """Calculate trending fields from activity snapshots.

        Args:
            field_stats: List of dicts, each with keys:
                - domain_id (str)
                - method_id (str | None)
                - endorsement_window (int) — count in current window
                - endorsement_avg (float) — rolling 6-month average
                - replication_window (int) — count in current window
                - replication_avg (float) — rolling 6-month average
                - citation_window (int) — count in current window
                - citation_avg (float) — rolling 6-month average
            window_days: Size of the current window in days (for context).
            limit: Maximum number of results to return.

        Returns:
            Sorted list of TrendingField (highest score first).
        """
        if not field_stats:
            return []

        results: list[TrendingField] = []

        for stats in field_stats:
            e_vel = self._velocity(
                stats.get("endorsement_window", 0),
                stats.get("endorsement_avg", 0.0),
            )
            r_vel = self._velocity(
                stats.get("replication_window", 0),
                stats.get("replication_avg", 0.0),
            )
            c_vel = self._velocity(
                stats.get("citation_window", 0),
                stats.get("citation_avg", 0.0),
            )

            score = (
                self.W_ENDORSEMENT * e_vel
                + self.W_REPLICATION * r_vel
                + self.W_CITATION * c_vel
            )

            results.append(
                TrendingField(
                    domain_id=stats.get("domain_id", ""),
                    method_id=stats.get("method_id"),
                    trending_score=round(score, 4),
                    endorsement_velocity=round(e_vel, 4),
                    replication_velocity=round(r_vel, 4),
                    citation_velocity=round(c_vel, 4),
                ),
            )

        results.sort(key=lambda t: (-t.trending_score, t.domain_id))
        return results[:limit]

    # ── helpers ───────────────────────────────────────────────────────

    def _velocity(self, window_count: int, avg_count: float) -> float:
        """Compute velocity: window_count / avg_count.

        - avg=0 and count>0 → large velocity (new field explosion) — capped at 10.0
        - Both 0 → velocity = 0.0
        """
        if window_count <= 0:
            return 0.0
        if avg_count <= 0.0:
            return min(float(window_count), 10.0)
        return round(window_count / avg_count, 4)
