"""Tests for auto_detect module — file extension → domain suggestion."""
from __future__ import annotations

from scientificstate.modules.auto_detect import suggest_domains


def test_csv_suggests_polymer():
    """CSV files should suggest polymer_science."""
    result = suggest_domains("data.csv")
    assert "polymer_science" in result["suggested_domains"]


def test_qasm_suggests_quantum():
    """QASM files should suggest quantum_circuit."""
    result = suggest_domains("circuit.qasm")
    assert "quantum_circuit" in result["suggested_domains"]


def test_fasta_suggests_genomics():
    """FASTA files should suggest genomics."""
    result = suggest_domains("sequence.fasta")
    assert "genomics" in result["suggested_domains"]


def test_pdb_suggests_structural_biology():
    """PDB files should suggest structural_biology."""
    result = suggest_domains("protein.pdb")
    assert "structural_biology" in result["suggested_domains"]


def test_unknown_extension_returns_empty():
    """Unknown extension should return empty list."""
    result = suggest_domains("unknown.xyz")
    assert result["suggested_domains"] == []


def test_confidence_high_for_single_match():
    """Single matching domain → high confidence."""
    result = suggest_domains("circuit.qasm")
    assert result["confidence"] == "high"


def test_confidence_low_for_no_match():
    """No matching domain → low confidence."""
    result = suggest_domains("file.unknown_ext")
    assert result["confidence"] == "low"


def test_dotless_filename():
    """File without extension → empty suggestions."""
    result = suggest_domains("Makefile")
    assert result["suggested_domains"] == []
    assert result["confidence"] == "low"


def test_full_path():
    """Full path should use only the final extension."""
    result = suggest_domains("/home/user/data/experiment_results.csv")
    assert "polymer_science" in result["suggested_domains"]


def test_mzml_suggests_polymer():
    """mzML files should suggest polymer_science."""
    result = suggest_domains("spectrum.mzml")
    assert "polymer_science" in result["suggested_domains"]
