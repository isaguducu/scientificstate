"""
deisotoping.py — Mass spectrometry isotope envelope grouping.

Extracted from NitechLAB/deisotoping.py.
Changes from source:
  - Updated imports: core_utils → polymer_science.utils
  - Removed _test_deisotoping() main block.
  - All scientific logic preserved verbatim.
"""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from polymer_science.utils import (
    mz_within_tolerance as core_mz_within_tolerance,
    normalize_peak_format,
    select_top_n,
)


# ============================================================================
# CONSTANTS
# ============================================================================

CARBON_MASS_DIFF = 1.003355  # 12C → 13C mass difference (Da)
DEFAULT_MAX_ISOTOPE = 5
DEFAULT_ABS_TOL = 0.01   # Da
DEFAULT_PPM_TOL = 10.0   # ppm

# ── Types ────────────────────────────────────────────────────────────────────
Peak = Dict[str, float]                    # {'mz': float, 'intensity': float}
IsotopePeak = Dict[str, Union[float, int]] # {'mz', 'intensity', 'iso_index'}
Envelope = Dict[str, Union[float, int, List[IsotopePeak]]]


# ============================================================================
# HELPERS
# ============================================================================

def mz_within_tolerance(
    mz_observed: float,
    mz_theoretical: float,
    abs_tol: float = DEFAULT_ABS_TOL,
    ppm_tol: float = DEFAULT_PPM_TOL,
) -> bool:
    """Delegate to utils.mz_within_tolerance (backward-compat shim)."""
    return core_mz_within_tolerance(mz_observed, mz_theoretical, abs_tol, ppm_tol)


def normalize_peaks(peaks: Union[List, np.ndarray]) -> List[Peak]:
    """Normalize peak data to standard format (backward-compat shim)."""
    return normalize_peak_format(peaks)


def find_peak_within_tolerance(
    peaks_by_mz: List[Peak],
    target_mz: float,
    used_indices: set,
    abs_tol: float,
    ppm_tol: float,
) -> Optional[Tuple[int, Peak]]:
    """
    Find the closest unused peak within tolerance of *target_mz* in a
    m/z-sorted peak list using a binary-search style scan.
    """
    if not peaks_by_mz:
        return None

    ppm_as_da = (target_mz * ppm_tol) / 1e6
    max_tol = max(abs_tol, ppm_as_da)
    low_mz = target_mz - max_tol
    high_mz = target_mz + max_tol

    n = len(peaks_by_mz)
    left, right = 0, n
    while left < right:
        mid = (left + right) // 2
        if peaks_by_mz[mid]['mz'] < low_mz:
            left = mid + 1
        else:
            right = mid

    best_idx: Optional[int] = None
    best_peak: Optional[Peak] = None
    best_diff = float('inf')

    for i in range(left, n):
        peak = peaks_by_mz[i]
        mz = peak['mz']
        if mz > high_mz:
            break
        if i in used_indices:
            continue
        if mz_within_tolerance(mz, target_mz, abs_tol, ppm_tol):
            diff = abs(mz - target_mz)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
                best_peak = peak

    return (best_idx, best_peak) if best_idx is not None else None


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def group_isotopes(
    peaks: Union[List, np.ndarray],
    charge_state: int = 1,
    max_isotope: int = DEFAULT_MAX_ISOTOPE,
    abs_tol: float = DEFAULT_ABS_TOL,
    ppm_tol: float = DEFAULT_PPM_TOL,
) -> List[Envelope]:
    """
    Group centroid peaks into isotope envelopes using greedy deisotoping.

    Algorithm:
      1. Sort peaks by intensity (descending).
      2. For each unassigned peak (most intense first):
         a. Guard: skip if a lower-m/z unused peak exists within Δm/z
            (this peak is likely an M+k isotope of another compound).
         b. Start new envelope with this peak as monoisotopic.
         c. Search for M+1, M+2, ... M+max_isotope.
      3. Return envelopes sorted by monoisotopic intensity (descending).

    Args:
        peaks: Centroid peak list in any supported format.
        charge_state: Ion charge state (Δm/z = 1.003355 / z).
        max_isotope: Maximum isotope index to search (M+1 ... M+max_isotope).
        abs_tol: Absolute m/z matching tolerance (Da).
        ppm_tol: Relative m/z matching tolerance (ppm).

    Returns:
        List of envelope dicts:
          {'mono_mz', 'mono_intensity', 'envelope_max_intensity',
           'total_iso_count', 'peaks': [{'mz', 'intensity', 'iso_index'}, ...]}
    """
    normalized_peaks = normalize_peaks(peaks)
    if not normalized_peaks:
        return []

    delta_mz = CARBON_MASS_DIFF / charge_state

    peaks_by_intensity = sorted(normalized_peaks,
                                key=lambda p: p['intensity'],
                                reverse=True)
    peaks_by_mz = sorted(normalized_peaks, key=lambda p: p['mz'])

    mz_index_map: Dict = {}
    for i, p in enumerate(peaks_by_mz):
        key = (p['mz'], p['intensity'])
        if key not in mz_index_map:
            mz_index_map[key] = i

    used_indices: set = set()
    envelopes: List[Envelope] = []

    for peak in peaks_by_intensity:
        key = (peak['mz'], peak['intensity'])
        mz_idx = mz_index_map.get(key)
        if mz_idx is None or mz_idx in used_indices:
            continue

        # Guard: is this peak an M+k of another compound?
        is_potential_isotope = False
        for k in range(1, max_isotope + 1):
            left_target_mz = peak['mz'] - k * delta_mz
            if find_peak_within_tolerance(
                peaks_by_mz, left_target_mz, used_indices, abs_tol, ppm_tol
            ) is not None:
                is_potential_isotope = True
                break
        if is_potential_isotope:
            continue

        mono_mz = peak['mz']
        mono_intensity = peak['intensity']
        envelope_peaks = [{'mz': mono_mz, 'intensity': mono_intensity, 'iso_index': 0}]
        used_indices.add(mz_idx)

        for k in range(1, max_isotope + 1):
            result = find_peak_within_tolerance(
                peaks_by_mz, mono_mz + k * delta_mz, used_indices, abs_tol, ppm_tol
            )
            if result:
                idx, iso_peak = result
                envelope_peaks.append({
                    'mz': iso_peak['mz'],
                    'intensity': iso_peak['intensity'],
                    'iso_index': k,
                })
                used_indices.add(idx)

        envelopes.append({
            'mono_mz': mono_mz,
            'mono_intensity': mono_intensity,
            'envelope_max_intensity': max(p['intensity'] for p in envelope_peaks),
            'total_iso_count': len(envelope_peaks),
            'peaks': envelope_peaks,
        })

    envelopes.sort(key=lambda e: e['mono_intensity'], reverse=True)
    return envelopes


