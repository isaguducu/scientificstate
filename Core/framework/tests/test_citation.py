"""Tests for SSV citation engine."""
from __future__ import annotations

import pytest

from scientificstate.discovery.citation import Citation, CitationEngine


@pytest.fixture()
def engine():
    return CitationEngine()


# ── create_citation ────────────────────────────────────────────────────


def test_create_builds_upon(engine):
    c = engine.create_citation("claim-A", "claim-B", "builds_upon", "0000-0001")
    assert isinstance(c, Citation)
    assert c.source_claim_id == "claim-A"
    assert c.cited_claim_id == "claim-B"
    assert c.relationship == "builds_upon"
    assert c.cited_by_orcid == "0000-0001"


def test_create_extends(engine):
    c = engine.create_citation("X", "Y", "extends", "0000-0002")
    assert c.relationship == "extends"


def test_create_replicates(engine):
    c = engine.create_citation("X", "Y", "replicates", "0000-0003")
    assert c.relationship == "replicates"


def test_create_contradicts(engine):
    c = engine.create_citation("X", "Y", "contradicts", "0000-0004")
    assert c.relationship == "contradicts"


def test_all_valid_relationships(engine):
    for rel in CitationEngine.VALID_RELATIONSHIPS:
        c = engine.create_citation("A", "B", rel, "orcid")
        assert c.relationship == rel


def test_invalid_relationship_raises(engine):
    with pytest.raises(ValueError, match="Invalid relationship"):
        engine.create_citation("A", "B", "likes", "orcid")


def test_self_citation_raises(engine):
    with pytest.raises(ValueError, match="Self-citation"):
        engine.create_citation("same", "same", "builds_upon", "orcid")


def test_citation_is_frozen(engine):
    c = engine.create_citation("A", "B", "extends", "orcid")
    with pytest.raises(AttributeError):
        c.relationship = "replicates"  # type: ignore[misc]


# ── get_citation_chain ─────────────────────────────────────────────────


def _sample_db():
    return [
        {"source_claim_id": "B", "cited_claim_id": "A", "relationship": "builds_upon"},
        {"source_claim_id": "C", "cited_claim_id": "A", "relationship": "extends"},
        {"source_claim_id": "D", "cited_claim_id": "B", "relationship": "replicates"},
    ]


def test_chain_root(engine):
    chain = engine.get_citation_chain("A", depth=2, citations_db=_sample_db())
    assert chain["claim_id"] == "A"
    assert len(chain["cited_by"]) == 2
    cited_ids = {c["claim_id"] for c in chain["cited_by"]}
    assert cited_ids == {"B", "C"}


def test_chain_depth_1(engine):
    chain = engine.get_citation_chain("A", depth=1, citations_db=_sample_db())
    # depth=1: B and C listed but their sub-chains have empty cited_by
    for child in chain["cited_by"]:
        assert child["chain"]["cited_by"] == []


def test_chain_depth_0(engine):
    chain = engine.get_citation_chain("A", depth=0, citations_db=_sample_db())
    assert chain["cited_by"] == []
    assert chain["cites"] == []


def test_chain_nested(engine):
    chain = engine.get_citation_chain("A", depth=3, citations_db=_sample_db())
    b_child = next(c for c in chain["cited_by"] if c["claim_id"] == "B")
    assert len(b_child["chain"]["cited_by"]) == 1
    assert b_child["chain"]["cited_by"][0]["claim_id"] == "D"


def test_chain_no_citations(engine):
    chain = engine.get_citation_chain("lonely", depth=3, citations_db=[])
    assert chain["cited_by"] == []
    assert chain["cites"] == []


def test_chain_cites_direction(engine):
    db = [{"source_claim_id": "X", "cited_claim_id": "Y", "relationship": "extends"}]
    chain = engine.get_citation_chain("X", depth=1, citations_db=db)
    assert len(chain["cites"]) == 1
    assert chain["cites"][0]["claim_id"] == "Y"


# ── get_citing_claims / get_cited_claims ───────────────────────────────


def test_get_citing_claims(engine):
    result = engine.get_citing_claims("A", _sample_db())
    assert len(result) == 2


def test_get_cited_claims(engine):
    result = engine.get_cited_claims("B", _sample_db())
    assert len(result) == 1
    assert result[0]["cited_claim_id"] == "A"


def test_get_citing_empty(engine):
    assert engine.get_citing_claims("Z", _sample_db()) == []


def test_get_cited_empty(engine):
    assert engine.get_cited_claims("Z", _sample_db()) == []
