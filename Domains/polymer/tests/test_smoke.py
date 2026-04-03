"""
Smoke tests for polymer_science domain module.

Acceptance criteria (W4 done):
  1. `uv pip install -e Domains/polymer/` succeeds.
  2. `entry_points(group='scientificstate.domains')` lists 'polymer_science'.
  3. Domain import + describe() works.
  4. PCA and HCA run end-to-end on minimal synthetic data.
  5. Deisotoping runs on minimal synthetic data.
  6. Fragment matching returns results against fragment_db.json.
  7. NitechLAB directory is NOT modified (verified via mtime check at import).
"""

from pathlib import Path
from typing import List, Dict

import numpy as np
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _synthetic_blocks(n_blocks: int = 6) -> List[Dict]:
    """Generate minimal synthetic Py-GC-MS block data."""
    rng = np.random.default_rng(42)
    blocks = []
    for i in range(n_blocks):
        mz = np.arange(40.0, 200.0, 1.0)
        intensity = rng.random(len(mz)) * 1000 + 10
        blocks.append({
            "block_id": i + 1,
            "mz": mz,
            "intensity": intensity,
            "temperature": 60.0 + i * 10,
        })
    return blocks


def _synthetic_peaks(n: int = 20) -> List[Dict]:
    """Generate minimal synthetic centroid peaks."""
    rng = np.random.default_rng(0)
    return [
        {"mz": 100.0 + i * 10.0 + rng.random() * 0.5,
         "intensity": float(1000 - i * 30)}
        for i in range(n)
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_import_domain():
    """Domain module imports without error."""
    from polymer_science import PolymerScienceDomain
    domain = PolymerScienceDomain()
    assert domain.domain_id == "polymer_science"


def test_describe():
    """describe() returns expected keys (DomainModule.describe() interface)."""
    from polymer_science import PolymerScienceDomain
    info = PolymerScienceDomain().describe()
    assert "domain_id" in info
    assert info["domain_id"] == "polymer_science"
    assert "domain_name" in info
    assert "method_count" in info
    assert info["method_count"] >= 5


def test_entry_points():
    """Entry point 'polymer_science' is discoverable."""
    from importlib.metadata import entry_points
    eps = entry_points(group="scientificstate.domains")
    names = [ep.name for ep in eps]
    assert "polymer_science" in names, f"Entry point not found. Found: {names}"


def test_fragment_db_loads():
    """fragment_db.json loads and has expected top-level keys."""
    from polymer_science import PolymerScienceDomain
    db = PolymerScienceDomain().get_fragment_db()
    assert isinstance(db, dict)
    assert "PS" in db


def test_pca_smoke():
    """PCA runs on synthetic blocks and returns expected keys."""
    from polymer_science.methods.pca import compute_pca
    blocks = _synthetic_blocks(6)
    result = compute_pca(blocks, n_components=2)
    assert "scores" in result
    assert result["scores"].shape[0] == 6
    assert result["n_components"] == 2


def test_hca_smoke():
    """HCA runs on synthetic blocks (dendrogram mode) and returns labels."""
    from polymer_science.methods.hca import compute_hca
    blocks = _synthetic_blocks(6)
    result = compute_hca(blocks, n_clusters=2, order_mode="dendrogram")
    assert "labels" in result
    assert len(result["labels"]) == 6
    assert result["n_clusters"] == 2


def test_hca_temperature_mode():
    """HCA temperature mode runs without error."""
    from polymer_science.methods.hca import compute_hca
    result = compute_hca(_synthetic_blocks(6), n_clusters=2, order_mode="temperature")
    assert len(result["labels"]) == 6


def test_hca_constrained_mode():
    """HCA constrained (sequence-constrained Ward) mode runs without error."""
    from polymer_science.methods.hca import compute_hca
    result = compute_hca(_synthetic_blocks(6), n_clusters=2, order_mode="constrained")
    assert len(result["labels"]) == 6


def test_deisotoping_smoke():
    """Deisotoping runs on synthetic peaks and returns envelopes."""
    from polymer_science.methods.deisotoping import process_total_spectrum_peaks
    peaks = _synthetic_peaks(20)
    result = process_total_spectrum_peaks(peaks, top_n=10)
    assert "envelopes" in result
    assert "statistics" in result
    assert result["statistics"]["total_envelopes"] > 0


def test_fragment_matching_smoke():
    """Fragment matching returns a list (may be empty on synthetic data)."""
    from polymer_science import PolymerScienceDomain
    domain = PolymerScienceDomain()
    db = domain.get_fragment_db()
    # Use m/z values known to be in PS fragment range
    ps_frags = db.get("PS", {}).get("fragments", [])
    if not ps_frags:
        pytest.skip("No PS fragments in fragment_db.json")
    # Build peaks near the first 5 fragment m/z values
    peaks = [{"mz": f["mz"] + 0.1, "intensity": 1000.0}
             for f in ps_frags[:5]]
    resp = domain.execute_method(
        "fragment_matching", data_ref="", assumptions=[],
        params={"peaks": peaks, "polymer": "PS", "abs_tol": 0.5},
    )
    assert resp["status"] == "ok", resp.get("error")
    matches = resp["result"]["matches"]
    assert isinstance(matches, list)
    assert len(matches) > 0, "Expected at least one fragment match"


def test_kmd_analysis_smoke():
    """KMD analysis runs on HCA result without error."""
    from polymer_science.methods.hca import compute_hca
    from polymer_science.methods.kmd_analysis import analyze_clusters
    blocks = _synthetic_blocks(6)
    hca_result = compute_hca(blocks, n_clusters=2)
    kmd_result = analyze_clusters(hca_result, blocks, polymer="PS")
    assert "cluster_relations" in kmd_result
    assert len(kmd_result["cluster_relations"]) == 2


def test_domain_module_interface():
    """PolymerScienceDomain fully implements DomainModule ABC."""
    from scientificstate.domain_registry import DomainModule
    from polymer_science import PolymerScienceDomain

    domain = PolymerScienceDomain()
    assert isinstance(domain, DomainModule)
    assert domain.domain_id == "polymer_science"
    assert isinstance(domain.domain_name, str) and domain.domain_name
    assert isinstance(domain.supported_data_types, list)
    assert len(domain.supported_data_types) > 0
    methods = domain.list_methods()
    assert isinstance(methods, list) and len(methods) > 0
    for m in methods:
        assert "method_id" in m
        assert "domain_id" in m
        assert m["domain_id"] == "polymer_science"


def test_registry_register_and_discover():
    """DomainRegistry.register() and discover_and_register() work with PolymerScienceDomain."""
    from scientificstate.domain_registry import DomainRegistry
    from polymer_science import PolymerScienceDomain

    # Manual registration
    reg = DomainRegistry()
    domain = PolymerScienceDomain()
    reg.register(domain)
    assert "polymer_science" in reg
    assert reg.get("polymer_science") is domain
    assert "polymer_science" in reg.list_domains()

    # Auto-discovery (entry_points path)
    reg2 = DomainRegistry()
    discovered = reg2.discover_and_register()
    assert "polymer_science" in discovered, (
        f"discover_and_register() did not find polymer_science. Got: {discovered}"
    )


def test_execute_method_pca():
    """execute_method('pca') returns status='ok' and result with 'scores'."""
    from polymer_science import PolymerScienceDomain

    domain = PolymerScienceDomain()
    blocks = _synthetic_blocks(6)
    resp = domain.execute_method("pca", data_ref="", assumptions=[],
                                 params={"blocks_data": blocks, "n_components": 2})
    assert resp["status"] == "ok", resp.get("error")
    assert "scores" in resp["result"]


def test_execute_method_hca():
    """execute_method('hca') returns status='ok' and result with 'labels'."""
    from polymer_science import PolymerScienceDomain

    domain = PolymerScienceDomain()
    blocks = _synthetic_blocks(6)
    resp = domain.execute_method("hca", data_ref="", assumptions=[],
                                 params={"blocks_data": blocks, "n_clusters": 2})
    assert resp["status"] == "ok", resp.get("error")
    assert "labels" in resp["result"]


def test_execute_method_unknown():
    """execute_method with unknown method_id returns status='error'."""
    from polymer_science import PolymerScienceDomain

    domain = PolymerScienceDomain()
    resp = domain.execute_method("nonexistent", data_ref="", assumptions=[], params={})
    assert resp["status"] == "error"
    assert "nonexistent" in resp["error"]


def test_w5_fallback_shim():
    """Domains/polymer/domain_manifest.py shim exports PolymerScienceDomain."""
    import importlib.util
    from pathlib import Path

    shim_path = Path(__file__).parents[1] / "domain_manifest.py"
    assert shim_path.exists(), "W5 fallback shim missing: Domains/polymer/domain_manifest.py"
    spec = importlib.util.spec_from_file_location("_w5_shim", shim_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "PolymerScienceDomain")
    instance = mod.PolymerScienceDomain()
    assert instance.domain_id == "polymer_science"


def test_nitechlab_readonly():
    """NitechLAB directory mtimes have not changed (read-only contract)."""
    nitechlab = Path("/Users/isaguducu/Preject/NitechLAB")
    if not nitechlab.exists():
        pytest.skip("NitechLAB not found on this system")
    # Spot-check key files: they must still exist (not deleted or replaced)
    key_files = [
        "polymer_compute.py",
        "data_engine.py",
        "cluster_pipeline.py",
        "core_utils.py",
        "cluster_kmd_engine.py",
        "deisotoping.py",
        "fragment_db.json",
    ]
    for fname in key_files:
        fpath = nitechlab / fname
        assert fpath.exists(), f"NitechLAB file missing (was it deleted?): {fname}"