def select_top_n_envelopes(
    envelopes: List[Envelope],
    top_n: int = 200,
    sort_by: str = 'mono_intensity',
) -> List[Envelope]:
    """Return the top *top_n* envelopes sorted by *sort_by*."""
    if not envelopes:
        return []
    reverse = sort_by != 'mono_mz'
    return select_top_n(envelopes, n=top_n, key=sort_by, reverse=reverse)


def envelopes_to_table_data(envelopes: List[Envelope]) -> List[Dict]:
    """Convert envelope list to a flat table suitable for UI rendering."""
    rows = []
    for i, env in enumerate(envelopes, 1):
        rows.append({
            'rank': i,
            'mono_mz': env['mono_mz'],
            'mono_intensity': env['mono_intensity'],
            'iso_count': env['total_iso_count'],
            'isotope_mzs': ', '.join(f"{p['mz']:.4f}" for p in env['peaks']),
            'is_single': env['total_iso_count'] == 1,
        })
    return rows


def get_monoisotopic_peaks_only(envelopes: List[Envelope]) -> List[Peak]:
    """Return only the monoisotopic peak from each envelope."""
    return [{'mz': e['mono_mz'], 'intensity': e['mono_intensity']} for e in envelopes]


def get_envelope_statistics(envelopes: List[Envelope]) -> Dict:
    """Return summary statistics for a list of envelopes."""
    if not envelopes:
        return {'total_envelopes': 0, 'single_peak_count': 0, 'multi_peak_count': 0,
                'avg_isotope_count': 0, 'max_isotope_count': 0,
                'mz_range': (0, 0), 'intensity_range': (0, 0)}

    iso_counts = [e['total_iso_count'] for e in envelopes]
    mono_mzs = [e['mono_mz'] for e in envelopes]
    mono_intensities = [e['mono_intensity'] for e in envelopes]

    return {
        'total_envelopes': len(envelopes),
        'single_peak_count': sum(1 for c in iso_counts if c == 1),
        'multi_peak_count': sum(1 for c in iso_counts if c > 1),
        'avg_isotope_count': sum(iso_counts) / len(iso_counts),
        'max_isotope_count': max(iso_counts),
        'mz_range': (min(mono_mzs), max(mono_mzs)),
        'intensity_range': (min(mono_intensities), max(mono_intensities)),
    }


def process_total_spectrum_peaks(
    peaks: Union[List, np.ndarray],
    top_n: int = 200,
    charge_state: int = 1,
    max_isotope: int = 5,
    abs_tol: float = 0.01,
    ppm_tol: float = 10.0,
) -> Dict:
    """
    One-call deisotoping pipeline: group → select top N → table data.

    Returns:
        {envelopes, top_envelopes, table_data, mono_peaks, statistics}
    """
    all_envelopes = group_isotopes(peaks, charge_state=charge_state,
                                   max_isotope=max_isotope,
                                   abs_tol=abs_tol, ppm_tol=ppm_tol)
    top_envelopes = select_top_n_envelopes(all_envelopes, top_n=top_n)
    return {
        'envelopes': all_envelopes,
        'top_envelopes': top_envelopes,
        'table_data': envelopes_to_table_data(top_envelopes),
        'mono_peaks': get_monoisotopic_peaks_only(top_envelopes),
        'statistics': get_envelope_statistics(all_envelopes),
    }
