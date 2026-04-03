"""
utils.py — Polymer Science utility functions (Source of Truth).

Extracted from NitechLAB/core_utils.py.
Changes from source:
  - Removed confidence_color() — had Tkinter/design_system dependency.
  - Updated module docstring and import path references.
  - All scientific logic preserved verbatim.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

@dataclass
class PeakData:
    """General peak data structure used across polymer_science modules."""
    mz: float
    intensity: float
    index: int = 0
    block_id: int = 0
    iso_index: int = 0  # Isotope index (0 = monoisotopic)

    def to_dict(self) -> Dict[str, float]:
        return {
            'mz': self.mz,
            'intensity': self.intensity,
            'index': self.index,
            'block_id': self.block_id,
            'iso_index': self.iso_index,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'PeakData':
        return cls(
            mz=float(d.get('mz', d.get('m/z', 0))),
            intensity=float(d.get('intensity', d.get('int', 0))),
            index=int(d.get('index', 0)),
            block_id=int(d.get('block_id', 0)),
            iso_index=int(d.get('iso_index', 0)),
        )


# ============================================================================
# PEAK SELECTION
# ============================================================================

def select_top_n(
    data: Union[List[Dict], List[Any], np.ndarray],
    n: int,
    key: Union[str, Callable] = 'intensity',
    reverse: bool = True,
    target_value: Optional[float] = None,
) -> List:
    """Return the top-N elements from *data* by *key*."""
    if not data or n <= 0:
        return []

    if isinstance(key, str):
        if isinstance(data[0], dict):
            def key_func(x: object, _k: str = key) -> float:  # noqa: E731 – E731 not applicable here
                return x.get(_k, 0)  # type: ignore[union-attr]
        else:
            def key_func(x: object, _k: str = key) -> float:  # type: ignore[misc]
                return getattr(x, _k, 0)
    else:
        key_func = key

    if target_value is not None:
        sorted_data = sorted(data, key=lambda x: abs(key_func(x) - target_value))
    else:
        sorted_data = sorted(data, key=key_func, reverse=reverse)

    return sorted_data[:n]


def select_bottom_n(
    data: Union[List[Dict], List[Any], np.ndarray],
    n: int,
    key: Union[str, Callable] = 'intensity',
) -> List:
    """Return the bottom-N elements from *data* by *key*."""
    return select_top_n(data, n, key, reverse=False)


# ============================================================================
# MAXIMUM / MINIMUM
# ============================================================================

def find_maximum(
    data: Union[List[Dict], List[Any], np.ndarray],
    key: Union[str, Callable] = 'intensity',
    return_index: bool = False,
) -> Union[Any, Tuple[int, Any], None]:
    """Return the element with the maximum *key* value."""
    if not data:
        return None

    if isinstance(data, np.ndarray):
        if data.ndim == 1:
            idx = int(np.argmax(data))
            return (idx, data[idx]) if return_index else data[idx]
        elif data.ndim == 2:
            col = 1 if key == 'intensity' else 0
            idx = int(np.argmax(data[:, col]))
            return (idx, data[idx]) if return_index else data[idx]

    if isinstance(key, str):
        key_func: Callable = (lambda x: x.get(key, 0)) if isinstance(data[0], dict) else (lambda x: getattr(x, key, 0))
    else:
        key_func = key

    max_idx, max_val = 0, key_func(data[0])
    for i, item in enumerate(data[1:], 1):
        v = key_func(item)
        if v > max_val:
            max_val, max_idx = v, i

    return (max_idx, data[max_idx]) if return_index else data[max_idx]


def find_minimum(
    data: Union[List[Dict], List[Any], np.ndarray],
    key: Union[str, Callable] = 'intensity',
    return_index: bool = False,
) -> Union[Any, Tuple[int, Any], None]:
    """Return the element with the minimum *key* value."""
    if not data:
        return None

    if isinstance(data, np.ndarray) and data.ndim == 1:
        idx = int(np.argmin(data))
        return (idx, data[idx]) if return_index else data[idx]

    if isinstance(key, str):
        key_func: Callable = (lambda x: x.get(key, 0)) if isinstance(data[0], dict) else (lambda x: getattr(x, key, 0))
    else:
        key_func = key

    min_idx, min_val = 0, key_func(data[0])
    for i, item in enumerate(data[1:], 1):
        v = key_func(item)
        if v < min_val:
            min_val, min_idx = v, i

    return (min_idx, data[min_idx]) if return_index else data[min_idx]


def find_max_in_range(
    data: Union[List[Dict], List[Any]],
    target_value: float,
    tolerance: float,
    target_key: str = 'mz',
    value_key: str = 'intensity',
) -> float:
    """Return the maximum *value_key* among elements within *tolerance* of *target_value*."""
    if not data:
        return 0.0

    max_value = 0.0
    found = False
    for item in data:
        if isinstance(item, dict):
            t = item.get(target_key, item.get('m/z', 0))
            v = item.get(value_key, item.get('int', 0))
        elif isinstance(item, (tuple, list)):
            t, v = item[0], item[1]
        else:
            t = getattr(item, target_key, 0)
            v = getattr(item, value_key, 0)

        if abs(t - target_value) <= tolerance:
            found = True
            if v > max_value:
                max_value = v

    return max_value if found else 0.0


# ============================================================================
# NORMALIZATION
# ============================================================================

class NormalizationMethod:
    ZSCORE = 'zscore'
    MINMAX = 'minmax'
    MAX = 'max'


def normalize_data(
    data: Union[List[float], np.ndarray],
    method: str = NormalizationMethod.ZSCORE,
    axis: Optional[int] = None,
) -> np.ndarray:
    """Normalize *data* using the specified method."""
    arr = np.array(data, dtype=float)
    if arr.size == 0:
        return arr

    if method == NormalizationMethod.ZSCORE:
        mean = np.mean(arr, axis=axis, keepdims=True) if axis is not None else np.mean(arr)
        std = np.std(arr, axis=axis, keepdims=True) if axis is not None else np.std(arr)
        if isinstance(std, np.ndarray):
            std[std == 0] = 1
        elif std == 0:
            std = 1
        return (arr - mean) / std

    elif method == NormalizationMethod.MINMAX:
        mn = np.min(arr, axis=axis, keepdims=True) if axis is not None else np.min(arr)
        mx = np.max(arr, axis=axis, keepdims=True) if axis is not None else np.max(arr)
        rng = mx - mn
        if isinstance(rng, np.ndarray):
            rng[rng == 0] = 1
        elif rng == 0:
            rng = 1
        return (arr - mn) / rng

    elif method == NormalizationMethod.MAX:
        mx = np.max(arr, axis=axis, keepdims=True) if axis is not None else np.max(arr)
        if isinstance(mx, np.ndarray):
            mx[mx == 0] = 1
        elif mx == 0:
            mx = 1
        return arr / mx

    raise ValueError(f"Unknown normalization method: {method!r}")


# ============================================================================
# GROUPING / TOLERANCE MATCHING
# ============================================================================

def mz_within_tolerance(
    mz_observed: float,
    mz_theoretical: float,
    abs_tol: float = 0.01,
    ppm_tol: float = 10.0,
) -> bool:
    """Return True if the two m/z values agree within abs_tol (Da) OR ppm_tol (ppm)."""
    abs_diff = abs(mz_observed - mz_theoretical)
    ppm_diff = (abs_diff / mz_theoretical) * 1e6 if mz_theoretical > 0 else float('inf')
    return (abs_diff <= abs_tol) or (ppm_diff <= ppm_tol)


def group_by_tolerance(
    data: Union[List[Dict], List[Any]],
    tolerance: float,
    key: str = 'mz',
) -> List[List]:
    """Group *data* elements whose *key* values are within *tolerance* of each other."""
    if not data:
        return []

    key_func: Callable = (lambda x: x.get(key, 0)) if isinstance(data[0], dict) else (lambda x: getattr(x, key, 0))
    sorted_data = sorted(data, key=key_func)

    groups: List[List] = []
    current_group = [sorted_data[0]]
    current_value = key_func(sorted_data[0])

    for item in sorted_data[1:]:
        v = key_func(item)
        if abs(v - current_value) <= tolerance:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]
            current_value = v

    groups.append(current_group)
    return groups


def select_representative_from_groups(
    groups: List[List],
    method: str = 'max_intensity',
    key: str = 'intensity',
) -> List:
    """Select one representative element from each group."""
    reps = []
    for group in groups:
        if not group:
            continue
        if method == 'first':
            reps.append(group[0])
        elif method == 'max_intensity':
            r = find_maximum(group, key=key)
            if r is not None:
                reps.append(r)
        elif method == 'centroid':
            key_func: Callable = (lambda x: x.get(key, 0)) if isinstance(group[0], dict) else (lambda x: getattr(x, key, 0))
            vals = [key_func(g) for g in group]
            mean_val = float(np.mean(vals))
            closest = int(np.argmin([abs(v - mean_val) for v in vals]))
            reps.append(group[closest])
    return reps


# ============================================================================
# DATA FORMAT CONVERSION
# ============================================================================

def normalize_peak_format(peaks: Union[List, np.ndarray]) -> List[Dict]:
    """Normalize peak data to List[{'mz': float, 'intensity': float}]."""
    if isinstance(peaks, np.ndarray):
        if peaks.size == 0:
            return []
        if peaks.ndim == 2 and peaks.shape[1] >= 2:
            return [{'mz': float(r[0]), 'intensity': float(r[1])} for r in peaks]
        return []
    if not peaks:
        return []

    first = peaks[0]
    normalized: List[Dict] = []

    if isinstance(first, dict):
        for p in peaks:
            normalized.append({
                'mz': float(p.get('mz', p.get('m/z', 0))),
                'intensity': float(p.get('intensity', p.get('int', 0))),
            })
    elif isinstance(first, (tuple, list)):
        for p in peaks:
            normalized.append({'mz': float(p[0]), 'intensity': float(p[1])})
    elif hasattr(first, 'mz') and hasattr(first, 'intensity'):
        for p in peaks:
            normalized.append({'mz': float(p.mz), 'intensity': float(p.intensity)})

    return normalized


def peaks_to_numpy(peaks: List[Dict]) -> np.ndarray:
    """Convert peak dicts to shape (N, 2) numpy array [mz, intensity]."""
    if not peaks:
        return np.array([]).reshape(0, 2)
    return np.array([[p.get('mz', 0), p.get('intensity', 0)] for p in peaks])


def numpy_to_peaks(arr: np.ndarray) -> List[Dict]:
    """Convert (N, 2) numpy array to peak dict list."""
    if arr.size == 0:
        return []
    return [{'mz': float(r[0]), 'intensity': float(r[1])} for r in arr]


# ============================================================================
# STATISTICS
# ============================================================================

def compute_basic_statistics(data: Union[List[float], np.ndarray]) -> Dict[str, float]:
    """Return basic descriptive statistics for numeric *data*."""
    arr = np.array(data, dtype=float)
    if arr.size == 0:
        return {'count': 0, 'mean': 0, 'std': 0, 'min': 0, 'max': 0,
                'median': 0, 'sum': 0, 'q25': 0, 'q75': 0, 'iqr': 0}

    q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    return {
        'count': len(arr),
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'median': float(np.median(arr)),
        'sum': float(np.sum(arr)),
        'q25': q25,
        'q75': q75,
        'iqr': q75 - q25,
    }


# ============================================================================
# BINARY SEARCH
# ============================================================================

def binary_search_range(
    sorted_values: Union[List[float], np.ndarray],
    target: float,
    tolerance: float,
) -> Tuple[int, int]:
    """Return (start, end) index range for elements within *tolerance* of *target*."""
    if not len(sorted_values):
        return (0, 0)

    lo, hi = target - tolerance, target + tolerance
    n = len(sorted_values)

    left, right = 0, n
    while left < right:
        mid = (left + right) // 2
        if sorted_values[mid] < lo:
            left = mid + 1
        else:
            right = mid
    start = left

    left, right = start, n
    while left < right:
        mid = (left + right) // 2
        if sorted_values[mid] <= hi:
            left = mid + 1
        else:
            right = mid

    return (start, left)


# ============================================================================
# MASS ACCURACY
# ============================================================================

def confidence_score(mz_obs: float, mz_lib: float,
                     resolution: int = 22000) -> Tuple[str, str, float]:
    """
    Return (level, symbol, ppm) mass accuracy confidence for a fragment match.

    Levels (AYDINLATMA_METODU.md §1):
      L2 — Strong  : < 5 ppm  (lock mass active, MS1)
      L3 — Probable: 5-50 ppm (no lock mass)
      L4 — Uncertain: > 50 ppm or no match

    Note: Without lock mass calibration (~200 ppm instrument drift) all
    results are effectively L3 regardless of computed ppm.
    """
    if mz_lib <= 0:
        return ("L4", "?", 999.9)

    delta_da = abs(mz_obs - mz_lib)
    ppm = (delta_da / mz_lib) * 1e6

    if ppm < 5.0:
        return ("L2", "OK", round(ppm, 1))
    elif ppm < 50.0:
        return ("L3", "~", round(ppm, 1))
    else:
        return ("L4", "?", round(ppm, 1))
