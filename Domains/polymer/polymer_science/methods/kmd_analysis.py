"""
kmd_analysis.py — KMD homolog series assignment per HCA cluster.

Extracted from NitechLAB/cluster_kmd_engine.py.
Changes from source:
  - Removed file-system output (CSV / JSON writing).
  - Kept all scientific logic verbatim.
  - Module header updated; import paths unchanged (no upstream imports).
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# POLYMER REFERENCE DATA
# ════════════════════════════════════════════════════════════════

POLYMER_REPEAT_MASSES: Dict[str, float] = {
    "PS":   104.0626,  # C8H8
    "PAN":   53.0266,  # C3H3N
    "PMMA": 100.0524,  # C5H8O2
    "PEG":   44.0262,  # C2H4O
}

POLYMER_NOMINAL_MASSES: Dict[str, int] = {
    "PS":  104,
    "PAN":  53,
    "PMMA": 100,
    "PEG":  44,
}


# ════════════════════════════════════════════════════════════════
# KMD CALCULATION
# ════════════════════════════════════════════════════════════════

def compute_kmd(mz: float, repeat_mass: float, nominal_mass: int) -> Tuple[float, float]:
    """
    Compute Kendrick Mass (KM) and Kendrick Mass Defect (KMD).

    KM  = mz × (nominal_mass / repeat_mass)
    KMD = round(KM) − KM

    Returns:
        (km, kmd)
    """
    km = mz * (nominal_mass / repeat_mass)
    kmd = round(km) - km
    return km, kmd


def assign_kmd_series(
    mz_list: List[float],
    polymer: str = "PS",
    kmd_tol: float = 0.02,
) -> Dict[int, List[float]]:
    """
    Assign m/z values to KMD homolog series for a given polymer.

    Peaks with KMD values within *kmd_tol* of each other belong to
    the same homolog series (differ by integer multiples of the repeat unit).

    Args:
        mz_list: List of m/z values.
        polymer: Polymer type (PS, PAN, PMMA, PEG).
        kmd_tol: KMD tolerance for series grouping.

    Returns:
        Dict mapping series_id → list of m/z values in that series.
    """
    repeat_mass = POLYMER_REPEAT_MASSES.get(polymer.upper())
    nominal_mass = POLYMER_NOMINAL_MASSES.get(polymer.upper())

    if repeat_mass is None or nominal_mass is None:
        logger.warning("Unknown polymer %r — KMD assignment skipped.", polymer)
        return {}

    kmd_values = []
    for mz in mz_list:
        _, kmd = compute_kmd(mz, repeat_mass, nominal_mass)
        kmd_values.append(kmd)

    series: Dict[int, List[float]] = {}
    series_kmd_ref: Dict[int, float] = {}
    next_series_id = 0

    for mz, kmd in sorted(zip(mz_list, kmd_values), key=lambda x: x[1]):
        matched = False
        for sid, ref_kmd in series_kmd_ref.items():
            if abs(kmd - ref_kmd) <= kmd_tol:
                series[sid].append(mz)
                matched = True
                break
        if not matched:
            series[next_series_id] = [mz]
            series_kmd_ref[next_series_id] = kmd
            next_series_id += 1

    return series


def compute_series_enrichment(
    cluster_mz: List[float],
    background_mz: List[float],
    repeat_mass: float,
    nominal_mass: int,
    kmd_tol: float = 0.02,
) -> Dict[str, Any]:
    """
    Fisher's exact test for KMD series enrichment in a cluster vs background.

    Returns:
        Dict with p_value, effect_size (odds ratio), and dominant_series_kmd.
    """
    try:
        from scipy.stats import fisher_exact
    except ImportError:
        return {"p_value": None, "effect_size": None, "dominant_series_kmd": None}

    if not cluster_mz or not background_mz:
        return {"p_value": None, "effect_size": None, "dominant_series_kmd": None}

    def kmd_round(mz: float) -> float:
        _, kmd = compute_kmd(mz, repeat_mass, nominal_mass)
        return round(kmd / kmd_tol) * kmd_tol  # discretize

    cluster_kmds = [kmd_round(m) for m in cluster_mz]
    bg_kmds = [kmd_round(m) for m in background_mz]

    if not cluster_kmds:
        return {"p_value": None, "effect_size": None, "dominant_series_kmd": None}

    dominant_kmd = Counter(cluster_kmds).most_common(1)[0][0]

    in_cluster_in_series = sum(1 for k in cluster_kmds if k == dominant_kmd)
    in_cluster_not_series = len(cluster_kmds) - in_cluster_in_series
    in_bg_in_series = sum(1 for k in bg_kmds if k == dominant_kmd)
    in_bg_not_series = len(bg_kmds) - in_bg_in_series

    contingency = [[in_cluster_in_series, in_cluster_not_series],
                   [in_bg_in_series, in_bg_not_series]]

    try:
        odds_ratio, p_value = fisher_exact(contingency, alternative='greater')
    except Exception:
        odds_ratio, p_value = None, None

    return {
        "p_value": float(p_value) if p_value is not None else None,
        "effect_size": float(odds_ratio) if odds_ratio is not None else None,
        "dominant_series_kmd": float(dominant_kmd),
    }


def infer_polymer_from_series(
    series: Dict[int, List[float]],
    kmd_tol: float = 0.02,
) -> Optional[str]:
    """
    Infer the most likely polymer type from KMD series spacing.

    Returns the polymer name with the best Δm/z match, or None.
    """
    if not series:
        return None

    best_polymer: Optional[str] = None
    best_score = 0.0

    for polymer, repeat_mass in POLYMER_REPEAT_MASSES.items():
        score = 0.0
        for sid, mz_list in series.items():
            if len(mz_list) < 2:
                continue
            sorted_mz = sorted(mz_list)
            diffs = [sorted_mz[i + 1] - sorted_mz[i] for i in range(len(sorted_mz) - 1)]
            for diff in diffs:
                # Compare to repeat_mass and its fractions (charge states z=1,2)
                for n in range(1, 4):
                    if abs(diff - repeat_mass / n) < kmd_tol * 5:
                        score += 1.0 / n
                        break

        if score > best_score:
            best_score = score
            best_polymer = polymer

    return best_polymer


# ════════════════════════════════════════════════════════════════
# CLUSTER → KMD RELATION (top-level)
# ════════════════════════════════════════════════════════════════

def analyze_clusters(
    hca_result: Dict,
    blocks_data: List[Dict],
    polymer: str = "PS",
    kmd_tol: float = 0.02,
    mz_min: float = 40.0,
    mz_max: float = 1200.0,
) -> Dict:
    """
    Quantitatively link HCA clusters to KMD homolog series.

    For each cluster:
      1. Collect all m/z values from member blocks.
      2. Assign KMD series.
      3. Compute series purity and enrichment vs. background.
      4. Infer probable polymer type.

    Args:
        hca_result: Output of compute_hca().
        blocks_data: Original block data list.
        polymer: Candidate polymer for KMD calculation.
        kmd_tol: KMD grouping tolerance.
        mz_min, mz_max: m/z filter range.

    Returns:
        Dict with per-cluster analysis results.
    """
    cluster_summary = hca_result.get("cluster_summary", {})
    n_clusters = hca_result.get("n_clusters", 0)

    block_map: Dict[int, Dict] = {b["block_id"]: b for b in blocks_data}

    # Collect all background m/z
    all_mz: List[float] = []
    for blk in blocks_data:
        for mz in blk.get("mz", []):
            if mz_min <= mz <= mz_max:
                all_mz.append(float(mz))

    repeat_mass = POLYMER_REPEAT_MASSES.get(polymer.upper(), 104.0626)
    nominal_mass = POLYMER_NOMINAL_MASSES.get(polymer.upper(), 104)

    cluster_relations: List[Dict] = []

    for cid in range(1, n_clusters + 1):
        cid_str = str(cid)
        csummary = cluster_summary.get(cid_str, {})
        block_ids = csummary.get("block_ids", [])

        # Collect cluster m/z
        cluster_mz: List[float] = []
        for bid in block_ids:
            blk = block_map.get(bid)
            if blk is None:
                continue
            for mz in blk.get("mz", []):
                if mz_min <= mz <= mz_max:
                    cluster_mz.append(float(mz))

        if not cluster_mz:
            cluster_relations.append({
                "cluster_id": cid,
                "block_ids": block_ids,
                "temp_range": [csummary.get("temp_min", 0), csummary.get("temp_max", 0)],
                "n_peaks": 0,
                "kmd_series": {},
                "dominant_series_id": None,
                "series_purity": 0.0,
                "enrichment": {},
                "inferred_polymer": None,
            })
            continue

        kmd_series = assign_kmd_series(cluster_mz, polymer=polymer, kmd_tol=kmd_tol)

        # Dominant series
        dominant_sid: Optional[int] = None
        dominant_count = 0
        for sid, mzs in kmd_series.items():
            if len(mzs) > dominant_count:
                dominant_count = len(mzs)
                dominant_sid = sid

        series_purity = dominant_count / len(cluster_mz) if cluster_mz else 0.0

        enrichment = compute_series_enrichment(
            cluster_mz, all_mz, repeat_mass, nominal_mass, kmd_tol
        )

        inferred = infer_polymer_from_series(kmd_series, kmd_tol=kmd_tol)

        cluster_relations.append({
            "cluster_id": cid,
            "block_ids": block_ids,
            "temp_range": [
                csummary.get("temp_min", 0),
                csummary.get("temp_max", 0),
            ],
            "n_peaks": len(cluster_mz),
            "kmd_series": {str(k): v for k, v in kmd_series.items()},
            "dominant_series_id": dominant_sid,
            "series_purity": round(series_purity, 4),
            "enrichment": enrichment,
            "inferred_polymer": inferred,
        })

    return {
        "polymer": polymer,
        "n_clusters": n_clusters,
        "cluster_relations": cluster_relations,
        "assumptions": {
            "repeat_mass": repeat_mass,
            "nominal_mass": nominal_mass,
            "kmd_tol": kmd_tol,
            "mz_range": [mz_min, mz_max],
        },
    }
