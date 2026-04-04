"""
SSV Comparison — field-level comparison of two SSV dicts for replication.

Compares the R (results) component of source and target SSVs and reports
whether they match within specified tolerances.

Pure function: no I/O, no side effects.
"""
from __future__ import annotations

import math


class SSVComparison:
    """Compare two SSV dicts for replication verification."""

    def __init__(self, tolerance: dict | None = None) -> None:
        tol = tolerance or {}
        self._abs_tol: float = tol.get("absolute", 1e-6)
        self._rel_tol: float = tol.get("relative", 1e-4)

    def compare(self, source: dict, target: dict) -> dict:
        """Compare source and target SSV dicts.

        Args:
            source: SSV dict from the original claim.
            target: SSV dict from the replication run.

        Returns:
            Comparison report dict with status, result_match, tolerance_used,
            differences, and confidence.
        """
        differences: list[dict] = []

        # Compare R (results) component — lowercase field names per SSV convention
        source_r = source.get("r", {})
        target_r = target.get("r", {})

        source_quantities = source_r.get("quantities", source_r)
        target_quantities = target_r.get("quantities", target_r)

        self._compare_dicts(source_quantities, target_quantities, "r", differences)

        # Compare T (transformation) component — method should match
        source_t = source.get("t", [])
        target_t = target.get("t", [])
        if source_t and target_t:
            if isinstance(source_t, list) and isinstance(target_t, list):
                if len(source_t) > 0 and len(target_t) > 0:
                    s_method = source_t[0].get("algorithm", "")
                    t_method = target_t[0].get("algorithm", "")
                    if s_method and t_method and s_method != t_method:
                        differences.append({
                            "field": "t.algorithm",
                            "source": s_method,
                            "target": t_method,
                            "type": "method_mismatch",
                        })

        result_match = len(differences) == 0
        max_fields = max(len(source_quantities), 1) if isinstance(source_quantities, dict) else 1
        confidence = max(0.0, 1.0 - (len(differences) / max_fields))

        if result_match:
            status = "confirmed"
        elif confidence >= 0.5:
            status = "partially_confirmed"
        else:
            status = "not_confirmed"

        return {
            "status": status,
            "result_match": result_match,
            "tolerance_used": {
                "absolute": self._abs_tol,
                "relative": self._rel_tol,
            },
            "differences": differences,
            "confidence": confidence,
        }

    def _compare_dicts(
        self,
        source: dict | object,
        target: dict | object,
        prefix: str,
        differences: list[dict],
    ) -> None:
        """Recursively compare two dicts, recording differences."""
        if not isinstance(source, dict) or not isinstance(target, dict):
            if source != target:
                if isinstance(source, (int, float)) and isinstance(target, (int, float)):
                    if not self._within_tolerance(source, target):
                        differences.append({
                            "field": prefix,
                            "source": source,
                            "target": target,
                            "type": "numeric_mismatch",
                        })
                else:
                    differences.append({
                        "field": prefix,
                        "source": source,
                        "target": target,
                        "type": "value_mismatch",
                    })
            return

        all_keys = set(source.keys()) | set(target.keys())
        for key in sorted(all_keys):
            field_path = f"{prefix}.{key}" if prefix else key
            s_val = source.get(key)
            t_val = target.get(key)

            if key not in source:
                differences.append({
                    "field": field_path,
                    "source": None,
                    "target": t_val,
                    "type": "missing_in_source",
                })
            elif key not in target:
                differences.append({
                    "field": field_path,
                    "source": s_val,
                    "target": None,
                    "type": "missing_in_target",
                })
            elif isinstance(s_val, dict) and isinstance(t_val, dict):
                self._compare_dicts(s_val, t_val, field_path, differences)
            elif isinstance(s_val, (int, float)) and isinstance(t_val, (int, float)):
                if not self._within_tolerance(s_val, t_val):
                    differences.append({
                        "field": field_path,
                        "source": s_val,
                        "target": t_val,
                        "type": "numeric_mismatch",
                    })
            elif s_val != t_val:
                differences.append({
                    "field": field_path,
                    "source": s_val,
                    "target": t_val,
                    "type": "value_mismatch",
                })

    def _within_tolerance(self, a: float, b: float) -> bool:
        """Check if two numbers match within absolute or relative tolerance."""
        if math.isclose(a, b, abs_tol=self._abs_tol):
            return True
        if b != 0 and abs((a - b) / b) <= self._rel_tol:
            return True
        if a != 0 and abs((a - b) / a) <= self._rel_tol:
            return True
        return False
