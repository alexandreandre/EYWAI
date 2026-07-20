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
    # Base journalière "normale" du maintien : plafonnée à la durée légale pour
    # un temps plein/temps majoré (comportement historique inchangé), mais
    # PRORATÉE pour un temps partiel — sinon l'indemnité de CP d'un salarié à
    # temps partiel est calculée sur une journée légale (7 h) au lieu de sa
    # journée contractuelle réelle, la sur-évaluant fortement (cf. Cegid MBC
    # mai 2026 LIKA, temps partiel 20,08 h/sem ≈ 4 h/j : indemnité EYWAI sur 7
    # h/j au lieu de ~4,02 h/j, écart net +197,31 € alors que Cegid neutralise
    # exactement la retenue par l'indemnité). Même pattern que le repli
    # journalier d'absence (`_heures_journalieres_contrat`, `min(contrat,35)/5`).
    heures_normales_par_jour = (
        min(contexte.duree_hebdo_contrat, lc.DUREE_LEGALE_HEBDO) / 5
    )
    # Plafonnée à 0 : pour un temps partiel (contrat < légal), il n'existe pas
    # d'heures sup. structurelles à indemniser — sans ce plancher, la
    # soustraction devient NÉGATIVE et `calculer_maintien_horaire` (qui
    # calcule ensuite `part_normale = total - part_hs`) déduit un `part_hs`
    # négatif, ce qui GONFLE artificiellement `part_normale` (la ligne
    # réellement ajoutée au brut) bien au-dessus du total réel de l'indemnité
    # — même cas LIKA que ci-dessus, bug distinct découvert en creusant le
    # premier fix (le total `maintien.total` était déjà correct, seul le
    # découpage part_normale/part_hs affichée-et-utilisée-pour-le-brut était
    # faux).
    heures_supp_structurelles_par_jour = max(
        0.0, (contexte.duree_hebdo_contrat - lc.DUREE_LEGALE_HEBDO) / 5
    )
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
