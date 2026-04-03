"""
pipeline.py — Polymer analysis preprocessing pipeline.

Extracted from NitechLAB/cluster_pipeline.py.
Changes from source:
  - Removed YAML protocol_config loading (file-system path coupling).
  - Removed CSV output / results directory writing.
  - Removed _get_config_or_default (caller supplies params directly).
  - Updated import paths (core_utils → polymer_science.utils).
  - All scientific logic preserved verbatim.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# TIME AXIS MODE
# ════════════════════════════════════════════════════════════════

class TimeAxisMode:
    """Time axis processing mode: raw_time or processed."""
    RAW_TIME = "raw_time"
    PROCESSED = "processed"

    _FORBIDDEN_RAW = frozenset([
        "shift", "interpolation", "warping", "alignment",
        "time_shift", "retention_time_correction",
    ])

    @classmethod
    def validate_raw_time(cls, transformations: List[str]) -> None:
        """Raise ValueError if any transformation is forbidden in raw_time mode."""
        violations = cls._FORBIDDEN_RAW.intersection(
            t.lower().strip() for t in transformations
        )
        if violations:
            raise ValueError(
                f"[RAW-TIME LOCK] Forbidden transformations: {sorted(violations)}. "
                "Time axis must not be modified in raw_time mode."
            )


# ════════════════════════════════════════════════════════════════
# MATRIX CONSTRUCTION
# ════════════════════════════════════════════════════════════════

def build_mz_matrix(
    blocks_data: List[Dict],
    mz_min: float = 40.0,
    mz_max: float = 1200.0,
    mz_bin: float = 1.0,
    normalize_tic: bool = True,
) -> Tuple[np.ndarray, np.ndarray, List[int], List[float]]:
    """
    Build (n_blocks × n_bins) m/z matrix from block data.

    Returns:
        (matrix, mz_bins, block_ids, temperatures)
    """
    mz_bins = np.arange(mz_min, mz_max + mz_bin, mz_bin)
    n_bins = len(mz_bins)

    block_ids: List[int] = []
    temperatures: List[float] = []
    rows: List[np.ndarray] = []

    for blk in blocks_data:
        block_ids.append(blk["block_id"])
        temperatures.append(blk.get("temperature", blk["block_id"] * 10 + 50))

        row = np.zeros(n_bins)
        mz_arr = blk["mz"]
        int_arr = blk["intensity"]

        for mz, intensity in zip(mz_arr, int_arr):
            if mz_min <= mz <= mz_max:
                bin_idx = min(int(round((mz - mz_min) / mz_bin)), n_bins - 1)
                row[bin_idx] += intensity

        if normalize_tic:
            total = row.sum()
            if total > 0:
                row = row / total

        rows.append(row)

    return np.array(rows), mz_bins, block_ids, temperatures


def scale_matrix(matrix: np.ndarray) -> Tuple[np.ndarray, Any]:
    """Apply StandardScaler (μ=0, σ=1) — JMP correlation-based PCA compatible."""
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    scaled = np.nan_to_num(scaled, nan=0.0)
    return scaled, scaler


# ════════════════════════════════════════════════════════════════
# POLYMER-AWARE m/z WEIGHTING (optional, hypothesis-driven)
# ════════════════════════════════════════════════════════════════

def build_polymer_weight_vector(
    polymer: str,
    mz_bins: np.ndarray,
    fragment_db: Optional[Dict] = None,
    sigma_da: float = 2.0,
    boost_factor: float = 3.0,
) -> Tuple[np.ndarray, Dict]:
    """
    Build polymer-specific m/z weight vector using Gaussian weighting
    around known fragment m/z positions.

    Args:
        polymer: Polymer type (PS, PAN, PMMA, PEG)
        mz_bins: m/z bin centers
        fragment_db: Pre-loaded fragment_db dict (or None → uniform weights)
        sigma_da: Gaussian width in Da
        boost_factor: Maximum weight multiplier at fragment peaks

    Returns:
        (weights, meta)
    """
    weights = np.ones(len(mz_bins))
    meta: Dict[str, Any] = {
        "polymer": polymer.upper(),
        "sigma_da": sigma_da,
        "boost_factor": boost_factor,
        "n_fragments_used": 0,
        "fragment_mz_list": [],
        "repeat_unit_mass": None,
    }

    if fragment_db is None:
        meta["warning"] = "No fragment_db provided — uniform weights used."
        return weights, meta

    poly_data = fragment_db.get(polymer.upper(), {})
    fragments = poly_data.get("fragments", [])

    if not fragments:
        meta["warning"] = f"No fragments found for {polymer!r}."
        return weights, meta

    frag_mz = np.array([f["mz"] for f in fragments])
    meta["n_fragments_used"] = len(frag_mz)
    meta["fragment_mz_list"] = sorted(frag_mz.tolist())

    for fmz in frag_mz:
        gaussian = np.exp(-0.5 * ((mz_bins - fmz) / sigma_da) ** 2)
        weights += (boost_factor - 1.0) * gaussian

    repeat_mass = poly_data.get("exact_mass")
    if repeat_mass:
        meta["repeat_unit_mass"] = repeat_mass
        for n in range(1, 6):
            gaussian = np.exp(-0.5 * ((mz_bins - n * repeat_mass) / sigma_da) ** 2)
            weights += (boost_factor - 1.0) * 0.5 * gaussian

    return weights, meta


def apply_polymer_weighting(matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Apply polymer-specific m/z weights to a binned matrix."""
    return matrix * weights[np.newaxis, :]


