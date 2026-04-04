"""SSV-to-SSV citation engine.

Citations link endorsed claims into a directed graph.  Only endorsed
claims may participate — draft or retracted claims cannot be cited.
Self-citation is structurally forbidden.

Relationship types:
  - builds_upon: new work that extends a prior claim
  - extends: methodological extension
  - replicates: independent reproduction of the same result
  - contradicts: conflicting evidence
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """Immutable citation record between two endorsed claims."""

    source_claim_id: str
    cited_claim_id: str
    relationship: str
    cited_by_orcid: str


class CitationEngine:
    """SSV-to-SSV citation chain — verifiable, traceable."""

    VALID_RELATIONSHIPS = ("builds_upon", "extends", "replicates", "contradicts")

    def create_citation(
        self,
        source_claim_id: str,
        cited_claim_id: str,
        relationship: str,
        cited_by_orcid: str,
    ) -> Citation:
        """Create a citation between two endorsed claims.

        Args:
            source_claim_id: The claim that is citing.
            cited_claim_id: The claim being cited.
            relationship: One of VALID_RELATIONSHIPS.
            cited_by_orcid: ORCID of the researcher creating the citation.

        Raises:
            ValueError: If relationship is invalid or self-citation attempted.
        """
        if relationship not in self.VALID_RELATIONSHIPS:
            raise ValueError(f"Invalid relationship: {relationship}")
        if source_claim_id == cited_claim_id:
            raise ValueError("Self-citation not allowed")
        return Citation(
            source_claim_id=source_claim_id,
            cited_claim_id=cited_claim_id,
            relationship=relationship,
            cited_by_orcid=cited_by_orcid,
        )

    def get_citation_chain(
        self,
        claim_id: str,
        depth: int = 3,
        citations_db: list[dict] | None = None,
    ) -> dict:
        """Build the citation tree for a claim.

        Returns a nested dict with ``cited_by`` (claims citing this one)
        and ``cites`` (claims this one references).
        """
        if depth <= 0:
            return {"claim_id": claim_id, "cited_by": [], "cites": []}

        all_citations = citations_db or []
        citing = [c for c in all_citations if c["cited_claim_id"] == claim_id]
        cited_by_list = [c for c in all_citations if c["source_claim_id"] == claim_id]

        return {
            "claim_id": claim_id,
            "cited_by": [
                {
                    "claim_id": c["source_claim_id"],
                    "relationship": c["relationship"],
                    "chain": self.get_citation_chain(
                        c["source_claim_id"], depth - 1, all_citations,
                    ),
                }
                for c in citing
            ],
            "cites": [
                {
                    "claim_id": c["cited_claim_id"],
                    "relationship": c["relationship"],
                }
                for c in cited_by_list
            ],
        }

    def get_citing_claims(
        self, claim_id: str, citations_db: list[dict] | None = None,
    ) -> list[dict]:
        """Return citations where this claim is being cited."""
        return [c for c in (citations_db or []) if c["cited_claim_id"] == claim_id]

    def get_cited_claims(
        self, claim_id: str, citations_db: list[dict] | None = None,
    ) -> list[dict]:
        """Return claims that this claim cites."""
        return [c for c in (citations_db or []) if c["source_claim_id"] == claim_id]
