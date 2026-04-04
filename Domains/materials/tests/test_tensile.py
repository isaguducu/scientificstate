"""Tensile test analysis tests — modulus, yield, UTS, elongation."""

import numpy as np
import pytest

from materials_science.methods.tensile import compute_tensile


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _synthetic_tensile(
    modulus: float = 200000.0,
    yield_stress: float = 300.0,
    uts: float = 500.0,
    elongation: float = 0.25,
    n_points: int = 200,
) -> tuple[list, list]:
    """Generate synthetic stress-strain curve.

    - Linear elastic region up to ~yield_stress/modulus strain
    - Hardening region up to UTS
    - Necking/softening to fracture
    """
    # Elastic region
    yield_strain = yield_stress / modulus
    n_elastic = int(n_points * 0.3)
    n_plastic = int(n_points * 0.5)
    n_necking = n_points - n_elastic - n_plastic

    strain_elastic = np.linspace(0, yield_strain, n_elastic, endpoint=False)
    stress_elastic = modulus * strain_elastic

    # Plastic hardening (power law)
    strain_plastic = np.linspace(yield_strain, elongation * 0.8, n_plastic, endpoint=False)
    t = (strain_plastic - yield_strain) / (elongation * 0.8 - yield_strain)
    stress_plastic = yield_stress + (uts - yield_stress) * t ** 0.5

    # Necking
    strain_necking = np.linspace(elongation * 0.8, elongation, n_necking)
    stress_necking = np.linspace(uts, uts * 0.7, n_necking)

    strain = np.concatenate([strain_elastic, strain_plastic, strain_necking])
    stress = np.concatenate([stress_elastic, stress_plastic, stress_necking])

    return strain.tolist(), stress.tolist()


def _linear_tensile(modulus: float = 100000.0, max_strain: float = 0.01) -> tuple[list, list]:
    """Purely linear stress-strain (ideal elastic material)."""
    strain = np.linspace(0, max_strain, 100)
    stress = modulus * strain
    return strain.tolist(), stress.tolist()


# ── Basic functionality ──────────────────────────────────────────────────────


def test_tensile_returns_modulus():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert result["youngs_modulus"] > 0
    assert result["youngs_modulus_unit"] == "MPa"


def test_tensile_modulus_near_expected():
    """Young's modulus should be close to the input modulus for synthetic data."""
    strain, stress = _synthetic_tensile(modulus=200000.0)
    # Elastic region is small (yield at ~0.0015), so restrict fit range
    result = compute_tensile(strain, stress, elastic_range_pct=0.001)
    assert abs(result["youngs_modulus"] - 200000.0) / 200000.0 < 0.10


def test_tensile_linear_modulus_exact():
    """Purely linear data → modulus matches exactly."""
    strain, stress = _linear_tensile(modulus=100000.0)
    result = compute_tensile(strain, stress, elastic_range_pct=0.01)
    assert abs(result["youngs_modulus"] - 100000.0) / 100000.0 < 0.001


def test_tensile_yield_strength_positive():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert result["yield_strength"] > 0


def test_tensile_yield_strength_reasonable():
    """Yield should be less than UTS."""
    strain, stress = _synthetic_tensile(yield_stress=300.0, uts=500.0)
    result = compute_tensile(strain, stress)
    assert result["yield_strength"] < result["ultimate_tensile_strength"]


def test_tensile_uts():
    strain, stress = _synthetic_tensile(uts=500.0)
    result = compute_tensile(strain, stress)
    assert result["ultimate_tensile_strength"] > 0
    assert result["uts_unit"] == "MPa"


def test_tensile_elongation_at_break():
    strain, stress = _synthetic_tensile(elongation=0.25)
    result = compute_tensile(strain, stress)
    assert abs(result["elongation_at_break"] - 0.25) < 0.01


def test_tensile_toughness_positive():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert result["toughness"] > 0
    assert result["toughness_unit"] == "MJ/m³"


def test_tensile_r_squared_high():
    """R² for elastic fit should be high on synthetic data."""
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress, elastic_range_pct=0.001)
    assert result["elastic_modulus_r_squared"] > 0.95


# ── Assumptions / uncertainty / validity ─────────────────────────────────────


def test_tensile_assumptions():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_tensile_uncertainty():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert "youngs_modulus" in result["uncertainty"]
    assert "std_error" in result["uncertainty"]["youngs_modulus"]


def test_tensile_validity_domain():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert "conditions" in result["validity_domain"]


def test_tensile_transformations():
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "tensile_test"


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_tensile_too_few_points():
    with pytest.raises(ValueError, match="At least 5"):
        compute_tensile([0, 0.01, 0.02], [0, 100, 200])


def test_tensile_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_tensile([0, 0.01, 0.02, 0.03, 0.04], [0, 100, 200])


def test_tensile_invalid_offset():
    strain, stress = _synthetic_tensile()
    with pytest.raises(ValueError, match="positive"):
        compute_tensile(strain, stress, offset_pct=-0.001)


def test_tensile_custom_offset():
    """Custom offset percentage is respected."""
    strain, stress = _synthetic_tensile()
    result = compute_tensile(strain, stress, offset_pct=0.005)
    assert result["yield_strength"] > 0
