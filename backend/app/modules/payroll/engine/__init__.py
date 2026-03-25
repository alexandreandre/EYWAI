# Moteur de calcul de paie (règles de calcul, formules, moteur de paie).
# Migré depuis backend_calculs/moteur_paie. Réexport pour usage interne au module.

from app.modules.payroll.engine.contexte import ContextePaie, ChargerContexte
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.bulletin import (
    creer_bulletin_final,
    creer_bulletin_sortie,
)
from app.modules.payroll.engine.calcul_conges import calculer_indemnite_conges
from app.modules.payroll.engine.calcul_absences import calculer_deduction_absence
from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnites_sortie,
)
from app.modules.payroll.engine.calcul_inverse import (
    calculer_brut_depuis_net,
    CalculInverseError,
    NonConvergenceError,
)
from app.modules.payroll.engine.analyser_jours_forfait import (
    analyser_jours_forfait_du_mois,
)
from app.modules.payroll.engine.period_forfait import definir_periode_de_paie
from app.modules.payroll.engine.analyser_horaires import analyser_horaires_du_mois
from app.modules.payroll.engine.simulation import (
    creer_simulation_bulletin,
    comparer_simulation_reel,
    generer_scenarios_predefinis,
)
from app.modules.payroll.engine.calculT import calculer_parametre_T
from app.modules.payroll.engine.idcc import (
    obtenir_token,
    rechercher_textes_kali,
    main as idcc_main,
    IDCC_A_TESTER,
    URL_TOKEN,
    URL_API_LEGIFRANCE,
)

__all__ = [
    "ContextePaie",
    "ChargerContexte",
    "calculer_salaire_brut",
    "calculer_salaire_brut_forfait",
    "calculer_cotisations",
    "calculer_net_et_impot",
    "calculer_reduction_generale",
    "creer_bulletin_final",
    "creer_bulletin_sortie",
    "calculer_indemnite_conges",
    "calculer_deduction_absence",
    "calculer_indemnites_sortie",
    "calculer_brut_depuis_net",
    "CalculInverseError",
    "NonConvergenceError",
    "analyser_jours_forfait_du_mois",
    "definir_periode_de_paie",
    "analyser_horaires_du_mois",
    "creer_simulation_bulletin",
    "comparer_simulation_reel",
    "generer_scenarios_predefinis",
    "calculer_parametre_T",
    "obtenir_token",
    "rechercher_textes_kali",
    "idcc_main",
    "IDCC_A_TESTER",
    "URL_TOKEN",
    "URL_API_LEGIFRANCE",
]
