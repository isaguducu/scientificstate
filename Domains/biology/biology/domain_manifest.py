"""
domain_manifest.py -- BiologyDomain entry point.

Implements scientificstate.DomainModule interface (registry.py).
Entry point group: scientificstate.domains
Entry point name:  biology

Methods:
  - pcr_amplification: Real-time qPCR analysis -- Ct, efficiency, threshold
  - gel_electrophoresis: Gel band detection -- sizes, intensities, ladder calibration
  - cell_viability: MTT/MTS assay -- viability %, IC50, dose-response
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from scientificstate.domain_registry import DomainModule


class MethodErrorCode(str, Enum):
    """Domain-level error codes for execute_method() responses."""

    UNKNOWN_METHOD = "UNKNOWN_METHOD"
    INVALID_PARAMS = "INVALID_PARAMS"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    DATA_REF_ERROR = "DATA_REF_ERROR"


class BiologyDomain(DomainModule):
    """
    ScientificState domain plugin for biological analysis.

    Provides:
      - PCR Amplification (Ct detection, efficiency, threshold crossing)
      - Gel Electrophoresis (band detection, size estimation, ladder calibration)
      - Cell Viability (MTT/MTS viability %, IC50, dose-response)

    Compute substrate: classical only (M1 milestone).
    """

    @property
    def domain_id(self) -> str:
        return "biology"

    @property
    def domain_name(self) -> str:
        return "Biology (PCR, Gel Electrophoresis, Cell Viability)"

    @property
    def supported_data_types(self) -> list[str]:
        return ["pcr_csv", "gel_csv", "gel_image", "viability_csv"]

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def taxonomy(self) -> dict | None:
        return {
            "field": "biology",
            "subfield": "molecular_biology",
            "specialization": "pcr_gel_viability",
        }

    # -- DomainModule.list_methods ------------------------------------------

    def list_methods(self) -> list[dict]:
        """Return method manifests aligned with MethodManifest schema."""
        return [
            {
                "method_id": "pcr_amplification",
                "domain_id": self.domain_id,
                "name": "PCR Amplification Analysis",
                "description": "Real-time qPCR: Ct detection, amplification efficiency, threshold",
                "required_data_types": ["pcr_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "gel_electrophoresis",
                "domain_id": self.domain_id,
                "name": "Gel Electrophoresis Band Analysis",
                "description": "Band detection, size estimation via ladder calibration, quantification",
                "required_data_types": ["gel_csv", "gel_image"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "cell_viability",
                "domain_id": self.domain_id,
                "name": "Cell Viability Assay",
                "description": "MTT/MTS: viability percentage, IC50, dose-response analysis",
                "required_data_types": ["viability_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
        ]

    # -- DomainModule.execute_method ----------------------------------------

    def execute_method(
        self,
        method_id: str,
        data_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        """Execute a biology method and return a result dict."""
        dispatch = {
            "pcr_amplification": self._execute_pcr,
            "gel_electrophoresis": self._execute_gel,
            "cell_viability": self._execute_viability,
        }

        fn = dispatch.get(method_id)
        if fn is None:
            msg = (
                f"Unknown method_id: {method_id!r}. "
                f"Available: {list(dispatch.keys())}"
            )
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.UNKNOWN_METHOD,
                "error": msg,
                "diagnostics": {},
            }

        # Optionally inject data from data_ref
        if data_ref:
            params = self._merge_data_ref(data_ref, method_id, params)

        try:
            result = fn(data_ref, assumptions, params)
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "ok",
                "result": result,
                "diagnostics": {},
            }
        except ValueError as exc:
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.INVALID_PARAMS,
                "error": str(exc),
                "diagnostics": {},
            }
        except Exception as exc:
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.EXECUTION_ERROR,
                "error": str(exc),
                "diagnostics": {},
            }

    # -- Data-ref helpers ---------------------------------------------------

    def _load_data_ref(self, data_ref: str) -> dict | list | None:
        """Load a CSV or JSON file referenced by data_ref."""
        path = Path(data_ref)
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        if suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        if suffix == ".csv":
            import numpy as np

            data = np.genfromtxt(path, delimiter=",", names=True)
            return {name: data[name].tolist() for name in data.dtype.names}
        return None

    def _merge_data_ref(self, data_ref: str, method_id: str, params: dict) -> dict:
        """Inject data from data_ref when expected param key is absent."""
        _param_keys = {
            "pcr_amplification": "cycles",
            "gel_electrophoresis": "distances",
            "cell_viability": "concentrations",
        }

        try:
            loaded = self._load_data_ref(data_ref)
        except Exception:
            return params

        if loaded is None:
            return params

        params = dict(params)
        key = _param_keys.get(method_id)
        if key and key not in params and isinstance(loaded, dict):
            params.update(loaded)
        return params

    # -- Private dispatch helpers -------------------------------------------

    def _execute_pcr(self, data_ref: str, assumptions: list, params: dict) -> dict:
        cycles = params.get("cycles")
        fluorescence = params.get("fluorescence")
        if cycles is None or fluorescence is None:
            raise ValueError(
                "params['cycles'] and params['fluorescence'] are required for pcr_amplification."
            )
        from .methods.pcr import compute_pcr

        return compute_pcr(
            cycles=cycles,
            fluorescence=fluorescence,
            threshold=params.get("threshold"),
            baseline_cycles=params.get("baseline_cycles", 5),
        )

    def _execute_gel(self, data_ref: str, assumptions: list, params: dict) -> dict:
        distances = params.get("distances")
        intensities = params.get("intensities")
        if distances is None or intensities is None:
            raise ValueError(
                "params['distances'] and params['intensities'] are required for gel_electrophoresis."
            )
        from .methods.gel_electrophoresis import compute_gel_electrophoresis

        return compute_gel_electrophoresis(
            distances=distances,
            intensities=intensities,
            ladder_distances=params.get("ladder_distances"),
            ladder_sizes=params.get("ladder_sizes"),
            min_prominence=params.get("min_prominence", 0.05),
        )

    def _execute_viability(self, data_ref: str, assumptions: list, params: dict) -> dict:
        concentrations = params.get("concentrations")
        absorbances = params.get("absorbances")
        if concentrations is None or absorbances is None:
            raise ValueError(
                "params['concentrations'] and params['absorbances'] are required for cell_viability."
            )
        from .methods.cell_viability import compute_cell_viability

        return compute_cell_viability(
            concentrations=concentrations,
            absorbances=absorbances,
            control_absorbance=params.get("control_absorbance"),
            blank_absorbance=params.get("blank_absorbance", 0.0),
        )
