"""
biology -- ScientificState domain module for biological analysis.

Provides PCR amplification, gel electrophoresis, and cell viability methods.

Entry point: scientificstate.domains -> biology
"""

from .domain_manifest import BiologyDomain

__all__ = ["BiologyDomain"]
__version__ = "0.1.0"
