"""
HPLC (High-Performance Liquid Chromatography) analysis.

Input: time (min) and detector signal (absorbance/intensity) arrays
Output: peaks, retention times, peak areas, resolution, plate count

Algorithms:
  - Peak detection: scipy.signal.find_peaks
  - Peak area: trapezoidal integration
  - Resolution: Rs = 2(tR2 - tR1) / (w1 + w2)
  - Plate count: N = 5.54 * (tR / w_half)^2
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks, peak_widths


def compute_hplc(
    time: list[float] | np.ndarray,
    signal: list[float] | np.ndarray,
    dead_time: float = 0.0,
    prominence: float = 0.01,
) -> dict[str, Any]:
    """Compute HPLC chromatography analysis.

    Args:
        time: Retention time values in minutes.
        signal: Detector response (absorbance, fluorescence, etc.).
        dead_time: Column void time (t0) in minutes.
        prominence: Minimum peak prominence as fraction of max signal.

    Returns:
        Dict with keys: peaks, retention_times, peak_areas, resolution,
        plate_count, assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    time = np.asarray(time, dtype=float)
    signal = np.asarray(signal, dtype=float)

    if len(time) < 10:
        raise ValueError("At least 10 data points required for HPLC analysis.")
    if len(time) != len(signal):
        raise ValueError(
            f"time ({len(time)}) and signal ({len(signal)}) must have same length."
        )

    # Sort by time
    sort_idx = np.argsort(time)
    time = time[sort_idx]
    signal = signal[sort_idx]

    # Baseline estimation (minimum signal)
    baseline = float(np.min(signal))
    corrected = signal - baseline

    max_signal = float(np.max(corrected))
    if max_signal <= 0:
        return _empty_result(time, dead_time, prominence)

    # Peak detection
    abs_prominence = max(prominence * max_signal, 1e-6)
    indices, properties = find_peaks(
        corrected,
        prominence=abs_prominence,
        distance=max(3, len(corrected) // 20),
    )

    if len(indices) == 0:
        return _empty_result(time, dead_time, prominence)

    # Peak widths at half maximum
    widths_result = peak_widths(corrected, indices, rel_height=0.5)
    widths_samples = widths_result[0]
    dt = np.mean(np.diff(time)) if len(time) > 1 else 1.0
    widths_time = widths_samples * dt

    # Build peak list
    peak_list = []
    for i, idx in enumerate(indices):
        retention_time = float(time[idx])
        height = float(corrected[idx])
        width_half = float(widths_time[i])

        # Peak area via trapezoidal integration around peak
        left = max(0, int(idx - widths_samples[i]))
        right = min(len(time) - 1, int(idx + widths_samples[i]))
        area = float(np.trapezoid(corrected[left:right + 1], time[left:right + 1]))

        # Plate count: N = 5.54 * (tR / w_half)^2
        plate_count = None
        if width_half > 0 and retention_time > dead_time:
            plate_count = float(5.54 * ((retention_time - dead_time) / width_half) ** 2)

        # Capacity factor k'
        capacity_factor = None
        if dead_time > 0:
            capacity_factor = float((retention_time - dead_time) / dead_time)

        peak: dict[str, Any] = {
            "retention_time_min": retention_time,
            "height": height,
            "area": area,
            "width_half_min": width_half,
            "plate_count": plate_count,
            "capacity_factor": capacity_factor,
            "prominence": float(properties["prominences"][i]),
        }
        peak_list.append(peak)

    # Sort by retention time
    peak_list.sort(key=lambda p: p["retention_time_min"])

    # Resolution between adjacent peaks
    resolutions = _compute_resolutions(peak_list)

    # Aggregate plate count (average of all peaks)
    plate_counts = [p["plate_count"] for p in peak_list if p["plate_count"] is not None]
    avg_plate_count = float(np.mean(plate_counts)) if plate_counts else None

    return {
        "peaks": peak_list,
        "peak_count": len(peak_list),
        "retention_times_min": [p["retention_time_min"] for p in peak_list],
        "peak_areas": [p["area"] for p in peak_list],
        "resolutions": resolutions,
        "average_plate_count": avg_plate_count,
        "baseline": baseline,
        "dead_time": dead_time,
        "time_range": {
            "min": float(time[0]),
            "max": float(time[-1]),
        },
        "assumptions": [
            {"type": "chemical", "description": f"Dead time (t0): {dead_time} min"},
            {"type": "analysis", "description": f"Peak prominence threshold: {prominence}"},
            {"type": "instrument", "description": "Isocratic elution assumed"},
        ],
        "uncertainty": {
            "retention_time": "depends on flow rate stability",
            "peak_area": "integration method: trapezoidal",
            "plate_count": "based on half-height width measurement",
        },
        "validity_domain": {
            "conditions": [
                f"Time range: {float(time[0]):.2f} - {float(time[-1]):.2f} min",
                "Gaussian peak shape assumed",
                "Baseline stability assumed",
            ],
        },
        "transformations": [
            {
                "name": "hplc",
                "algorithm": "peak_detection_plate_count",
                "parameters": {
                    "dead_time": dead_time,
                    "prominence": prominence,
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _compute_resolutions(peak_list: list[dict]) -> list[dict[str, Any]]:
    """Compute resolution between adjacent peaks.

    Rs = 2(tR2 - tR1) / (w1 + w2)
    """
    resolutions = []
    for i in range(len(peak_list) - 1):
        p1 = peak_list[i]
        p2 = peak_list[i + 1]
        w1 = p1["width_half_min"]
        w2 = p2["width_half_min"]
        if w1 + w2 > 0:
            rs = 2.0 * (p2["retention_time_min"] - p1["retention_time_min"]) / (w1 + w2)
            resolutions.append({
                "peak_pair": [i, i + 1],
                "resolution": float(rs),
            })
    return resolutions


def _empty_result(time: np.ndarray, dead_time: float, prominence: float) -> dict[str, Any]:
    """Return empty result when no peaks are detected."""
    return {
        "peaks": [],
        "peak_count": 0,
        "retention_times_min": [],
        "peak_areas": [],
        "resolutions": [],
        "average_plate_count": None,
        "baseline": 0.0,
        "dead_time": dead_time,
        "time_range": {
            "min": float(time[0]),
            "max": float(time[-1]),
        },
        "assumptions": [
            {"type": "chemical", "description": f"Dead time (t0): {dead_time} min"},
            {"type": "analysis", "description": f"Peak prominence threshold: {prominence}"},
            {"type": "instrument", "description": "Isocratic elution assumed"},
        ],
        "uncertainty": {
            "retention_time": "no peaks detected",
            "peak_area": "no peaks detected",
            "plate_count": "no peaks detected",
        },
        "validity_domain": {
            "conditions": [
                f"Time range: {float(time[0]):.2f} - {float(time[-1]):.2f} min",
                "No peaks detected above threshold",
            ],
        },
        "transformations": [
            {
                "name": "hplc",
                "algorithm": "peak_detection_plate_count",
                "parameters": {
                    "dead_time": dead_time,
                    "prominence": prominence,
                },
                "software_version": "0.1.0",
            },
        ],
    }
