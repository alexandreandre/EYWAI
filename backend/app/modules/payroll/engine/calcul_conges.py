from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.calcul_conges")
# moteur_paie/calcul_conges.py

from .contexte import ContextePaie
from . import legal_constants as lc
from .iccp_arbitrage import (
    arbitrer_iccp_complet,
    calculer_maintien_horaire,
    lire_parametres_conges,
)
from .reference_remuneration import lire_brut_reference_depuis_cumuls
from typing import Dict, Any


def _lire_majoration_hs(contexte: ContextePaie) -> float:
    majoration_hs = None
    if hasattr(contexte, "get_bareme_value"):
        majoration_hs = contexte.get_bareme_value(
            "heures_supp",
            "regles_calcul_communes",
            "taux_majoration_par_defaut",
            "heures_supplementaires",
            0,
            "taux",
        )
    else:
        majoration_hs = (
            contexte.baremes.get("heures_supp", {})
            .get("regles_calcul_communes", {})
            .get("taux_majoration_par_defaut", {})
            .get("heures_supplementaires", [{}])[0]
            .get("taux")
        )
    if majoration_hs is None:
        return 0.0
    return float(majoration_hs)


def calculer_indemnite_conges(
    contexte: ContextePaie, nombre_jours_conges: int, salaire_horaire_base: float
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de congés payés en comparant les deux méthodes
    et en retournant la plus avantageuse pour le salarié, en tenant compte des HS structurelles.
    """
    log_payroll_debug(logger, "INFO: Démarrage du calcul de l'indemnité de congés payés...")

    params = lire_parametres_conges(getattr(contexte, "baremes", None))
    heures_normales_par_jour = lc.DUREE_LEGALE_HEBDO / 5
    heures_supp_structurelles_par_jour = (
        contexte.duree_hebdo_contrat - lc.DUREE_LEGALE_HEBDO
    ) / 5
    majoration_hs = _lire_majoration_hs(contexte)

    maintien = calculer_maintien_horaire(
        float(nombre_jours_conges),
        salaire_horaire_base,
        heures_normales_par_jour=heures_normales_par_jour,
        heures_supp_par_jour=heures_supp_structurelles_par_jour,
        majoration_hs=majoration_hs,
    )

    brut_reference_n_1 = lire_brut_reference_depuis_cumuls(contexte.cumuls)
    resultat = arbitrer_iccp_complet(
        float(nombre_jours_conges),
        maintien_horaire=maintien,
        base_reference_dixieme=brut_reference_n_1,
        taux_dixieme=params["taux_dixieme"],
        jours_reference_dixieme=params["jours_reference_dixieme"],
    )

    methode_retenue = (
        "1/10ème" if resultat.methode_retenue == "dixieme" else "Maintien"
    )

    log_payroll_debug(logger, '\n--- Arbitrage Indemnité Congés Payés ---')
    log_payroll_debug(logger, f"\tMéthode 'Maintien de salaire'  : {resultat.indemnite_maintien:10.2f} €")
    log_payroll_debug(logger, f"\tMéthode 'Règle du 1/10ème'     : {resultat.indemnite_dixieme:10.2f} €")
    log_payroll_debug(logger, '\t--------------------------------------------')
    log_payroll_debug(logger, f'\tMontant retenu (plus avantageux) : {resultat.montant_final:10.2f} € (Méthode: {methode_retenue})')
    log_payroll_debug(logger, '----------------------------------------\n')

    total_heures_absence_global = maintien.heures_normales + maintien.heures_hs

    return {
        "montant_retenue": resultat.indemnite_maintien,
        "montant_indemnite": resultat.montant_final,
        "indemnite_maintien_base": maintien.part_normale,
        "indemnite_maintien_hs": maintien.part_hs,
        "nombre_jours": nombre_jours_conges,
        "methode_retenue": methode_retenue,
        "total_heures_absence": total_heures_absence_global,
        "heures_base": maintien.heures_normales,
        "heures_hs": maintien.heures_hs,
    }
