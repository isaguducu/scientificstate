"""
pca.py — JMP-compatible PCA for Py-GC-MS block data.

Extracted from NitechLAB/polymer_compute.py (compute_pca function).
Changes from source:
  - Updated import: cluster_pipeline → polymer_science.pipeline
  - Module header updated.
  - All scientific logic preserved verbatim.
"""

from typing import Dict, List, Optional

import numpy as np


def compute_pca(
    blocks_data: List[Dict],
    n_components: int = 3,
    mz_min: float = 40.0,
    mz_max: float = 1200.0,
    mz_bin: float = 1.0,
    mode: str = "raw_time",
    transformations: Optional[List[str]] = None,
) -> Dict:
    """
    Compute PCA from block list — **JMP-compatible (correlation-based)**.

    JMP compatibility details (Ref: JMP Principal Components v19.0):
      1. Pre-processing: TIC normalization → StandardScaler (μ=0, σ=1)
         → correlation matrix PCA == JMP "on Correlations" mode.
      2. sklearn.PCA uses SVD internally; results are equivalent to
         JMP eigendecomp after StandardScaler.
      3. JMP-style loadings:
         Loading(i,j) = Eigenvector(i,j) × √Eigenvalue_j
      4. Eigenvector = pca.components_ (row = PC, col = variable, norm=1)
         Scores = data_scaled @ eigenvectors.T

    Args:
        blocks_data: List of dicts with keys:
            block_id (int), mz (array-like), intensity (array-like),
            temperature (float, optional).
        n_components: Number of principal components to retain.
        mz_min, mz_max, mz_bin: m/z binning parameters (Da).
        mode: "raw_time" | "processed" (enables baseline + smoothing).
        transformations: Override transform list for processed mode.

    Returns:
        Dict with PCA results and JMP-compatible loadings.
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    try:
        from polymer_science.pipeline import preprocess_for_mode as _preprocess
        _HAS_PIPELINE = True
    except ImportError:
        _HAS_PIPELINE = False

    mz_bins = np.arange(mz_min, mz_max + mz_bin, mz_bin)
    n_bins = len(mz_bins)

    block_ids: List[int] = []
    temperatures: List[float] = []
    rows: List[np.ndarray] = []

    for blk in blocks_data:
        block_ids.append(blk["block_id"])
        temperatures.append(blk.get("temperature", blk["block_id"] * 10 + 50))

        row = np.zeros(n_bins)
        for mz, intensity in zip(blk["mz"], blk["intensity"]):
            if mz_min <= mz <= mz_max:
                bin_idx = min(int(round((mz - mz_min) / mz_bin)), n_bins - 1)
                row[bin_idx] += intensity

        total = row.sum()
        if total > 0:
            row = row / total
        rows.append(row)

    matrix = np.array(rows)

    if mode == "processed" and _HAS_PIPELINE:
        try:
            matrix = _preprocess(matrix, "processed", transformations)
        except Exception:
            pass

    scaler = StandardScaler()
    matrix_scaled = scaler.fit_transform(matrix)

    n_comp = min(n_components, matrix_scaled.shape[0], matrix_scaled.shape[1])
    pca = PCA(n_components=n_comp)
    scores = pca.fit_transform(matrix_scaled)

    eigenvectors = pca.components_           # (n_comp, n_bins)
    eigenvalues = pca.explained_variance_    # (n_comp,)
    jmp_loadings = eigenvectors * np.sqrt(eigenvalues)[:, np.newaxis]

    kaiser_n = int((eigenvalues > 1.0).sum()) if len(eigenvalues) > 0 else n_comp

    eigenvalue_table = []
    cumvar = 0.0
    for i in range(n_comp):
        ev = float(eigenvalues[i])
        pct = float(pca.explained_variance_ratio_[i]) * 100.0
        cumvar += pct
        eigenvalue_table.append({
            "pc": i + 1,
            "eigenvalue": round(ev, 6),
            "percent": round(pct, 2),
            "cumulative_percent": round(cumvar, 2),
            "kaiser_retain": ev > 1.0,
        })

    return {
        "block_ids": block_ids,
        "temperatures": temperatures,
        "scores": scores,
        "loadings": pca.components_,
        "jmp_loadings": jmp_loadings,
        "explained_variance_ratio": pca.explained_variance_ratio_,
        "explained_variance": eigenvalues,
        "cumulative_variance": np.cumsum(pca.explained_variance_ratio_),
        "mz_bins": mz_bins,
        "n_components": n_comp,
        "kaiser_n": kaiser_n,
        "eigenvalue_table": eigenvalue_table,
        "assumptions": {
            "mz_bin_da": mz_bin,
            "mz_range": [mz_min, mz_max],
            "n_components": n_comp,
            "normalize": "TIC",
            "scaler": "StandardScaler (μ=0, σ=1)",
            "matrix_type": "Correlation (JMP default)",
            "decomposition": "SVD (sklearn) ≡ Eigendecomp(corr) on standardized data",
            "loading_formula": "eigenvector × √eigenvalue (JMP convention)",
        },
    }
