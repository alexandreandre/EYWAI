# Domain layer for repos_compensateur.

from app.modules.repos_compensateur.domain.entities import ReposCredit
from app.modules.repos_compensateur.domain.enums import SourceCredit
from app.modules.repos_compensateur.domain.rules import (
    CONTINGENT_DEFAUT,
    HEURES_PAR_JOUR_REPOS,
    calculer_heures_cor_mois,
    cumuler_heures_hs_annee,
    extraire_heures_hs_du_bulletin,
    get_taux_cor_par_effectif,
    heures_vers_jours,
)

__all__ = [
    "ReposCredit",
    "SourceCredit",
    "CONTINGENT_DEFAUT",
    "HEURES_PAR_JOUR_REPOS",
    "calculer_heures_cor_mois",
    "cumuler_heures_hs_annee",
    "extraire_heures_hs_du_bulletin",
    "get_taux_cor_par_effectif",
    "heures_vers_jours",
]
