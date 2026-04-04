"""Titration analysis tests -- equivalence point, pKa, concentration."""

import numpy as np
import pytest

from chemistry.methods.titration import compute_titration


# -- Fixtures ----------------------------------------------------------------


def _strong_acid_base(
    eq_volume: float = 25.0,
    n_points: int = 100,
    initial_ph: float = 2.0,
    final_ph: float = 12.0,
) -> tuple[list, list]:
    """Synthetic strong acid-base titration curve (sigmoid)."""
    volume = np.linspace(0, 50, n_points)
    # Sigmoidal: pH = initial + (final-initial) / (1 + exp(-k*(v - eq_volume)))
    k = 0.5
    ph = initial_ph + (final_ph - initial_ph) / (1.0 + np.exp(-k * (volume - eq_volume)))
    return volume.tolist(), ph.tolist()


def _weak_acid_titration(
    pka: float = 4.75,
    eq_volume: float = 20.0,
    n_points: int = 100,
) -> tuple[list, list]:
    """Synthetic weak acid titration (buffer region + equivalence)."""
    volume = np.linspace(0, 40, n_points)
    ph = np.zeros(n_points)
    for i, v in enumerate(volume):
        if v < eq_volume * 0.01:
            ph[i] = pka - 1.5
        elif v < eq_volume:
            # Henderson-Hasselbalch buffer region
            ratio = v / (eq_volume - v) if eq_volume - v > 0.01 else 100
            ph[i] = pka + np.log10(max(ratio, 1e-6))
        elif v < eq_volume * 1.01:
            ph[i] = 7.0 + 0.5 * (pka - 4.0)  # near neutral at eq
        else:
            # Excess titrant
            ph[i] = 10.0 + 2.0 * (v - eq_volume) / (40 - eq_volume)
    return volume.tolist(), ph.tolist()


def _linear_ph(n_points: int = 50) -> tuple[list, list]:
    """Perfectly linear pH (no real equivalence -- edge case)."""
    volume = np.linspace(0, 50, n_points)
    ph = np.linspace(3, 11, n_points)
    return volume.tolist(), ph.tolist()


# -- Basic functionality ----------------------------------------------------


def test_titration_equivalence_point():
    vol, ph = _strong_acid_base(eq_volume=25.0)
    result = compute_titration(vol, ph)
    assert result["equivalence_point_ml"] is not None
    assert abs(result["equivalence_point_ml"] - 25.0) < 5.0


def test_titration_ph_at_equivalence():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert 4.0 < result["ph_at_equivalence"] < 10.0


def test_titration_max_derivative():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert result["max_dpH_dV"] > 0


def test_titration_half_equivalence():
    vol, ph = _strong_acid_base(eq_volume=20.0)
    result = compute_titration(vol, ph)
    assert abs(result["half_equivalence_ml"] - 10.0) < 3.0


def test_titration_pka_estimate():
    vol, ph = _weak_acid_titration(pka=4.75)
    result = compute_titration(vol, ph)
    if result["pka_estimate"] is not None:
        assert 2.0 < result["pka_estimate"] < 8.0


def test_titration_analyte_concentration():
    vol, ph = _strong_acid_base(eq_volume=25.0)
    result = compute_titration(
        vol, ph,
        titrant_concentration=0.1,
        analyte_volume=25.0,
    )
    assert result["analyte_concentration_mol_l"] is not None
    # C_a = C_t * V_eq / V_a = 0.1 * 25 / 25 = 0.1
    assert abs(result["analyte_concentration_mol_l"] - 0.1) < 0.05


def test_titration_no_concentration_without_params():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert result["analyte_concentration_mol_l"] is None


def test_titration_curve():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert len(result["titration_curve"]) == len(vol)
    for point in result["titration_curve"]:
        assert "volume_ml" in point
        assert "ph" in point


def test_titration_volume_range():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert result["volume_range"]["min"] < result["volume_range"]["max"]


def test_titration_different_eq_volumes():
    """Different equivalence volumes detected correctly."""
    _, ph1 = _strong_acid_base(eq_volume=15.0)
    _, ph2 = _strong_acid_base(eq_volume=35.0)
    vol = np.linspace(0, 50, 100).tolist()
    r1 = compute_titration(vol, ph1)
    r2 = compute_titration(vol, ph2)
    assert r1["equivalence_point_ml"] < r2["equivalence_point_ml"]


# -- Assumptions / uncertainty / validity ------------------------------------


def test_titration_assumptions():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_titration_uncertainty():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert "equivalence_point" in result["uncertainty"]


def test_titration_validity_domain():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert "conditions" in result["validity_domain"]


def test_titration_transformations():
    vol, ph = _strong_acid_base()
    result = compute_titration(vol, ph)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "titration"


# -- Edge cases ---------------------------------------------------------------


def test_titration_too_few_points():
    with pytest.raises(ValueError, match="At least 5"):
        compute_titration([0, 10, 20], [3, 7, 11])


def test_titration_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_titration(list(range(50)), [3.0] * 20)


def test_titration_linear_ph():
    """Linear pH should still find an approximate equivalence."""
    vol, ph = _linear_ph()
    result = compute_titration(vol, ph)
    assert result["equivalence_point_ml"] is not None


def test_titration_unsorted_volume():
    """Should handle unsorted volume data."""
    vol, ph = _strong_acid_base()
    result = compute_titration(vol[::-1], ph[::-1])
    assert result["equivalence_point_ml"] is not None
