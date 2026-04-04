"""
Gel electrophoresis band analysis.

Input: distance/position array and intensity profile
Output: detected bands, estimated sizes (bp), band intensities

Algorithms:
  - Band detection: peak finding on intensity profile (scipy.signal.find_peaks)
  - Size estimation: log-linear calibration from DNA ladder
    log10(size) = a * distance + b
  - Band quantification: peak area integration
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks


def compute_gel_electrophoresis(
    distances: list[float] | np.ndarray,
    intensities: list[float] | np.ndarray,
    ladder_distances: list[float] | np.ndarray | None = None,
    ladder_sizes: list[float] | np.ndarray | None = None,
    min_prominence: float = 0.05,
) -> dict[str, Any]:
    """Analyze gel electrophoresis intensity profile.

    Args:
        distances: Migration distances or pixel positions along gel lane.
        intensities: Intensity values at each position.
        ladder_distances: Migration distances of DNA ladder bands.
        ladder_sizes: Known sizes (bp) of DNA ladder bands.
        min_prominence: Minimum peak prominence as fraction of max intensity.

    Returns:
        Dict with keys: bands, band_count, ladder_calibration,
        assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    distances = np.asarray(distances, dtype=float)
    intensities = np.asarray(intensities, dtype=float)

    if len(distances) < 10:
        raise ValueError("At least 10 data points required for gel analysis.")
    if len(distances) != len(intensities):
        raise ValueError(
            f"distances ({len(distances)}) and intensities ({len(intensities)}) "
            "must have same length."
        )

    # Sort by distance
    sort_idx = np.argsort(distances)
    distances = distances[sort_idx]
    intensities = intensities[sort_idx]

    # Normalize intensities to [0, 1]
    max_intensity = float(np.max(intensities))
    if max_intensity <= 0:
        raise ValueError("All intensities are zero or negative.")
    normalized = intensities / max_intensity

    # Build ladder calibration if provided
    calibration = None
    if ladder_distances is not None and ladder_sizes is not None:
        calibration = _build_calibration(
            np.asarray(ladder_distances, dtype=float),
            np.asarray(ladder_sizes, dtype=float),
        )

    # Detect bands via peak finding
    abs_prominence = max(min_prominence, 1e-6)
    indices, properties = find_peaks(
        normalized,
        prominence=abs_prominence,
        distance=max(3, len(normalized) // 30),
    )

    # Build band list
    bands = []
    for i, peak_idx in enumerate(indices):
        band: dict[str, Any] = {
            "distance": float(distances[peak_idx]),
            "intensity": float(intensities[peak_idx]),
            "relative_intensity": float(normalized[peak_idx]),
            "prominence": float(properties["prominences"][i]),
        }

        # Estimate size from calibration
        if calibration is not None:
            estimated_size = _estimate_size(distances[peak_idx], calibration)
            if estimated_size is not None:
                band["estimated_size_bp"] = estimated_size

        bands.append(band)

    # Sort bands by distance (migration order)
    bands.sort(key=lambda b: b["distance"])

    return {
        "bands": bands,
        "band_count": len(bands),
        "band_sizes_bp": [b.get("estimated_size_bp") for b in bands if "estimated_size_bp" in b],
        "band_intensities": [b["intensity"] for b in bands],
        "ladder_calibration": calibration,
        "distance_range": {
            "min": float(distances[0]),
            "max": float(distances[-1]),
        },
        "assumptions": [
            {"type": "biological", "description": "DNA migration in uniform electric field"},
            {"type": "analysis", "description": f"Min prominence: {min_prominence}"},
            {"type": "instrument", "description": "Uniform gel density assumed"},
        ],
        "uncertainty": {
            "size_estimation": "depends on ladder calibration quality" if calibration else "no ladder — sizes unavailable",
            "band_detection": f"prominence threshold = {min_prominence}",
        },
        "validity_domain": {
            "conditions": [
                f"Distance range: {float(distances[0]):.1f} – {float(distances[-1]):.1f}",
                "Linear DNA assumed (not supercoiled)",
                "Log-linear size-distance relationship assumed",
            ],
        },
        "transformations": [
            {
                "name": "gel_electrophoresis",
                "algorithm": "peak_detection_log_linear_calibration",
                "parameters": {
                    "min_prominence": min_prominence,
                    "has_ladder": calibration is not None,
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _build_calibration(
    ladder_distances: np.ndarray,
    ladder_sizes: np.ndarray,
) -> dict[str, Any] | None:
    """Build log-linear calibration from DNA ladder.

    log10(size) = slope * distance + intercept
    """
    if len(ladder_distances) < 2 or len(ladder_distances) != len(ladder_sizes):
        return None

    # Filter out non-positive sizes
    valid = ladder_sizes > 0
    if np.sum(valid) < 2:
        return None

    ld = ladder_distances[valid]
    ls = ladder_sizes[valid]
    log_sizes = np.log10(ls)

    # Linear fit: log10(size) = slope * distance + intercept
    coeffs = np.polyfit(ld, log_sizes, 1)
    slope = float(coeffs[0])
    intercept = float(coeffs[1])

    # R² calculation
    predicted = np.polyval(coeffs, ld)
    ss_res = np.sum((log_sizes - predicted) ** 2)
    ss_tot = np.sum((log_sizes - np.mean(log_sizes)) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "ladder_points": len(ld),
    }


def _estimate_size(
    distance: float,
    calibration: dict[str, Any],
) -> float | None:
    """Estimate DNA size (bp) from migration distance using calibration."""
    log_size = calibration["slope"] * distance + calibration["intercept"]
    size = 10.0 ** log_size
    if size < 1 or size > 1e8:
        return None
    return round(float(size))
