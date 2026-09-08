"""
Types / énumérations du domaine employee_exits.

Alignés sur app.modules.employee_exits.schemas.requests (ExitType, ExitStatus, etc.).
Définis ici pour le domain ; les schémas API réutilisent les mêmes Literal.
"""

from typing import Literal

ExitType = Literal[
    "demission",
    "rupture_conventionnelle",
    "licenciement",
    "depart_retraite",
    "fin_periode_essai",
    # Fin de contrat à durée déterminée : STC avec indemnité de précarité
    # (portée par le BULLETIN du dernier mois) + ICCP.
    "fin_cdd",
    # Mutation intra-groupe : sortie purement administrative — jamais de STC,
    # d'indemnités ni de documents (solde CP et ancienneté conservés).
    "transfert",
]
ExitStatus = Literal[
    "demission_recue",
    "demission_preavis_en_cours",
    "demission_effective",
    "rupture_en_negociation",
    "rupture_validee",
    "rupture_homologuee",
    "rupture_effective",
    "licenciement_convocation",
    "licenciement_notifie",
    "licenciement_preavis_en_cours",
    "licenciement_effective",
    "archivee",
    "annulee",
]
ChecklistCategory = Literal["administratif", "materiel", "acces", "legal", "autre"]
DocumentCategory = Literal["uploaded", "generated"]
