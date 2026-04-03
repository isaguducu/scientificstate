"""
fragment_matching.py — Fragment database matching for polymer identification.

Uses fragment_db.json (keys: PS, PAN, ADDITIVES, BACKGROUND) to match
experimental m/z peaks against known polymer fragment libraries.

Scientific context:
  All matches are L3 (Probable) without lock mass calibration.
  Ratios and differences are meaningful; absolute identities uncertain.
  (Reference: AYDINLATMA_METODU.md §1)
"""

from typing import Any, Dict, List, Optional

from polymer_science.utils import confidence_score, mz_within_tolerance


def match_peaks(
    peaks,
    fragment_db: Dict,
    polymer: str = "PS",
    abs_tol: float = 0.5,
    ppm_tol: float = 200.0,
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Match experimental peaks against the fragment reference database.

    Args:
        peaks: Peak list — any format accepted by normalize_peak_format, or
               list of {'mz': float, 'intensity': float} dicts.
        fragment_db: Parsed fragment_db.json dict.
        polymer: Key to look up in fragment_db (PS, PAN, PMMA, ADDITIVES, …).
        abs_tol: Absolute m/z matching tolerance (Da). Default 0.5 Da
                 (appropriate for instruments without lock mass calibration).
        ppm_tol: Relative m/z tolerance (ppm). Default 200 ppm (no lock mass).
        top_n: If set, return only the top-N matches by intensity.

    Returns:
        List of match dicts, each with:
          {mz_obs, intensity, mz_lib, fragment_name, delta_da, ppm,
           confidence_level, confidence_symbol, polymer}
        Sorted by intensity descending.
    """
    from polymer_science.utils import normalize_peak_format

    normalized = normalize_peak_format(peaks) if not (
        peaks and isinstance(peaks[0], dict) and 'mz' in peaks[0]
    ) else list(peaks)

    poly_data = fragment_db.get(polymer.upper(), {})
    lib_fragments = poly_data.get("fragments", [])

    if not lib_fragments:
        return []

    matches: List[Dict[str, Any]] = []

    for peak in normalized:
        mz_obs = float(peak.get('mz', 0))
        intensity = float(peak.get('intensity', 0))

        best: Optional[Dict] = None
        best_delta = float('inf')

        for frag in lib_fragments:
            mz_lib = float(frag.get('mz', 0))
            if mz_lib <= 0:
                continue
            if mz_within_tolerance(mz_obs, mz_lib, abs_tol=abs_tol, ppm_tol=ppm_tol):
                delta = abs(mz_obs - mz_lib)
                if delta < best_delta:
                    best_delta = delta
                    best = frag

        if best is not None:
            mz_lib = float(best.get('mz', 0))
            level, symbol, ppm = confidence_score(mz_obs, mz_lib)
            matches.append({
                'mz_obs': round(mz_obs, 4),
                'intensity': intensity,
                'mz_lib': round(mz_lib, 4),
                'fragment_name': best.get('name', best.get('formula', '?')),
                'delta_da': round(mz_obs - mz_lib, 4),
                'ppm': ppm,
                'confidence_level': level,
                'confidence_symbol': symbol,
                'polymer': polymer.upper(),
            })

    matches.sort(key=lambda x: x['intensity'], reverse=True)

    if top_n is not None:
        matches = matches[:top_n]

    return matches


def match_all_polymers(
    peaks,
    fragment_db: Dict,
    abs_tol: float = 0.5,
    ppm_tol: float = 200.0,
) -> Dict[str, List[Dict]]:
    """
    Run fragment matching against all polymers present in *fragment_db*.

    Returns:
        Dict mapping polymer_key → list of match dicts.
    """
    results: Dict[str, List[Dict]] = {}
    for key in fragment_db:
        if key.startswith('_'):
            continue
        results[key] = match_peaks(
            peaks, fragment_db, polymer=key,
            abs_tol=abs_tol, ppm_tol=ppm_tol,
        )
    return results
