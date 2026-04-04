"""UV-Vis spectroscopy analysis tests."""

import numpy as np
import pytest

from chemistry.methods.uv_vis import compute_uv_vis


# -- Fixtures ----------------------------------------------------------------


def _synthetic_spectrum(
    lambda_max: float = 450.0,
    absorbance_max: float = 1.2,
    n_points: int = 200,
    noise_level: float = 0.005,
) -> tuple[list, list]:
    """Generate synthetic UV-Vis absorption spectrum (Gaussian peak)."""
    wavelength = np.linspace(200, 800, n_points)
    absorbance = absorbance_max * np.exp(-0.5 * ((wavelength - lambda_max) / 30.0) ** 2)
    rng = np.random.default_rng(42)
    absorbance += noise_level * rng.normal(size=n_points)
    absorbance = np.maximum(absorbance, 0)
    return wavelength.tolist(), absorbance.tolist()


def _multi_peak_spectrum(
    peaks: list[tuple] | None = None,
    n_points: int = 300,
) -> tuple[list, list]:
    """Multiple absorption bands."""
    if peaks is None:
        peaks = [(280, 0.8, 15), (450, 1.2, 30)]  # (center, height, width)
    wavelength = np.linspace(200, 800, n_points)
    absorbance = np.zeros(n_points)
    for center, height, width in peaks:
        absorbance += height * np.exp(-0.5 * ((wavelength - center) / width) ** 2)
    return wavelength.tolist(), absorbance.tolist()


def _flat_spectrum(n_points: int = 100) -> tuple[list, list]:
    """Flat baseline spectrum (no absorption)."""
    wavelength = np.linspace(200, 800, n_points)
    absorbance = np.full(n_points, 0.01)
    return wavelength.tolist(), absorbance.tolist()


# -- Basic functionality ----------------------------------------------------


def test_uv_vis_lambda_max():
    wl, ab = _synthetic_spectrum(lambda_max=450.0)
    result = compute_uv_vis(wl, ab)
    assert abs(result["lambda_max_nm"] - 450.0) < 10.0


def test_uv_vis_absorbance_max():
    wl, ab = _synthetic_spectrum(absorbance_max=1.2)
    result = compute_uv_vis(wl, ab)
    assert abs(result["absorbance_max"] - 1.2) < 0.1


def test_uv_vis_peaks_detected():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert result["peak_count"] >= 1


def test_uv_vis_peak_wavelengths():
    wl, ab = _synthetic_spectrum(lambda_max=450.0)
    result = compute_uv_vis(wl, ab)
    peak_wls = [p["wavelength_nm"] for p in result["peaks"]]
    assert any(abs(w - 450.0) < 10 for w in peak_wls)


def test_uv_vis_multi_peaks():
    wl, ab = _multi_peak_spectrum()
    result = compute_uv_vis(wl, ab)
    assert result["peak_count"] >= 2


def test_uv_vis_wavelength_range():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert result["wavelength_range"]["min"] < result["wavelength_range"]["max"]


# -- Beer-Lambert law ---------------------------------------------------------


def test_uv_vis_molar_absorptivity():
    wl, ab = _synthetic_spectrum(absorbance_max=1.0)
    result = compute_uv_vis(wl, ab, concentration=0.001, path_length=1.0)
    assert result["molar_absorptivity"] is not None
    assert result["molar_absorptivity"] > 0


def test_uv_vis_molar_absorptivity_beer_lambert():
    """epsilon = A / (l * c)"""
    wl, ab = _synthetic_spectrum(absorbance_max=1.0)
    result = compute_uv_vis(wl, ab, concentration=0.001, path_length=1.0)
    # epsilon = 1.0 / (1.0 * 0.001) = 1000
    assert abs(result["molar_absorptivity"] - 1000.0) < 200


def test_uv_vis_no_concentration():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert result["molar_absorptivity"] is None


def test_uv_vis_different_path_length():
    wl, ab = _synthetic_spectrum(absorbance_max=1.0)
    r1 = compute_uv_vis(wl, ab, concentration=0.001, path_length=1.0)
    r2 = compute_uv_vis(wl, ab, concentration=0.001, path_length=2.0)
    # epsilon halves with doubled path length
    assert r1["molar_absorptivity"] > r2["molar_absorptivity"]


def test_uv_vis_molar_absorptivity_unit():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab, concentration=0.001)
    assert result["molar_absorptivity_unit"] == "L/(mol*cm)"


# -- Assumptions / uncertainty / validity ------------------------------------


def test_uv_vis_assumptions():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_uv_vis_uncertainty():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert "wavelength_accuracy" in result["uncertainty"]


def test_uv_vis_validity_domain():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert "conditions" in result["validity_domain"]


def test_uv_vis_transformations():
    wl, ab = _synthetic_spectrum()
    result = compute_uv_vis(wl, ab)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "uv_vis_spectroscopy"


# -- Edge cases ---------------------------------------------------------------


def test_uv_vis_too_few_points():
    with pytest.raises(ValueError, match="At least 10"):
        compute_uv_vis([200, 300, 400], [0.1, 0.2, 0.3])


def test_uv_vis_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_uv_vis(list(range(200, 800)), [0.1] * 50)


def test_uv_vis_invalid_path_length():
    wl, ab = _synthetic_spectrum()
    with pytest.raises(ValueError, match="positive"):
        compute_uv_vis(wl, ab, path_length=-1.0)


def test_uv_vis_custom_prominence():
    wl, ab = _synthetic_spectrum()
    r_low = compute_uv_vis(wl, ab, prominence=0.001)
    r_high = compute_uv_vis(wl, ab, prominence=0.5)
    assert r_low["peak_count"] >= r_high["peak_count"]
