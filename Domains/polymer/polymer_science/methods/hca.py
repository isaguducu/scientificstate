"""
hca.py — JMP-compatible Two-Way HCA for Py-GC-MS block data.

Extracted from NitechLAB/polymer_compute.py (compute_hca, constrained_ward_linkage,
_auto_k, compute_hca_metrics functions).
Changes from source:
  - Updated import: cluster_pipeline → polymer_science.pipeline
  - Module header updated.
  - All scientific logic preserved verbatim.
"""

from typing import Dict, List, Optional

import numpy as np


# ════════════════════════════════════════════════════════════════
# CONSTRAINED WARD LINKAGE
# ════════════════════════════════════════════════════════════════

def constrained_ward_linkage(
    X: np.ndarray,
    sort_indices: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Sequence-constrained Ward linkage: only adjacent clusters may merge.

    Suitable for temperature-ordered block data where clusters must remain
    contiguous along the temperature axis.

    Args:
        X: (n_samples, n_features) scaled data matrix.
        sort_indices: Desired order (e.g. temperature argsort). None → 0..n-1.

    Returns:
        Z: (n-1, 4) scipy-compatible linkage matrix.
    """
    n = X.shape[0]
    if n < 2:
        return np.zeros((0, 4))

    if sort_indices is not None:
        X = X[sort_indices]

    centroids = {i: X[i].copy() for i in range(n)}
    sizes = {i: 1 for i in range(n)}
    active = list(range(n))

    Z = np.zeros((n - 1, 4))
    next_id = n

    for step in range(n - 1):
        best_dist = float('inf')
        best_j = -1

        for j in range(len(active) - 1):
            c1, c2 = active[j], active[j + 1]
            n1, n2 = sizes[c1], sizes[c2]
            diff = centroids[c1] - centroids[c2]
            ward_d = (n1 * n2) / (n1 + n2) * np.dot(diff, diff)
            if ward_d < best_dist:
                best_dist = ward_d
                best_j = j

        c1, c2 = active[best_j], active[best_j + 1]
        n1, n2 = sizes[c1], sizes[c2]
        new_size = n1 + n2
        new_centroid = (centroids[c1] * n1 + centroids[c2] * n2) / new_size

        Z[step, 0] = min(c1, c2)
        Z[step, 1] = max(c1, c2)
        Z[step, 2] = best_dist
        Z[step, 3] = new_size

        centroids[next_id] = new_centroid
        sizes[next_id] = new_size
        active[best_j] = next_id
        active.pop(best_j + 1)
        next_id += 1

    return Z


def compute_hca_metrics(
    matrix_scaled: np.ndarray,
    labels: np.ndarray,
    temperatures: List[float],
) -> Dict:
    """
    Compute HCA cluster quality metrics.

    Returns:
        Dict with silhouette, davies_bouldin, calinski_harabasz, contiguity_score.
    """
    from sklearn.metrics import (
        silhouette_score,
        davies_bouldin_score,
        calinski_harabasz_score,
    )

    n = len(labels)
    n_unique = len(set(labels))
    metrics: Dict = {}

    if n_unique >= 2 and n_unique < n:
        for name, fn in [
            ("silhouette", silhouette_score),
            ("davies_bouldin", davies_bouldin_score),
            ("calinski_harabasz", calinski_harabasz_score),
        ]:
            try:
                metrics[name] = round(float(fn(matrix_scaled, labels)), 4)
            except Exception:
                metrics[name] = None
    else:
        metrics.update(silhouette=None, davies_bouldin=None, calinski_harabasz=None)

    temp_order = np.argsort(temperatures)
    labels_temp_sorted = np.array(labels)[temp_order]
    n_transitions = sum(
        1 for i in range(1, len(labels_temp_sorted))
        if labels_temp_sorted[i] != labels_temp_sorted[i - 1]
    )
    n_clusters = n_unique
    if n_clusters > 1:
        perfect_transitions = n_clusters - 1
        contiguity = round(perfect_transitions / max(n_transitions, 1), 4)
    else:
        contiguity = 1.0

    metrics["contiguity_score"] = min(contiguity, 1.0)
    metrics["n_transitions"] = n_transitions
    metrics["perfect_transitions"] = n_clusters - 1 if n_clusters > 1 else 0

    return metrics


def _auto_k(Z: np.ndarray, n_blocks: int) -> int:
    """Estimate optimal k via elbow method on Ward merge distances."""
    if Z is None or len(Z) == 0:
        return min(4, max(2, n_blocks // 4))
    dists = Z[:, 2]
    cap = min(12, n_blocks - 1)
    last = dists[-cap:] if len(dists) >= cap else dists
    if len(last) < 2:
        return 2
    gaps = np.diff(last)
    best = int(np.argmax(gaps))
    k = len(gaps) - best
    lo, hi = 2, min(12, n_blocks // 2)
    return int(np.clip(k, lo, hi))


# ════════════════════════════════════════════════════════════════
# TWO-WAY HCA
# ════════════════════════════════════════════════════════════════

def compute_hca(
    blocks_data: List[Dict],
    n_clusters: Optional[int] = None,
    method: str = "ward",
    mz_min: float = 40.0,
    mz_max: float = 1200.0,
    mz_bin: float = 1.0,
    mode: str = "raw_time",
    transformations: Optional[List[str]] = None,
    order_mode: str = "dendrogram",
) -> Dict:
    """
    Compute Two-Way Hierarchical Cluster Analysis — **JMP-compatible**.

    Three order_mode values:
      "dendrogram"  (Mode-A): Unconstrained HCA, dendrogram leaf order.
      "temperature" (Mode-B): Unconstrained HCA, temperature-sorted display.
      "constrained" (Mode-C): Sequence-constrained Ward, adjacent merges only.

    Args:
        blocks_data: List of block dicts (block_id, mz, intensity, temperature).
        n_clusters: Desired cluster count; None → auto (elbow method).
        method: Linkage method for unconstrained modes ("ward").
        mz_min, mz_max, mz_bin: Binning parameters (Da).
        mode: "raw_time" | "processed".
        transformations: Override transform list for processed mode.
        order_mode: "dendrogram" | "temperature" | "constrained".

    Returns:
        Dict with Two-Way HCA results compatible with the UI heatmap renderer.
    """
    from scipy.cluster.hierarchy import linkage, fcluster, leaves_list
    from scipy.spatial.distance import pdist
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
    matrix_scaled = np.nan_to_num(matrix_scaled, nan=0.0)

    _auto_mode = n_clusters is None
    if not _auto_mode:
        n_clusters = min(n_clusters, len(rows))

    temp_sort = np.argsort(temperatures)

    # ── Column clustering ─────────────────────────────────────────────────────
    if order_mode == "constrained":
        Z_col = constrained_ward_linkage(matrix_scaled, sort_indices=temp_sort)
        Z_col_display = Z_col
        if _auto_mode:
            n_clusters = _auto_k(Z_col, len(rows))
        else:
            n_clusters = min(n_clusters, len(rows))
        labels_sorted = fcluster(Z_col, t=n_clusters, criterion="maxclust")
        labels_arr = np.zeros(len(rows), dtype=int)
        for i, orig_idx in enumerate(temp_sort):
            labels_arr[orig_idx] = labels_sorted[i]
        col_order = temp_sort.tolist()

    elif order_mode == "temperature":
        Z_col = linkage(matrix_scaled, method=method, metric='euclidean')
        Z_col_display = Z_col
        if _auto_mode:
            n_clusters = _auto_k(Z_col, len(rows))
        else:
            n_clusters = min(n_clusters, len(rows))
        labels_arr = fcluster(Z_col, t=n_clusters, criterion="maxclust")
        col_order = temp_sort.tolist()

    else:  # "dendrogram" (Mode-A)
        Z_col = linkage(matrix_scaled, method=method, metric='euclidean')
        Z_col_display = Z_col
        if _auto_mode:
            n_clusters = _auto_k(Z_col, len(rows))
        else:
            n_clusters = min(n_clusters, len(rows))
        labels_arr = fcluster(Z_col, t=n_clusters, criterion="maxclust")
        col_order = leaves_list(Z_col).tolist()

    labels = labels_arr.tolist()

    # ── Row clustering (m/z bins) ─────────────────────────────────────────────
    matrix_T = matrix_scaled.T
    row_var = matrix_T.var(axis=1)
    active_rows = row_var > 1e-12
    n_active = active_rows.sum()

    if n_active >= 2:
        Z_row = linkage(matrix_T[active_rows], method=method, metric='euclidean')
        row_order_active = leaves_list(Z_row)
        active_idx = np.where(active_rows)[0]
        row_order = active_idx[row_order_active].tolist()
        passive_idx = np.where(~active_rows)[0].tolist()
        row_order_full = row_order + passive_idx
    else:
        Z_row = None
        row_order_full = list(range(n_bins))

    reordered_matrix = matrix_scaled[np.ix_(col_order, row_order_full)]

    dists = pdist(matrix_scaled, metric='euclidean')
    dist_stats = {
        "min": float(dists.min()) if len(dists) > 0 else 0,
        "max": float(dists.max()) if len(dists) > 0 else 0,
        "mean": float(dists.mean()) if len(dists) > 0 else 0,
        "median": float(np.median(dists)) if len(dists) > 0 else 0,
    }

    merge_distances = Z_col[:, 2].tolist() if len(Z_col) > 0 else []

    labels_np = np.array(labels)
    cluster_summary: Dict = {}
    for cid in range(1, n_clusters + 1):
        mask = labels_np == cid
        temps = np.array(temperatures)[mask]
        bids = np.array(block_ids)[mask]
        cluster_matrix = matrix_scaled[mask]
        mean_spec = cluster_matrix.mean(axis=0) if cluster_matrix.shape[0] > 0 else np.zeros(n_bins)
        cluster_summary[str(cid)] = {
            "block_count": int(mask.sum()),
            "block_ids": bids.tolist(),
            "temp_min": float(temps.min()) if len(temps) > 0 else 0,
            "temp_max": float(temps.max()) if len(temps) > 0 else 0,
            "temp_mean": float(temps.mean()) if len(temps) > 0 else 0,
            "temp_std": float(temps.std()) if len(temps) > 1 else 0,
            "mean_spectrum_top5_mz": [
                float(mz_bins[i])
                for i in np.argsort(np.abs(mean_spec))[-5:][::-1]
            ],
        }

    metrics = compute_hca_metrics(matrix_scaled, labels_np, temperatures)

    _order_desc = {
        "dendrogram": "Unconstrained Ward — dendrogram leaf order (Mode-A)",
        "temperature": "Unconstrained Ward — temperature-sorted display (Mode-B)",
        "constrained": "Sequence-constrained Ward — adjacent-only merges (Mode-C)",
    }

    return {
        "block_ids": block_ids,
        "temperatures": temperatures,
        "labels": labels,
        "linkage_matrix": Z_col,
        "linkage_matrix_col": Z_col,
        "linkage_matrix_col_display": Z_col_display,
        "linkage_matrix_row": Z_row,
        "col_order": col_order,
        "row_order": row_order_full,
        "reordered_matrix": reordered_matrix,
        "matrix_scaled": matrix_scaled,
        "mz_bins": mz_bins,
        "cluster_summary": cluster_summary,
        "n_clusters": n_clusters,
        "auto_k_used": _auto_mode,
        "method": method,
        "order_mode": order_mode,
        "merge_distances": merge_distances,
        "distance_stats": dist_stats,
        "metrics": metrics,
        "assumptions": {
            "standardization": "StandardScaler (μ=0, σ=1) — JMP 'Standardize by Columns'",
            "distance_metric": "Euclidean",
            "linkage_method": f"{method} (JMP: Ward minimum variance criterion)",
            "ward_formula": "Δ(A,B) = (n_A·n_B)/(n_A+n_B) · ||μ_A - μ_B||²",
            "two_way": True,
            "order_mode": order_mode,
            "order_description": _order_desc.get(order_mode, order_mode),
        },
    }
