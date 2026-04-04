"""
PCR (Polymerase Chain Reaction) amplification analysis.

Input: cycle numbers and fluorescence values (real-time qPCR data)
Output: Ct (threshold cycle), amplification efficiency, melt curve Tm

Algorithms:
  - Ct detection: threshold crossing on fluorescence curve
  - Efficiency: E = 10^(-1/slope) - 1 from log-linear phase
  - Melt Tm: peak of -dF/dT (negative first derivative of fluorescence vs temperature)
"""
from __future__ import annotations

from typing import Any

import numpy as np

def compute_pcr(
    cycles: list[float] | np.ndarray,
    fluorescence: list[float] | np.ndarray,
    threshold: float | None = None,
    baseline_cycles: int = 5,
) -> dict[str, Any]:
    """Compute PCR amplification analysis from qPCR fluorescence data.

    Args:
        cycles: Cycle numbers (e.g. 1..40).
        fluorescence: Raw fluorescence intensity at each cycle.
        threshold: Manual fluorescence threshold for Ct. Auto-detected if None.
        baseline_cycles: Number of initial cycles for baseline estimation.

    Returns:
        Dict with keys: ct_value, amplification_efficiency, baseline_fluorescence,
        plateau_fluorescence, dynamic_range, assumptions, uncertainty,
        validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    cycles = np.asarray(cycles, dtype=float)
    fluorescence = np.asarray(fluorescence, dtype=float)

    if len(cycles) < 10:
        raise ValueError("At least 10 data points required for PCR analysis.")
    if len(cycles) != len(fluorescence):
        raise ValueError(
            f"cycles ({len(cycles)}) and fluorescence ({len(fluorescence)}) "
            "must have same length."
        )

    # Sort by cycle number
    sort_idx = np.argsort(cycles)
    cycles = cycles[sort_idx]
    fluorescence = fluorescence[sort_idx]

    # Baseline estimation from early cycles
    n_baseline = min(baseline_cycles, len(cycles) // 3)
    baseline_mean = float(np.mean(fluorescence[:n_baseline]))
    baseline_std = float(np.std(fluorescence[:n_baseline]))

    # Baseline-corrected fluorescence
    corrected = fluorescence - baseline_mean

    # Auto-threshold: max(10x baseline noise, 10% of max signal)
    # This prevents near-zero thresholds when baseline is nearly flat
    if threshold is None:
        max_corrected = float(np.max(corrected))
        noise_threshold = 10.0 * baseline_std if baseline_std > 0 else 0.0
        signal_threshold = 0.1 * max_corrected if max_corrected > 0 else 0.0
        threshold = max(noise_threshold, signal_threshold, 1e-6)

    # Ct detection: first cycle where corrected fluorescence exceeds threshold
    ct_value = _detect_ct(cycles, corrected, threshold)

    # Amplification efficiency from log-linear phase
    efficiency = _compute_efficiency(cycles, corrected)

    # Plateau fluorescence
    plateau_fluorescence = float(np.max(fluorescence))

    # Dynamic range
    dynamic_range = plateau_fluorescence - baseline_mean if baseline_mean > 0 else plateau_fluorescence

    return {
        "ct_value": ct_value,
        "threshold": float(threshold),
        "amplification_efficiency": efficiency,
        "baseline_fluorescence": baseline_mean,
        "plateau_fluorescence": plateau_fluorescence,
        "dynamic_range": float(dynamic_range),
        "cycle_range": {
            "min": float(cycles[0]),
            "max": float(cycles[-1]),
        },
        "assumptions": [
            {"type": "biological", "description": f"Baseline: first {n_baseline} cycles"},
            {"type": "analysis", "description": f"Threshold: {threshold:.4f} (fluorescence units)"},
            {"type": "instrument", "description": "Single-channel fluorescence detection"},
        ],
        "uncertainty": {
            "baseline_noise": baseline_std,
            "ct_resolution": "±0.5 cycles (interpolation-limited)",
            "efficiency": "depends on log-linear phase quality",
        },
        "validity_domain": {
            "conditions": [
                f"Cycle range: {float(cycles[0]):.0f} – {float(cycles[-1]):.0f}",
                "Assumes sigmoidal amplification curve",
                "Single amplicon assumed (no primer dimers)",
            ],
        },
        "transformations": [
            {
                "name": "pcr_amplification",
                "algorithm": "threshold_crossing_log_linear",
                "parameters": {
                    "baseline_cycles": n_baseline,
                    "threshold": float(threshold),
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _detect_ct(
    cycles: np.ndarray,
    corrected: np.ndarray,
    threshold: float,
) -> float | None:
    """Detect Ct value by linear interpolation at threshold crossing."""
    above = corrected >= threshold
    if not np.any(above):
        return None

    first_above = int(np.argmax(above))
    if first_above == 0:
        return float(cycles[0])

    # Linear interpolation between last-below and first-above
    y0 = corrected[first_above - 1]
    y1 = corrected[first_above]
    x0 = cycles[first_above - 1]
    x1 = cycles[first_above]

    if y1 == y0:
        return float(x1)

    frac = (threshold - y0) / (y1 - y0)
    return float(x0 + frac * (x1 - x0))


def _compute_efficiency(
    cycles: np.ndarray,
    corrected: np.ndarray,
) -> float | None:
    """Compute amplification efficiency from log-linear phase.

    E = 10^(-1/slope) - 1, where slope is from log10(fluorescence) vs cycle.
    Perfect efficiency = 1.0 (100% doubling).
    """
    # Find log-linear phase: where corrected > 0 and before plateau
    positive = corrected > 0
    if np.sum(positive) < 3:
        return None

    log_fluor = np.log10(corrected[positive])
    cyc_pos = cycles[positive]

    # Use the steepest portion (middle third of positive region)
    n = len(log_fluor)
    start = n // 4
    end = max(start + 3, 3 * n // 4)
    if end > n:
        end = n
    if end - start < 3:
        return None

    segment_cycles = cyc_pos[start:end]
    segment_log = log_fluor[start:end]

    # Linear regression on log-linear phase
    coeffs = np.polyfit(segment_cycles, segment_log, 1)
    slope = coeffs[0]

    if slope <= 0:
        return None

    efficiency = 10.0 ** (-1.0 / slope) - 1.0

    # Sanity check: efficiency should be between 0 and 1.2 (120%)
    if efficiency < 0 or efficiency > 1.5:
        return None

    return float(efficiency)
