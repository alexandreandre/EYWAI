"""
Case-specific modules for Solde de Tout Compte PDF generation
Each module handles one termination type
"""

from .demission import generate_demission_solde
from .rupture_conventionnelle import generate_rupture_conventionnelle_solde
from .licenciement import generate_licenciement_solde
from .retraite import generate_retraite_solde
from .fin_periode_essai import generate_fin_periode_essai_solde
from .generic import generate_generic_solde

__all__ = [
    "generate_demission_solde",
    "generate_rupture_conventionnelle_solde",
    "generate_licenciement_solde",
    "generate_retraite_solde",
    "generate_fin_periode_essai_solde",
    "generate_generic_solde",
]