# ════════════════════════════════════════════════════════════════
# INTEGRITY HASHES
# ════════════════════════════════════════════════════════════════

def compute_dataset_hash(blocks_data: List[Dict]) -> str:
    """SHA-256 hash of block data for reproducibility provenance."""
    h = hashlib.sha256()
    for blk in sorted(blocks_data, key=lambda b: b["block_id"]):
        h.update(str(blk["block_id"]).encode())
        mz, intensity = blk["mz"], blk["intensity"]
        h.update(str(len(mz)).encode())
        if hasattr(mz, "tobytes"):
            h.update(mz.tobytes())
            h.update(intensity.tobytes())
        else:
            h.update(str(mz).encode())
            h.update(str(intensity).encode())
    return h.hexdigest()[:16]


def compute_config_hash(config: Dict) -> str:
    """SHA-256 hash of a config dict."""
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ════════════════════════════════════════════════════════════════
# PROCESSED MODE PREPROCESSING
# ════════════════════════════════════════════════════════════════

def apply_baseline_correction(matrix: np.ndarray) -> np.ndarray:
    """Rolling-minimum baseline correction for each row (block)."""
    corrected = np.copy(matrix)
    for i in range(matrix.shape[0]):
        row = matrix[i]
        window = max(matrix.shape[1] // 20, 5)
        baseline = np.array([
            row[max(0, j - window):min(len(row), j + window + 1)].min()
            for j in range(len(row))
        ])
        corrected[i] = np.maximum(row - baseline, 0.0)
    return corrected


def apply_smoothing(matrix: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Moving-average smoothing (Savitzky-Golay style) for each row."""
    from scipy.ndimage import uniform_filter1d
    smoothed = np.copy(matrix)
    for i in range(matrix.shape[0]):
        smoothed[i] = uniform_filter1d(matrix[i], size=window_size)
    return smoothed


def preprocess_for_mode(
    matrix: np.ndarray,
    mode: str,
    transformations: Optional[List[str]] = None,
) -> np.ndarray:
    """
    Apply mode-specific preprocessing to a binned matrix.

    raw_time : no additional transforms (TIC + StandardScaler already applied).
    processed: baseline_correction + smoothing (configurable).
    """
    if mode == TimeAxisMode.RAW_TIME:
        return matrix

    transformations = transformations or ["baseline_correction", "smoothing"]
    result = matrix.copy()
    for t in transformations:
        t_lower = t.lower().strip()
        if t_lower == "baseline_correction":
            result = apply_baseline_correction(result)
        elif t_lower == "smoothing":
            result = apply_smoothing(result)
        # "tic_normalization" is handled earlier in build_mz_matrix
    return result


# ════════════════════════════════════════════════════════════════
# CLUSTER METRICS (standalone — no sklearn guard)
# ════════════════════════════════════════════════════════════════

def compute_cluster_metrics(
    matrix_scaled: np.ndarray,
    labels: np.ndarray,
) -> Dict[str, Optional[float]]:
    """
    Compute cluster quality metrics: silhouette, Davies-Bouldin,
    Calinski-Harabasz.
    """
    from sklearn.metrics import (
        silhouette_score,
        davies_bouldin_score,
        calinski_harabasz_score,
    )

    n_unique = len(set(labels.tolist()))
    n = len(labels)
    metrics: Dict[str, Optional[float]] = {}

    if n_unique >= 2 and n_unique < n:
        try:
            metrics["silhouette"] = round(float(silhouette_score(matrix_scaled, labels)), 4)
        except Exception:
            metrics["silhouette"] = None
        try:
            metrics["davies_bouldin"] = round(float(davies_bouldin_score(matrix_scaled, labels)), 4)
        except Exception:
            metrics["davies_bouldin"] = None
        try:
            metrics["calinski_harabasz"] = round(float(calinski_harabasz_score(matrix_scaled, labels)), 2)
        except Exception:
            metrics["calinski_harabasz"] = None
    else:
        metrics.update(silhouette=None, davies_bouldin=None, calinski_harabasz=None)

    return metrics
