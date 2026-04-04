"""
materials_science — ScientificState domain module for materials characterization.

Provides XRD, tensile testing, and DSC thermal analysis methods.

Entry point: scientificstate.domains → materials_science
"""

from .domain_manifest import MaterialsScienceDomain

__all__ = ["MaterialsScienceDomain"]
__version__ = "0.1.0"
