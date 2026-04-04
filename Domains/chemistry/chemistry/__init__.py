"""
chemistry -- ScientificState domain module for chemical analysis.

Provides UV-Vis spectroscopy, titration, and HPLC chromatography methods.

Entry point: scientificstate.domains -> chemistry
"""

from .domain_manifest import ChemistryDomain

__all__ = ["ChemistryDomain"]
__version__ = "0.1.0"
