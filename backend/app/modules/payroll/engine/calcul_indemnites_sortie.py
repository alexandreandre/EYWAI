"""
Module de calcul des indemnités de sortie selon le droit du travail français

Calcule:
- Indemnité de préavis
- Congés payés restants
- Indemnité de licenciement (Article L1234-9)
- Indemnité de rupture conventionnelle
"""
from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.calcul_indemnites_sortie")

from calendar import monthrange
from typing import Any, Dict, Optional
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.modules.payroll.engine.cp_solde_sortie import get_cp_solde_a_la_sortie
from app.modules.payroll.engine.iccp_arbitrage import (
    arbitrer_iccp_complet,
    lire_parametres_conges,
)
from app.modules.payroll.engine.iccp_fin_contrat import (
    PeriodeConges,
    indemnite_fin_de_contrat,
    valeur_jour_maintien,
)
from app.modules.payroll.engine.preavis import (
    JOURS_PAR_MOIS,
    ajouter_les_conges_du_preavis,
    conges_du_preavis_non_execute,
    indemnite_compensatrice_due,
    jours_de_preavis_restants,
    phrase_execution_preavis,
)
from app.modules.payroll.engine.regime_indemnites_rupture import (
    LICENCIEMENT,
    MISE_A_LA_RETRAITE,
    RUPTURE_CONVENTIONNELLE,
    ventiler_indemnite_de_rupture,
)
from app.modules.payroll.engine.reference_remuneration import (
    calculer_base_reference_dixieme,
    estimer_extras_fin_contrat,
    lire_brut_reference_depuis_cumuls,
    lire_brut_total_contrat,
)
from app.modules.payroll.engine.salaire_reference_sortie import (
    calculer_salaire_de_reference,
    lire_mois_de_salaire,
)
from app.modules.payroll.engine.salaire_contractuel import (
    heures_mensuelles_legales,
    heures_sup_structurelles_mensuelles,
    salaire_contractuel_total_hors_hs_mode,
    salaire_hors_hs_structurelles,
)


def _euros(valeur: float) -> str:
    """12712.27 → « 12 712,27 € » (texte visible)."""
    return f"{float(valeur):,.2f} €".replace(",", " ").replace(".", ",")


def _nombre(valeur: float) -> str:
    """1.66 → « 1,66 »."""
    return f"{float(valeur):.2f}".replace(".", ",")


# ============================================================================
# CALCULS DE BASE
# ============================================================================


def calculer_anciennete_annees(hire_date: date, exit_date: date) -> float:
    """
    Calcule l'ancienneté en années (avec décimales)

    Args:
        hire_date: Date d'embauche
        exit_date: Date de sortie

    Returns:
        Ancienneté en années décimales
    """
    delta = relativedelta(exit_date, hire_date)
    years = delta.years
    months = delta.months
    days = delta.days

    # Convertir en années décimales
    anciennete = years + (months / 12) + (days / 365)

    log_payroll_debug(logger, f'  Ancienneté: {years} ans, {months} mois, {days} jours = {anciennete:.2f} ans')

    return round(anciennete, 2)


def calculer_salaire_reference_12_mois(employee_data: Dict[str, Any]) -> float:
    """
    Calcule le salaire de référence sur les 12 derniers mois

    Pour une implémentation complète, il faudrait:
    - Récupérer les 12 derniers bulletins de paie
    - Calculer la moyenne du brut
    - Inclure primes annuelles, 13ème mois, etc.

    Pour l'instant, utilise le salaire de base
    """
    salaire_base_obj = employee_data.get("salaire_de_base", {})

    if isinstance(salaire_base_obj, dict):
        salaire_base = salaire_base_obj.get("valeur", 0)
    else:
        salaire_base = salaire_base_obj or 0

    # TODO: Implémenter le calcul réel à partir des bulletins
    return float(salaire_base)


def calculer_salaire_reference_3_mois(employee_data: Dict[str, Any]) -> float:
    """
    Calcule le salaire de référence sur les 3 derniers mois

    Pour une implémentation complète, il faudrait:
    - Récupérer les 3 derniers bulletins de paie
    - Calculer la moyenne du brut

    Pour l'instant, utilise le salaire de base
    """
    salaire_base_obj = employee_data.get("salaire_de_base", {})

    if isinstance(salaire_base_obj, dict):
        salaire_base = salaire_base_obj.get("valeur", 0)
    else:
        salaire_base = salaire_base_obj or 0

    return float(salaire_base)


# ============================================================================
# INDEMNITÉ DE PRÉAVIS
# ============================================================================


def calculer_indemnite_preavis(
    remuneration_mensuelle: float,
    notice_period_days: int,
    notice_indemnity_type: str,
    *,
    jours_restants: Optional[int] = None,
    source_remuneration: str = "",
    is_gross_misconduct: bool = False,
) -> Dict[str, Any]:
    """
    Indemnité compensatrice de préavis (Code du travail L1234-5, cf. engine/preavis).

    Due seulement quand l'employeur dispense le salarié de son préavis
    (« paid ») : elle vaut la rémunération qu'il aurait perçue, pour le temps
    de préavis qui restait après son dernier jour travaillé. Un préavis
    exécuté (« executed ») est payé avec le salaire du mois ; une dispense
    demandée par le salarié (« waived ») ne donne rien.

    Args:
        remuneration_mensuelle: rémunération mensuelle qu'il aurait perçue
        notice_period_days: durée du préavis, en jours
        notice_indemnity_type: 'executed', 'paid', 'waived', 'not_applicable'
        jours_restants: jours de préavis non exécutés (défaut : toute la durée)
        source_remuneration: d'où vient la rémunération, pour le détail affiché
    """
    log_payroll_debug(logger, '\n  [PRÉAVIS]')
    log_payroll_debug(logger, f'    Rémunération mensuelle: {remuneration_mensuelle:.2f} €')
    log_payroll_debug(logger, f'    Jours de préavis: {notice_period_days}')
    log_payroll_debug(logger, f'    Type: {notice_indemnity_type}')

    jours = notice_period_days if jours_restants is None else jours_restants
    if (
        not indemnite_compensatrice_due(notice_indemnity_type, faute_grave=is_gross_misconduct)
        or not notice_period_days
        or jours <= 0
    ):
        return {
            "montant": 0.0,
            "jours_preavis": notice_period_days,
            "type": notice_indemnity_type,
            "description": "Indemnité de préavis",
            "calcul": phrase_execution_preavis(
                notice_indemnity_type if notice_period_days else None
            ),
        }

    indemnite = round(remuneration_mensuelle / JOURS_PAR_MOIS * jours, 2)
    log_payroll_debug(logger, f'    Indemnité: ({remuneration_mensuelle} / 30) × {jours} = {indemnite:.2f} €')
    origine = f" ({source_remuneration})" if source_remuneration else ""
    return {
        "montant": indemnite,
        "jours_preavis": notice_period_days,
        "jours_restants": jours,
        "salaire_reference": round(remuneration_mensuelle, 2),
        "type": notice_indemnity_type,
        "description": f"Indemnité compensatrice de préavis ({jours} jours non exécutés)",
        "calcul": (
            f"Rémunération qu'il aurait perçue : {_euros(remuneration_mensuelle)} par mois"
            f"{origine} / 30 × {jours} jours de préavis restant = {_euros(indemnite)}"
        ),
    }


def _rythme_des_conges(employee_data: Dict[str, Any]) -> tuple[float, int]:
    """(jours acquis par mois, mois de début de la période de référence) de la
    société ; à défaut 2,5 jours ouvrables et juin, les valeurs par défaut de
    la politique de congés (absences.domain.leave_policy)."""
    company_id = employee_data.get("company_id")
    if company_id:
        try:
            from app.modules.absences.infrastructure.leave_settings_repository import (
                get_leave_policy,
            )

            politique = get_leave_policy(str(company_id))
            return (
                float(politique.cp_acquisition_days_per_month),
                int(politique.cp_reference_period_start_month),
            )
        except Exception:
            logger.warning("Politique de congés illisible (%s)", company_id, exc_info=True)
    return 2.5, 6


def _jours_fr(valeur: float) -> str:
    return f"{float(valeur):g}".replace(".", ",")


def poser_les_conges_du_preavis(
    bloc: Dict[str, Any], employee_data: Dict[str, Any], dernier_jour: date
) -> Dict[str, Any]:
    """Préavis (ou délai de prévenance) non exécuté et indemnisé : les congés que
    le salarié aurait acquis jusqu'à sa fin théorique, et l'indemnité, comptés
    dans l'indemnité de congés de la sortie (L1234-5 : « indemnité de congés
    payés comprise » ; L1221-25 pour le délai de prévenance)."""
    montant = float(bloc.get("montant") or 0.0)
    jours = int(bloc.get("jours_restants") or 0)
    if montant <= 0 or jours <= 0:
        return bloc
    acquisition, debut_periode = _rythme_des_conges(employee_data)
    parts = conges_du_preavis_non_execute(
        dernier_jour_travaille=dernier_jour,
        fin_du_preavis=dernier_jour + timedelta(days=jours),
        indemnite=montant,
        acquisition_par_mois=acquisition,
        mois_debut_periode=debut_periode,
    )
    if not parts:
        return bloc
    total = round(sum(p.jours for p in parts), 2)
    bloc = dict(bloc)
    bloc["conges_du_preavis"] = [p.en_dict() for p in parts]
    bloc["calcul"] = (
        f"{bloc.get('calcul') or ''}. Congés acquis pendant ce temps non exécuté : "
        f"{_jours_fr(total)} jours, indemnisés avec les congés payés, et l'indemnité entre dans "
        "l'assiette du dixième (L1234-5)."
    )
    return bloc


def _remuneration_du_preavis(
    employee_data: Dict[str, Any], exit_date: date, supabase_client
) -> tuple[float, str, list[str]]:
    """La rémunération qu'aurait perçue le salarié pendant son préavis : le
    tiers des trois derniers mois de bulletins (heures structurelles, heures
    supplémentaires et primes comprises, primes annuelles à due proportion) ;
    sans bulletin, le salaire habituel du contrat."""
    salaire_base = _parse_salaire_base(employee_data)
    habituel, _, _ = _salaire_habituel_et_taux_horaire(employee_data, salaire_base)
    mois: list = []
    employee_id = employee_data.get("id")
    if employee_id and supabase_client is not None:
        try:
            mois = lire_mois_de_salaire(str(employee_id), exit_date, supabase_client, nombre=3)
        except Exception:
            logger.warning("Bulletins illisibles pour le préavis (%s)", employee_id, exc_info=True)
            mois = []
    # Trois mois suffisent ici : la moyenne de douze mois sert à l'indemnité
    # de licenciement, pas à ce que le salarié aurait gagné pendant son préavis.
    reference = calculer_salaire_de_reference(
        mois, repli_contrat=habituel, mois_d_anciennete=3, avant_l_arret=False
    )
    if reference.tiers_trois_mois is None:
        return reference.retenu, "salaire habituel du contrat, aucun bulletin lu", list(reference.alertes)
    return (
        reference.tiers_trois_mois,
        f"tiers des {reference.mois_lus} derniers bulletins",
        list(reference.alertes),
    )


# ============================================================================
# INDEMNITÉ DE LICENCIEMENT
# ============================================================================


def calculer_indemnite_licenciement(
    anciennete_annees: float,
    salaire_reference: float,
    is_gross_misconduct: bool = False,
    *,
    mois_a_la_notification: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calcule l'indemnité légale de licenciement selon le Code du travail français

    Article L1234-9 du Code du travail (2025):
    - Faute grave/lourde: pas d'indemnité
    - < 8 mois d'ancienneté: pas d'indemnité
    - >= 8 mois:
        * 1/4 de mois de salaire par année d'ancienneté (10 premières années)
        * 1/3 de mois de salaire par année au-delà de 10 ans

    Args:
        anciennete_annees: Ancienneté en années
        salaire_reference: Salaire de référence (moyenne 12 ou 3 derniers mois)
        is_gross_misconduct: Faute grave ou lourde

    Returns:
        Dict contenant le montant et les détails du calcul
    """
    log_payroll_debug(logger, '\n  [LICENCIEMENT]')
    log_payroll_debug(logger, f'    Ancienneté: {anciennete_annees:.2f} ans')
    log_payroll_debug(logger, f'    Salaire référence: {salaire_reference:.2f} €')
    log_payroll_debug(logger, f'    Faute grave: {is_gross_misconduct}')

    if is_gross_misconduct:
        return {
            "montant": 0.0,
            "anciennete": anciennete_annees,
            "description": "Indemnité de licenciement",
            "calcul": "Faute grave/lourde - pas d'indemnité",
            "motif": "Faute grave/lourde",
        }

    # Les 8 mois s'apprécient à la notification (service-public F987) ; le
    # montant, à la fin du préavis (L1234-4).
    mois_requis = (
        mois_a_la_notification if mois_a_la_notification is not None else anciennete_annees * 12
    )
    if mois_requis < 8:  # Moins de 8 mois
        return {
            "montant": 0.0,
            "anciennete": anciennete_annees,
            "description": "Indemnité de licenciement",
            "calcul": "Ancienneté insuffisante (< 8 mois)",
            "motif": "Ancienneté < 8 mois",
        }

    # Calcul pour les 10 premières années: 1/4 de mois par an
    annees_tranche1 = min(anciennete_annees, 10)
    indemnite_tranche1 = (salaire_reference * annees_tranche1) / 4

    log_payroll_debug(logger, f'    Tranche 1 (≤10 ans): {annees_tranche1:.2f} ans × 1/4 = {indemnite_tranche1:.2f} €')

    # Calcul au-delà de 10 ans: 1/3 de mois par an
    indemnite_tranche2 = 0.0
    annees_tranche2 = 0.0

    if anciennete_annees > 10:
        annees_tranche2 = anciennete_annees - 10
        indemnite_tranche2 = (salaire_reference * annees_tranche2) / 3
        log_payroll_debug(logger, f'    Tranche 2 (>10 ans): {annees_tranche2:.2f} ans × 1/3 = {indemnite_tranche2:.2f} €')

    indemnite_totale = indemnite_tranche1 + indemnite_tranche2

    log_payroll_debug(logger, f'    TOTAL: {indemnite_totale:.2f} €')

    return {
        "montant": round(indemnite_totale, 2),
        "anciennete": anciennete_annees,
        "salaire_reference": salaire_reference,
        "tranche1_annees": annees_tranche1,
        "tranche1_montant": round(indemnite_tranche1, 2),
        "tranche2_annees": annees_tranche2,
        "tranche2_montant": round(indemnite_tranche2, 2),
        "description": "Indemnité légale de licenciement (Article L1234-9)",
        "calcul": f"Tranche 1 : {_nombre(annees_tranche1)} ans × 1/4 de mois ({_euros(indemnite_tranche1)})"
        + (
            f" + tranche 2 : {_nombre(annees_tranche2)} ans × 1/3 de mois ({_euros(indemnite_tranche2)})"
            if annees_tranche2 > 0
            else ""
        )
        + f", sur un salaire de référence de {_euros(salaire_reference)}",
    }


# ============================================================================
# INDEMNITÉ DE RUPTURE CONVENTIONNELLE
# ============================================================================


def calculer_indemnite_rupture_conventionnelle(
    anciennete_annees: float,
    salaire_reference: float,
    montant_negocie_saisi: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de rupture conventionnelle

    Minimum légal = indemnité légale de licenciement
    En pratique, souvent négociée au-dessus du minimum : le montant de la
    convention, saisi sur le départ, remplace alors le minimum.

    Args:
        anciennete_annees: Ancienneté en années
        salaire_reference: Salaire de référence
        montant_negocie_saisi: Montant de la convention, ou None

    Returns:
        Dict contenant le montant minimum et les détails
    """
    log_payroll_debug(logger, '\n  [RUPTURE CONVENTIONNELLE]')

    # Minimum légal = indemnité légale de licenciement ; sous 8 mois
    # d'ancienneté, la même formule au prorata des mois de présence (BOSS,
    # Indemnités de rupture, § 870 et § 1010 : salaire × 1/4 × mois / 12).
    indemnite_licenciement = calculer_indemnite_licenciement(
        anciennete_annees, salaire_reference, is_gross_misconduct=False, mois_a_la_notification=8
    )

    montant_minimum = indemnite_licenciement["montant"]
    alertes: list[str] = []
    if montant_negocie_saisi is None:
        montant_negocie = montant_minimum
        calcul = f"Minimum légal = {montant_minimum:.2f} € (indemnité de licenciement)"
    else:
        montant_negocie = round(float(montant_negocie_saisi), 2)
        calcul = (
            f"Montant de la convention saisi : {montant_negocie:.2f} € "
            f"(minimum légal estimé : {montant_minimum:.2f} €)"
        )
        if montant_negocie < montant_minimum:
            alertes.append(
                f"Montant de la convention ({montant_negocie:.2f} €) inférieur au minimum légal "
                f"({montant_minimum:.2f} €) : la convention ne peut pas descendre sous l'indemnité "
                "légale de licenciement, ni sous l'indemnité conventionnelle si elle est plus "
                "élevée (BOSS, Indemnités de rupture, § 840 à 860)."
            )

    log_payroll_debug(logger, f'    Minimum légal: {montant_minimum:.2f} € (= indemnité licenciement)')
    log_payroll_debug(logger, f'    Montant négocié: {montant_negocie:.2f} €')

    return {
        "montant_minimum": montant_minimum,
        "montant_negocie": montant_negocie,
        "montant_negocie_saisi": montant_negocie_saisi,
        "anciennete": anciennete_annees,
        "salaire_reference": salaire_reference,
        "description": "Indemnité de rupture conventionnelle",
        "calcul": calcul,
        "details_licenciement": indemnite_licenciement,
        "alertes": alertes,
    }


def _montant_negocie_saisi(exit_data: Dict[str, Any]) -> Optional[float]:
    """Le montant de la convention saisi sur le départ.

    Une saisie nouvelle (`montant_negocie`, None pour l'effacer) l'emporte ;
    sinon celle du dossier précédent, pour qu'un recalcul ne la perde pas.
    """
    if "montant_negocie" in exit_data:
        valeur = exit_data.get("montant_negocie")
    else:
        precedent = (exit_data.get("calculated_indemnities") or {}).get(
            "indemnite_rupture_conventionnelle"
        ) or {}
        valeur = precedent.get("montant_negocie_saisi")
    return None if valeur is None else float(valeur)


# ============================================================================
# CONGÉS PAYÉS RESTANTS
# ============================================================================


def _date_ou_none(valeur: Any) -> Optional[date]:
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _parse_salaire_base(employee_data: Dict[str, Any]) -> float:
    salaire_base_obj = employee_data.get("salaire_de_base", {})
    if isinstance(salaire_base_obj, dict):
        return float(salaire_base_obj.get("valeur", 0) or 0)
    return float(salaire_base_obj or 0)


def _est_cdd(employee_data: Dict[str, Any]) -> bool:
    contract = (
        employee_data.get("contract_type")
        or employee_data.get("type_contrat")
        or ""
    )
    return str(contract).upper() in {"CDD", "CONTRAT A DUREE DETERMINEE"}


def _est_interim(employee_data: Dict[str, Any]) -> bool:
    contract = (
        employee_data.get("contract_type")
        or employee_data.get("type_contrat")
        or ""
    )
    return "INTERIM" in str(contract).upper() or "INTÉRIM" in str(contract).upper()


def _charger_baremes_paie(supabase_client) -> dict:
    from app.modules.payroll.engine.baremes_loader import (
        assembler_baremes,
        charger_conventions_collectives,
        charger_db_baremes,
    )

    db_baremes = charger_db_baremes(supabase_client)
    conventions = charger_conventions_collectives(supabase_client)
    return assembler_baremes(db_baremes, conventions)


#: Majoration des heures structurelles au-delà de 35 h, pour la valeur d'un
#: jour au maintien (celle du bulletin à défaut d'un taux société).
MAJORATION_HS_STRUCTURELLES = 0.25


def _cumuls_du_mois_precedent(employee_id: str, exit_date: date, supabase_client) -> dict | None:
    an, mois = (exit_date.year, exit_date.month - 1) if exit_date.month > 1 else (exit_date.year - 1, 12)
    lignes = (
        supabase_client.table("employee_schedules")
        .select("cumuls")
        .match({"employee_id": employee_id, "year": an, "month": mois})
        .execute()
        .data
    ) or []
    return (lignes[0].get("cumuls") if lignes else None) or None


def _conges_par_periode_a_la_sortie(
    employee_id: str, exit_date: date, supabase_client
) -> Optional[Dict[str, Any]]:
    """Les compteurs de congés par période au jour de la sortie et la
    rémunération des périodes, lus comme le bulletin de sortie les lit
    (`payslip_run_heures.cp_fin_de_contrat`). None sans compteurs : le dossier
    retombe alors sur l'estimation globale, comme le bulletin sur son repli."""
    from app.modules.absences.application.queries import get_absence_balances_for_payslip
    from app.modules.payroll.documents.payslip_run_heures import (
        _brut_de_la_periode_precedente,
        periodes_depuis_compteurs,
    )

    try:
        compteurs = get_absence_balances_for_payslip(
            employee_id, exit_date.year, exit_date.month, date_de_sortie=exit_date
        )
        cumuls = _cumuls_du_mois_precedent(employee_id, exit_date, supabase_client)
    except Exception:
        logger.warning(
            "Compteurs de congés par période illisibles pour le dossier de départ (%s)",
            employee_id,
            exc_info=True,
        )
        return None
    return periodes_depuis_compteurs(
        compteurs,
        brut_periode_precedente=_brut_de_la_periode_precedente(employee_id, cumuls),
        brut_en_cours_avant_mois=lire_brut_reference_depuis_cumuls(cumuls),
    )


def _salaire_habituel_et_taux_horaire(
    employee_data: Dict[str, Any], salaire_base: float
) -> tuple[float, float, float]:
    """(salaire mensuel habituel, taux horaire de base, durée hebdomadaire) :
    le salaire d'un mois complet, heures structurelles majorées comprises
    quand la fiche porte un salaire hors heures structurelles."""
    try:
        duree = float(employee_data.get("duree_hebdomadaire") or 35.0)
    except (TypeError, ValueError):
        duree = 35.0
    if duree <= 0:
        duree = 35.0
    if salaire_base <= 0:
        return 0.0, 0.0, duree
    if duree <= 35.0:
        heures = round(duree * 52 / 12, 2)
        return salaire_base, salaire_base / heures, duree
    if salaire_hors_hs_structurelles(employee_data):
        mensuel = salaire_contractuel_total_hors_hs_mode(
            salaire_base, duree, MAJORATION_HS_STRUCTURELLES
        )
        return mensuel, salaire_base / heures_mensuelles_legales(), duree
    heures_equivalentes = heures_mensuelles_legales() + heures_sup_structurelles_mensuelles(duree) * (
        1 + MAJORATION_HS_STRUCTURELLES
    )
    return salaire_base, salaire_base / heures_equivalentes, duree


def _prorata_du_mois_de_sortie(hire_date: date, exit_date: date) -> float:
    jours_du_mois = monthrange(exit_date.year, exit_date.month)[1]
    premier = hire_date.day if (hire_date.year, hire_date.month) == (exit_date.year, exit_date.month) else 1
    return max(0.0, (exit_date.day - premier + 1) / jours_du_mois)


def _iccp_par_periode(
    periodes_cfg: Dict[str, Any],
    *,
    brut_du_mois: float,
    taux: float,
    valeur_jour: float,
    conges_du_preavis: Optional[list] = None,
):
    """La règle du bulletin (calcul_brut._iccp_legale_par_periode) : le brut du
    mois de sortie s'ajoute à la période en cours."""
    periodes = []
    precedente = periodes_cfg.get("periode_precedente")
    if isinstance(precedente, dict):
        periodes.append(
            PeriodeConges(
                libelle=str(precedente.get("libelle") or "période précédente"),
                brut=None if precedente.get("brut") is None else float(precedente["brut"]),
                droits=float(precedente.get("droits") or 0.0),
                restants=float(precedente.get("restants") or 0.0),
            )
        )
    en_cours = periodes_cfg.get("periode_en_cours")
    if isinstance(en_cours, dict):
        periodes.append(
            PeriodeConges(
                libelle=str(en_cours.get("libelle") or "période en cours"),
                brut=round(float(en_cours.get("brut_avant_mois") or 0.0) + brut_du_mois, 2),
                droits=float(en_cours.get("droits") or 0.0),
                restants=float(en_cours.get("restants") or 0.0),
            )
        )
    periodes = ajouter_les_conges_du_preavis(periodes, conges_du_preavis or [])
    return indemnite_fin_de_contrat(periodes, taux=taux, valeur_jour=valeur_jour), periodes


def calculer_indemnite_conges_restants(
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    supabase_client=None,
    *,
    conges_du_preavis: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Calcule l'indemnité compensatrice de congés payés restants avec arbitrage
    maintien de salaire / règle du 1/10e (source canonique : module absences).
    """
    log_payroll_debug(logger, '\n  [CONGÉS PAYÉS]')

    salaire_base = _parse_salaire_base(employee_data)
    employee_id = employee_data.get("id")

    hire_date_str = employee_data.get("hire_date")
    if not hire_date_str:
        logger.warning("    ⚠ Date d'embauche non trouvée, calcul simplifié")
        return {
            "montant": 0.0,
            "jours_restants": 0.0,
            "salaire_reference": salaire_base,
            "description": "Indemnité compensatrice de congés payés",
            "calcul": "Date d'embauche non trouvée - calcul impossible",
            "note": "Date d'embauche manquante",
        }

    if isinstance(hire_date_str, str):
        hire_date = datetime.fromisoformat(hire_date_str).date()
    else:
        hire_date = hire_date_str

    exit_date_str = exit_data.get("last_working_day")
    if isinstance(exit_date_str, str):
        exit_date = datetime.fromisoformat(exit_date_str).date()
    else:
        exit_date = exit_date_str

    jours_restants = 0.0
    cp_acquis = 0.0
    cp_pris = 0.0
    alertes: list[str] = []

    baremes = employee_data.get("baremes") or {}
    if not baremes and supabase_client:
        # Sans barèmes, l'indemnité sortait au légal seul, sans rien dire : une
        # lecture ratée arrête le calcul (LectureIndispensable).
        baremes = _charger_baremes_paie(supabase_client)

    is_cdd = _est_cdd(employee_data)
    is_interim = _est_interim(employee_data)
    montant_precarite = 0.0
    montant_ifm = 0.0
    brut_total_contrat = 0.0

    if employee_id and supabase_client and (is_cdd or is_interim):
        brut_total_contrat, alertes_contrat = lire_brut_total_contrat(
            str(employee_id),
            hire_date,
            exit_date,
            supabase_client,
            salaire_contractuel_fallback=salaire_base,
        )
        alertes.extend(alertes_contrat)
        montant_precarite, montant_ifm = estimer_extras_fin_contrat(
            brut_total_contrat,
            baremes,
            is_cdd=is_cdd,
            is_interim=is_interim,
            specificites=employee_data.get("specificites_paie") or {},
            classification=employee_data.get("classification_conventionnelle"),
        )

    params = lire_parametres_conges(baremes)
    taux_journalier = salaire_base / params["taux_journalier_diviseur"] if salaire_base > 0 else 0.0

    # La règle du bulletin de sortie : par période de référence, sur les jours
    # restants, le plus favorable du dixième et du maintien. Le dossier n'en est
    # qu'une estimation (le brut du mois de sortie n'est pas encore connu) ;
    # le bulletin la recalcule sur le brut réel.
    periodes_cfg = (
        _conges_par_periode_a_la_sortie(str(employee_id), exit_date, supabase_client)
        if employee_id and supabase_client
        else None
    )
    if periodes_cfg:
        return _indemnite_conges_par_periode(
            periodes_cfg,
            employee_data=employee_data,
            salaire_base=salaire_base,
            hire_date=hire_date,
            exit_date=exit_date,
            baremes=baremes,
            params=params,
            is_cdd=is_cdd,
            is_interim=is_interim,
            extras=round(montant_precarite + montant_ifm, 2),
            alertes=alertes,
            conges_du_preavis=conges_du_preavis,
        )

    # Repli : le solde global à la date de sortie et l'arbitrage d'ensemble.
    if employee_id and supabase_client:
        solde = get_cp_solde_a_la_sortie(str(employee_id), exit_date, supabase_client)
        if solde:
            jours_restants = solde.jours_restants
            cp_acquis = solde.conges_acquis
            cp_pris = solde.conges_pris
            log_payroll_debug(logger, f'    Congés acquis: {cp_acquis} jours')
            log_payroll_debug(logger, f'    Congés pris: {cp_pris} jours')
            log_payroll_debug(logger, f'    Solde restant: {jours_restants} jours')

    start_month = 6
    company_id = employee_data.get("company_id")
    if company_id and supabase_client:
        try:
            from app.modules.absences.infrastructure.leave_settings_repository import (
                get_leave_policy,
            )

            start_month = get_leave_policy(str(company_id)).cp_reference_period_start_month
        except Exception:
            pass

    ref_rem = None
    if employee_id and supabase_client:
        ref_rem = calculer_base_reference_dixieme(
            str(employee_id),
            exit_date,
            supabase_client,
            start_month=start_month,
            salaire_contractuel_fallback=salaire_base,
            is_cdd=is_cdd,
            montant_precarite=montant_precarite,
            montant_ifm=montant_ifm,
        )
    else:
        from app.modules.payroll.engine.reference_remuneration import (
            ReferenceRemunerationResult,
            get_cp_reference_period_bounds,
        )

        period_start, period_end = get_cp_reference_period_bounds(
            exit_date, start_month=start_month
        )
        months_count = max(
            1,
            (period_end.year - period_start.year) * 12
            + period_end.month
            - period_start.month
            + 1,
        )
        ref_rem = ReferenceRemunerationResult(
            base_totale=round(salaire_base * months_count, 2),
            periode_debut=period_start,
            periode_fin=period_end,
            periode_label=f"{period_start.strftime('%d/%m/%Y')} – {period_end.strftime('%d/%m/%Y')}",
            alertes=["Calcul sans accès aux bulletins — estimation sur salaire contractuel."],
            source="contractuel",
        )
    alertes.extend(ref_rem.alertes)

    arbitrage = arbitrer_iccp_complet(
        jours_restants,
        taux_journalier=taux_journalier,
        base_reference_dixieme=ref_rem.base_totale,
        taux_dixieme=params["taux_dixieme"],
        jours_reference_dixieme=params["jours_reference_dixieme"],
        alertes=alertes,
    )

    indemnite = arbitrage.montant_final
    methode_label = "maintien" if arbitrage.methode_retenue == "maintien" else "dixieme"

    if (is_cdd or is_interim) and supabase_client and employee_id:
        # Repli d'une fin de CDD ou de mission sans compteurs : le dixième de
        # toute la rémunération du contrat, précarité comprise — le repli du
        # bulletin (`dixieme_global`). Le plus favorable des deux est retenu.
        brut_contrat = brut_total_contrat
        extras = montant_precarite + montant_ifm
        if brut_contrat <= 0:
            brut_contrat = max(ref_rem.base_totale - ref_rem.prime_precarite_incluse, 0.0)
            if extras <= 0:
                extras = ref_rem.prime_precarite_incluse
        base_contrat = brut_contrat + max(extras, 0.0)
        dixieme_contrat = round(base_contrat * params["taux_dixieme"], 2) if base_contrat > 0 else 0.0
        if dixieme_contrat >= indemnite and dixieme_contrat > 0:
            indemnite = dixieme_contrat
            methode_label = "dixieme_global"

    log_payroll_debug(logger, f'    Indemnité (maintien): {arbitrage.indemnite_maintien:.2f} €')
    log_payroll_debug(logger, f'    Indemnité (1/10ème): {arbitrage.indemnite_dixieme:.2f} €')
    log_payroll_debug(logger, f'    Indemnité retenue: {indemnite:.2f} €')

    libelles = {
        "maintien": "maintien",
        "dixieme": "1/10ème",
        "dixieme_global": "1/10ème de la rémunération du contrat",
    }
    calcul_txt = (
        f"{jours_restants} jours restants — méthode {libelles[methode_label]} "
        f"retenue = {indemnite:.2f} € "
        f"(maintien: {arbitrage.indemnite_maintien:.2f} €, "
        f"1/10ème: {arbitrage.indemnite_dixieme:.2f} €) — estimation globale, "
        "compteurs de congés par période indisponibles"
    )

    return {
        "montant": round(indemnite, 2),
        "jours_restants": round(jours_restants, 2),
        "salaire_reference": salaire_base,
        "description": "Indemnité compensatrice de congés payés",
        "calcul": calcul_txt,
        "details": {
            "methode_retenue": methode_label,
            "indemnite_maintien": arbitrage.indemnite_maintien,
            "indemnite_dixieme": arbitrage.indemnite_dixieme,
            "taux_journalier": round(taux_journalier, 4),
            "base_reference_dixieme": ref_rem.base_totale,
            "prime_precarite_incluse": ref_rem.prime_precarite_incluse,
            "periode_reference": ref_rem.periode_label,
            "source_solde": "absences.compute_cp_period_balances",
            "conges_acquis": cp_acquis,
            "conges_pris": cp_pris,
            "alertes": arbitrage.alertes,
        },
    }


def _indemnite_conges_par_periode(
    periodes_cfg: Dict[str, Any],
    *,
    employee_data: Dict[str, Any],
    salaire_base: float,
    hire_date: date,
    exit_date: date,
    baremes: dict,
    params: Dict[str, float],
    is_cdd: bool,
    is_interim: bool,
    extras: float,
    alertes: list,
    conges_du_preavis: Optional[list] = None,
) -> Dict[str, Any]:
    """Estimation du dossier par la règle du bulletin (engine/iccp_fin_contrat).

    Brut du mois de sortie estimé au salaire habituel au prorata des jours du
    mois sous contrat ; précarité ou fin de mission ajoutées au brut de la
    période en cours, comme au bulletin."""
    salaire_habituel, taux_horaire, duree = _salaire_habituel_et_taux_horaire(
        employee_data, salaire_base
    )
    brut_mois = round(salaire_habituel * _prorata_du_mois_de_sortie(hire_date, exit_date), 2)
    if is_cdd or is_interim:
        cle = "interim" if is_interim else "cdd"
        cfg = (baremes.get(cle, {}) or {}).get("indemnite_conges", {}) or {}
        taux = float(cfg.get("taux", 0.10))
    else:
        taux = float(params["taux_dixieme"])
    valeur_jour = (
        valeur_jour_maintien(taux_horaire, duree, MAJORATION_HS_STRUCTURELLES)
        if taux_horaire > 0
        else 0.0
    )
    resultat, periodes = _iccp_par_periode(
        periodes_cfg,
        brut_du_mois=round(brut_mois + max(extras, 0.0), 2),
        taux=taux,
        valeur_jour=valeur_jour,
        conges_du_preavis=conges_du_preavis,
    )
    jours_restants = round(sum(max(p.restants, 0.0) for p in periodes), 2)
    droits = round(sum(p.droits for p in periodes), 2)
    resume = resultat.resume()
    return {
        "montant": resultat.total,
        "jours_restants": jours_restants,
        "salaire_reference": salaire_base,
        "description": "Indemnité compensatrice de congés payés",
        "calcul": resultat.mention or "Aucun jour de congé restant.",
        "details": {
            "methode_retenue": "par_periode",
            "periodes": resume["periodes"],
            "mention": resume["mention"],
            "taux": taux,
            "valeur_jour": resume["valeur_jour"],
            "brut_mois_de_sortie_estime": brut_mois,
            "prime_precarite_incluse": round(max(extras, 0.0), 2),
            "source_solde": "absences.get_absence_balances_for_payslip",
            "conges_acquis": droits,
            "conges_pris": round(droits - jours_restants, 2),
            "alertes": list(alertes)
            + [
                "Estimation : le bulletin de sortie recalcule l'indemnité sur le brut réel du mois."
            ],
        },
    }


def _remuneration_annuelle_n_1(employee_id: str, annee: int, supabase_client) -> Optional[float]:
    """Rémunération brute de l'année civile précédant la rupture (BOSS,
    Indemnités de rupture, § 110 à 120) : le cumul de décembre, à défaut la
    somme des bulletins de l'année ; None si l'année n'est pas dans Martine."""
    lignes = (
        supabase_client.table("employee_schedules")
        .select("cumuls")
        .match({"employee_id": employee_id, "year": annee - 1, "month": 12})
        .execute()
        .data
    ) or []
    if lignes:
        cumuls = (lignes[0].get("cumuls") or {}).get("cumuls") or {}
        for cle in ("brut_annee_civile", "brut_total"):
            if cumuls.get(cle) is not None:
                return round(float(cumuls[cle]), 2)
    bulletins = (
        supabase_client.table("payslips")
        .select("payslip_data")
        .eq("employee_id", employee_id)
        .eq("year", annee - 1)
        .execute()
        .data
    ) or []
    total = sum(
        float((b.get("payslip_data") or {}).get("salaire_brut") or 0)
        for b in bulletins
        if isinstance(b.get("payslip_data"), dict)
    )
    return round(total, 2) if bulletins else None


def _donnees_du_regime_social(
    employee_data: Dict[str, Any], exit_date: date, supabase_client
) -> tuple[float, Optional[float], list[str]]:
    """(PASS annuel, rémunération de l'année précédente, alertes)."""
    alertes: list[str] = []
    baremes = employee_data.get("baremes") or {}
    if not (baremes.get("pss") or {}).get("annuel") and supabase_client is not None:
        baremes = _charger_baremes_paie(supabase_client)
    pass_annuel = float((baremes.get("pss") or {}).get("annuel") or 0.0)
    remuneration = None
    employee_id = employee_data.get("id")
    if employee_id and supabase_client is not None:
        try:
            remuneration = _remuneration_annuelle_n_1(str(employee_id), exit_date.year, supabase_client)
        except Exception:
            logger.warning("Rémunération de l'année précédente illisible (%s)", employee_id, exc_info=True)
    if remuneration is None:
        alertes.append(
            f"Rémunération de {exit_date.year - 1} absente de Martine : limite d'exonération "
            "calculée sur le minimum et la moitié de l'indemnité seulement (BOSS, § 130), à vérifier."
        )
    return pass_annuel, remuneration, alertes


def _regime_social(
    nature: str,
    montant: float,
    minimum: float,
    remuneration_n_1: Optional[float],
    pass_annuel: float,
    alertes: list[str],
    *,
    conventionnelle: bool = False,
    pension_de_retraite: bool = False,
) -> Optional[Dict[str, Any]]:
    """`minimum` : le montant légal, ou le montant conventionnel de branche
    quand il est versé (seuil de la CSG/CRDS et troisième critère des limites
    d'exonération, BOSS § 80, 300, 360, 1640, 1650)."""
    if pass_annuel <= 0:
        # Sans plafond, pas de limite calculable : le bulletin le dira.
        return None
    regime = ventiler_indemnite_de_rupture(
        nature,
        montant,
        minimum=minimum,
        remuneration_annuelle_n_1=remuneration_n_1,
        pass_annuel=pass_annuel,
        pension_de_retraite=pension_de_retraite,
    ).en_dict()
    regime["conventionnelle"] = bool(conventionnelle)
    if alertes:
        regime["alertes"] = list(alertes)
    return regime


def anciennete_en_mois(debut: date, fin_incluse: date) -> int:
    """Mois complets de présence, du premier jour au dernier jour inclus
    (R1234-1 : « proportionnellement au nombre de mois complets »)."""
    if fin_incluse < debut:
        return 0
    delta = relativedelta(fin_incluse + timedelta(days=1), debut)
    return max(0, delta.years * 12 + delta.months)


def _fin_du_contrat(exit_data: Dict[str, Any], dernier_jour: date, notification: date) -> date:
    """Le contrat finit à la fin du préavis, même non exécuté (L1234-4) ; au
    plus tôt le dernier jour travaillé. Faute grave : pas de préavis."""
    if exit_data.get("is_gross_misconduct"):
        return dernier_jour
    jours = int(exit_data.get("notice_period_days") or 0)
    fin_preavis = _date_ou_none(exit_data.get("notice_end_date"))
    if fin_preavis is None and jours > 0:
        fin_preavis = notification + timedelta(days=jours)
    return max(dernier_jour, fin_preavis) if fin_preavis else dernier_jour


def _salaire_de_reference_des_bulletins(
    employee_data: Dict[str, Any], avant_le: date, supabase_client, mois_d_anciennete: Optional[int]
):
    """Le salaire de référence de R1234-4 sur les bulletins des 12 mois qui
    précèdent la notification ; sans bulletin, le salaire habituel du contrat."""
    salaire_base = _parse_salaire_base(employee_data)
    habituel, _, _ = _salaire_habituel_et_taux_horaire(employee_data, salaire_base)
    mois: list = []
    employee_id = employee_data.get("id")
    if employee_id and supabase_client is not None:
        try:
            # Vingt-quatre mois : un arrêt maladie fait prendre les douze qui le précèdent.
            mois = lire_mois_de_salaire(str(employee_id), avant_le, supabase_client, nombre=24)
        except Exception:
            logger.warning("Bulletins illisibles pour le salaire de référence (%s)", employee_id, exc_info=True)
            mois = []
    return calculer_salaire_de_reference(
        mois, repli_contrat=habituel, mois_d_anciennete=mois_d_anciennete
    )


ALERTE_MONTANT_CONVENTIONNEL = (
    "Minimum légal versé : si la convention collective de branche prévoit un montant "
    "conventionnel plus élevé, saisissez-le dans « Indemnité conventionnelle » ; le plus "
    "élevé des deux est versé."
)


def _indemnite_conventionnelle_saisie(exit_data: Dict[str, Any]) -> Optional[float]:
    """Le montant conventionnel saisi sur le départ (`exit_notes`), ou None."""
    notes = exit_data.get("exit_notes") if isinstance(exit_data.get("exit_notes"), dict) else {}
    valeur = notes.get("indemnite_conventionnelle")
    if valeur in (None, ""):
        return None
    try:
        return round(float(valeur), 2)
    except (TypeError, ValueError):
        return None


def _retenir_le_plus_eleve(
    bloc: Dict[str, Any],
    conventionnelle: Optional[float],
    *,
    libelle: str,
    description: str,
) -> Dict[str, Any]:
    """L'indemnité légale ou l'indemnité conventionnelle saisie, la plus élevée :
    elles ne se cumulent pas (BOSS, Indemnités de rupture, § 280, § 1550,
    § 1630). Le montant conventionnel est celui de la convention collective de
    branche : le régime social le retient comme minimum conventionnel."""
    bloc = dict(bloc)
    legal = round(float(bloc.get("montant") or 0.0), 2)
    bloc["montant_legal"] = legal
    alertes = list(bloc.get("alertes") or [])
    if conventionnelle is None:
        bloc["alertes"] = alertes + [ALERTE_MONTANT_CONVENTIONNEL]
        return bloc
    bloc["montant_conventionnel"] = conventionnelle
    if conventionnelle > legal:
        bloc.update(
            {
                "montant": conventionnelle,
                "base_calcul": "Conventionnelle",
                "description": description,
                "libelle_bulletin": libelle,
                "calcul": (
                    f"Indemnité conventionnelle saisie : {_euros(conventionnelle)}, plus élevée "
                    f"que le minimum légal de {_euros(legal)} ({bloc.get('calcul') or ''}) : "
                    "l'indemnité conventionnelle est versée."
                ),
            }
        )
    else:
        bloc["base_calcul"] = "Légale"
        bloc["calcul"] = (
            f"{bloc.get('calcul') or ''}. Indemnité conventionnelle saisie ({_euros(conventionnelle)}) "
            "pas plus élevée que le minimum légal : le minimum légal est versé."
        )
    bloc["alertes"] = alertes
    return bloc

#: Code du travail D1237-1 : (années d'ancienneté minimales, mois de salaire).
BAREME_DEPART_RETRAITE = ((30, 2.0), (20, 1.5), (15, 1.0), (10, 0.5))


def calculer_indemnite_depart_retraite(mois_d_anciennete: int, salaire_reference: float) -> Dict[str, Any]:
    """Indemnité légale de départ volontaire à la retraite (L1237-9, D1237-1) :
    un demi-mois de salaire après dix ans, un mois après quinze, un mois et
    demi après vingt, deux mois après trente. Soumise aux cotisations, à la
    CSG/CRDS et à l'impôt (BOSS, Indemnités de rupture, § 1560 ; F13965)."""
    annees = mois_d_anciennete // 12
    mois_de_salaire = next((m for seuil, m in BAREME_DEPART_RETRAITE if annees >= seuil), 0.0)
    montant = round(salaire_reference * mois_de_salaire, 2)
    if mois_de_salaire == 0:
        calcul = (
            f"Ancienneté de {annees} ans : moins de dix ans, pas d'indemnité légale de "
            "départ à la retraite (D1237-1)"
        )
    else:
        mois_fr = f"{mois_de_salaire:g}".replace(".", ",")
        calcul = (
            f"{mois_fr} mois de salaire pour {annees} ans d'ancienneté (D1237-1) "
            f"× {_euros(salaire_reference)} = {_euros(montant)}"
        )
    return {
        "montant": montant,
        "mois_de_salaire": mois_de_salaire,
        "anciennete_annees_completes": annees,
        "salaire_reference": salaire_reference,
        "description": "Indemnité de départ à la retraite (articles L1237-9 et D1237-1)",
        "calcul": calcul,
        "base_calcul": "Légale",
    }


def _notes(exit_data: Dict[str, Any]) -> Dict[str, Any]:
    notes = exit_data.get("exit_notes")
    return notes if isinstance(notes, dict) else {}


def _pension_liquidable(exit_data: Dict[str, Any]) -> bool:
    """Case du dossier : le salarié peut liquider une pension de retraite de base."""
    return bool(_notes(exit_data).get("pension_liquidable"))


def _alerte_pension_liquidable(
    employee_data: Dict[str, Any], exit_data: Dict[str, Any], fin_du_contrat: date
) -> list[str]:
    """À l'âge légal de sa génération, le salarié peut liquider sa pension :
    l'indemnité de rupture conventionnelle est alors imposable dès le premier
    euro (BOSS, Indemnités de rupture, § 940). Signalé, la case reste à cocher."""
    from app.modules.payroll.engine.age_retraite import (
        a_atteint_l_age_legal,
        age_legal_de_depart,
        lire_date_de_naissance,
    )

    naissance = lire_date_de_naissance(employee_data)
    if naissance is None or _pension_liquidable(exit_data):
        return []
    if not a_atteint_l_age_legal(naissance, fin_du_contrat):
        return []
    return [
        f"Le salarié a l'âge légal de départ à la retraite de sa génération "
        f"({age_legal_de_depart(naissance).libelle}, CSS L161-17-2) : s'il peut liquider une "
        "pension de retraite de base, cochez la case du dossier ; l'indemnité est alors "
        "imposable dès le premier euro, ses cotisations, sa CSG/CRDS et la contribution de "
        "40 % ne changent pas (BOSS, Indemnités de rupture, § 60, 890 et 940)."
    ]


def alertes_age_de_la_retraite(
    employee_data: Dict[str, Any], *, mise_a_la_retraite: bool, a_la_date: date
) -> list[str]:
    """L'âge du salarié au départ ou à la mise à la retraite : signalé, jamais
    bloquant (BOSS, Indemnités de rupture, § 1540, 1590 à 1610 ; L1237-5 ;
    CSS L161-17-2)."""
    from app.modules.payroll.engine.age_retraite import (
        AGE_MISE_A_LA_RETRAITE_D_OFFICE,
        AGE_TAUX_PLEIN,
        a_atteint_l_age_legal,
        age_en_annees,
        age_legal_de_depart,
        date_de_l_age_legal,
        lire_date_de_naissance,
    )

    naissance = lire_date_de_naissance(employee_data)
    if naissance is None:
        return [
            "Date de naissance absente de la fiche : l'âge requis pour un départ ou une mise "
            "à la retraite n'a pas pu être vérifié."
        ]
    if mise_a_la_retraite:
        age = age_en_annees(naissance, a_la_date)
        if age >= AGE_MISE_A_LA_RETRAITE_D_OFFICE:
            return []
        if age < AGE_TAUX_PLEIN:
            return [
                f"Mise à la retraite d'un salarié de {age} ans : avant {AGE_TAUX_PLEIN} ans, l'âge "
                "du taux plein (1° de l'article L. 351-8 du code de la sécurité sociale), elle "
                "n'est pas possible ; la rupture serait un licenciement (BOSS, Indemnités de "
                "rupture, § 1600 et 1610)."
            ]
        return [
            f"Mise à la retraite d'un salarié de {age} ans : avant {AGE_MISE_A_LA_RETRAITE_D_OFFICE} "
            "ans, elle demande son accord exprès ; l'employeur l'interroge par écrit avant chaque "
            "anniversaire et ne peut pas le mettre à la retraite dans l'année qui suit un refus "
            "(Code du travail L1237-5 ; BOSS, Indemnités de rupture, § 1600)."
        ]
    if a_atteint_l_age_legal(naissance, a_la_date):
        return []
    return [
        f"Départ à la retraite avant l'âge légal de la génération du salarié "
        f"({age_legal_de_depart(naissance).libelle}, atteint le "
        f"{date_de_l_age_legal(naissance).strftime('%d/%m/%Y')}, CSS L161-17-2) : un départ "
        "volontaire n'est possible qu'à l'âge où il peut liquider sa pension (BOSS, Indemnités "
        "de rupture, § 1540). Vérifiez une retraite anticipée (carrière longue, handicap, "
        "incapacité permanente, inaptitude, amiante : service-public F14043)."
    ]


def _initiative_retraite(exit_data: Dict[str, Any]) -> str:
    """« employer » pour une mise à la retraite, « employee » sinon (départ volontaire)."""
    notes = exit_data.get("exit_notes") if isinstance(exit_data.get("exit_notes"), dict) else {}
    initiative = notes.get("retirement_initiator") or exit_data.get("retirement_initiator")
    return "employer" if initiative == "employer" else "employee"


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================


def calculer_indemnites_sortie(
    employee_data: Dict[str, Any], exit_data: Dict[str, Any], supabase_client=None
) -> Dict[str, Any]:
    """
    Fonction principale pour calculer toutes les indemnités de sortie

    Args:
        employee_data: Données de l'employé (id, hire_date, salaire_de_base, etc.)
        exit_data: Données du processus de sortie (exit_type, last_working_day, etc.)

    Returns:
        Dict contenant tous les calculs d'indemnités avec détails
    """
    log_payroll_debug(logger, '\n' + '=' * 70)
    log_payroll_debug(logger, 'CALCUL DES INDEMNITÉS DE SORTIE')
    log_payroll_debug(logger, '=' * 70)

    # Extraire les données nécessaires
    hire_date_str = employee_data.get("hire_date")
    if not hire_date_str:
        raise ValueError("Date d'embauche (hire_date) non trouvée dans employee_data")

    if isinstance(hire_date_str, str):
        hire_date = datetime.fromisoformat(hire_date_str).date()
    else:
        hire_date = hire_date_str

    exit_date_str = exit_data.get("last_working_day")
    if not exit_date_str:
        raise ValueError("Date de sortie (last_working_day) non trouvée dans exit_data")

    if isinstance(exit_date_str, str):
        exit_date = datetime.fromisoformat(exit_date_str).date()
    else:
        exit_date = exit_date_str

    exit_type = exit_data.get("exit_type")
    notice_period_days = exit_data.get("notice_period_days", 0)
    notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")
    is_gross_misconduct = exit_data.get("is_gross_misconduct", False)

    log_payroll_debug(logger, f"\nEmployé: {employee_data.get('first_name')} {employee_data.get('last_name')}")
    log_payroll_debug(logger, f'Type de sortie: {exit_type}')
    log_payroll_debug(logger, f"Date d'embauche: {hire_date}")
    log_payroll_debug(logger, f'Date de sortie: {exit_date}')

    # 1 et 2. Ancienneté et salaire de référence.
    # Licenciement et rupture conventionnelle : ancienneté jusqu'à la fin du
    # contrat, c'est-à-dire du préavis même non exécuté (L1234-4), en mois
    # complets (R1234-1) ; les 8 mois du licenciement s'apprécient à la
    # notification (F987) ; salaire de référence tiré des bulletins bruts, le
    # plus favorable des 12 ou 3 derniers mois (R1234-4).
    # L'ancienneté part de la date d'entrée du contrat (`hire_date`) : la
    # reprise d'ancienneté de la fiche (`seniority_reference_date`,
    # `prior_service_months`) n'est pas lue, en attendant de savoir si elle
    # est contractuelle et vaut pour l'indemnité ([H5], décision d'Alexandre ;
    # `prior_service_months` porte de plus un double compte connu).
    alertes_reference: list[str] = []
    phrase_arret: Optional[str] = None
    mois_a_la_notification: Optional[int] = None
    fin_du_contrat = exit_date
    mois_d_anciennete: Optional[int] = None
    mise_a_la_retraite = exit_type == "depart_retraite" and _initiative_retraite(exit_data) == "employer"
    if exit_type in ("licenciement", "rupture_conventionnelle", "depart_retraite"):
        notification = _date_ou_none(exit_data.get("exit_request_date")) or exit_date
        fin_du_contrat = _fin_du_contrat(exit_data, exit_date, notification)
        mois_d_anciennete = anciennete_en_mois(hire_date, fin_du_contrat)
        mois_a_la_notification = anciennete_en_mois(hire_date, notification)
        anciennete = mois_d_anciennete / 12
        # Départ volontaire : les mois qui précèdent le départ (F13965) ;
        # licenciement, rupture et mise à la retraite : ceux qui précèdent la
        # notification ou la signature (R1234-4, F13965).
        avant_le = (
            fin_du_contrat
            if exit_type == "depart_retraite" and not mise_a_la_retraite
            else notification
        )
        reference = _salaire_de_reference_des_bulletins(
            employee_data, avant_le, supabase_client, anciennete_en_mois(hire_date, avant_le)
        )
        salaire_reference = reference.retenu
        salaire_ref_12 = reference.moyenne_douze_mois
        salaire_ref_3 = reference.tiers_trois_mois
        alertes_reference = list(reference.alertes)
        phrase_arret = reference.arret
    else:
        anciennete = calculer_anciennete_annees(hire_date, exit_date)
        salaire_ref_12 = calculer_salaire_reference_12_mois(employee_data)
        salaire_ref_3 = calculer_salaire_reference_3_mois(employee_data)
        salaire_reference = max(salaire_ref_12, salaire_ref_3)

    log_payroll_debug(logger, f'\nSalaire référence (12 mois): {salaire_ref_12} €')
    log_payroll_debug(logger, f'Salaire référence (3 mois): {salaire_ref_3} €')
    log_payroll_debug(logger, f'Salaire référence retenu: {salaire_reference:.2f} €')

    # 3. Indemnité de préavis : due seulement pour une dispense à l'initiative
    # de l'employeur, sur la rémunération qu'il aurait perçue et pour le temps
    # de préavis restant après le dernier jour travaillé (engine/preavis).
    alertes_preavis: list[str] = []
    if indemnite_compensatrice_due(notice_indemnity_type, faute_grave=bool(is_gross_misconduct)) and (
        notice_period_days or 0
    ) > 0:
        remuneration_preavis, source_preavis, alertes_preavis = _remuneration_du_preavis(
            employee_data, exit_date, supabase_client
        )
        indemnite_preavis = calculer_indemnite_preavis(
            remuneration_preavis,
            notice_period_days,
            notice_indemnity_type,
            jours_restants=jours_de_preavis_restants(
                jours_de_preavis=notice_period_days,
                fin_du_preavis=_date_ou_none(exit_data.get("notice_end_date")),
                dernier_jour_travaille=exit_date,
            ),
            source_remuneration=source_preavis,
            is_gross_misconduct=bool(is_gross_misconduct),
        )
        if alertes_preavis:
            indemnite_preavis["alertes"] = alertes_preavis
        indemnite_preavis = poser_les_conges_du_preavis(indemnite_preavis, employee_data, exit_date)
    else:
        indemnite_preavis = calculer_indemnite_preavis(
            0.0,
            notice_period_days or 0,
            notice_indemnity_type,
            is_gross_misconduct=bool(is_gross_misconduct),
        )

    # 4. Calculer les congés payés restants
    indemnite_conges = calculer_indemnite_conges_restants(
        employee_data,
        exit_data,
        supabase_client,
        conges_du_preavis=indemnite_preavis.get("conges_du_preavis"),
    )

    # 5. Calculer l'indemnité spécifique selon le type de sortie
    indemnite_licenciement = None
    indemnite_rupture = None
    indemnite_precarite = None

    if exit_type == "fin_cdd":
        # La précarité 10 % (art. L1243-8) est PORTÉE PAR LE BULLETIN du
        # dernier mois du CDD (calcul_brut._calculer_prime_precarite_cdd) :
        # ici elle n'est qu'INFORMATIVE — affichée au STC, jamais ajoutée à
        # total_gross_indemnities, sinon elle serait versée deux fois. Le
        # montant est celui déjà estimé par le chemin ICCP (mêmes règles,
        # même assiette bulletins du contrat).
        montant_precarite = float(
            (indemnite_conges.get("details") or {}).get("prime_precarite_incluse")
            or 0.0
        )
        indemnite_precarite = {
            "montant": round(montant_precarite, 2),
            "description": "Indemnité de fin de contrat (précarité, art. L1243-8)",
            "calcul": (
                "10 % des rémunérations brutes du CDD — versée sur le BULLETIN "
                "du dernier mois du contrat, rappelée ici pour information"
            ),
            "versee_au_bulletin": True,
        }

    conventionnelle = _indemnite_conventionnelle_saisie(exit_data)
    if exit_type == "licenciement":
        indemnite_licenciement = calculer_indemnite_licenciement(
            anciennete,
            salaire_reference,
            is_gross_misconduct,
            mois_a_la_notification=mois_a_la_notification,
        )
        indemnite_licenciement["alertes"] = alertes_reference
        if is_gross_misconduct:
            if conventionnelle:
                indemnite_licenciement["alertes"] = alertes_reference + [
                    "Faute grave ou lourde : l'indemnité conventionnelle saisie n'est pas versée."
                ]
        else:
            indemnite_licenciement = _retenir_le_plus_eleve(
                indemnite_licenciement,
                conventionnelle,
                libelle="Indemnité conventionnelle de licenciement",
                description="Indemnité conventionnelle de licenciement (convention collective de branche)",
            )

    elif exit_type == "rupture_conventionnelle":
        indemnite_rupture = calculer_indemnite_rupture_conventionnelle(
            anciennete, salaire_reference, _montant_negocie_saisi(exit_data)
        )
        indemnite_rupture["alertes"] = (
            alertes_reference
            + indemnite_rupture.get("alertes", [])
            + _alerte_pension_liquidable(employee_data, exit_data, fin_du_contrat)
        )

    indemnite_depart_retraite = None
    indemnite_mise_retraite = None
    if exit_type == "depart_retraite":
        if mise_a_la_retraite:
            # L1237-7 : au moins l'indemnité légale de licenciement.
            legale = calculer_indemnite_licenciement(
                anciennete,
                salaire_reference,
                False,
                mois_a_la_notification=mois_a_la_notification,
            )
            indemnite_mise_retraite = _retenir_le_plus_eleve(
                {
                    **legale,
                    "description": "Indemnité de mise à la retraite (articles L1237-7 et L1234-9)",
                    "base_calcul": "Légale",
                    "alertes": alertes_age_de_la_retraite(
                        employee_data,
                        mise_a_la_retraite=True,
                        a_la_date=_date_ou_none(exit_data.get("exit_request_date")) or exit_date,
                    )
                    + list(alertes_reference),
                },
                conventionnelle,
                libelle="Indemnité conventionnelle de mise à la retraite",
                description="Indemnité conventionnelle de mise à la retraite (convention collective de branche)",
            )
        else:
            indemnite_depart_retraite = calculer_indemnite_depart_retraite(
                mois_d_anciennete or 0, salaire_reference
            )
            indemnite_depart_retraite["alertes"] = alertes_age_de_la_retraite(
                employee_data, mise_a_la_retraite=False, a_la_date=fin_du_contrat
            ) + list(alertes_reference)
            indemnite_depart_retraite = _retenir_le_plus_eleve(
                indemnite_depart_retraite,
                conventionnelle,
                libelle="Indemnité conventionnelle de départ à la retraite",
                description="Indemnité conventionnelle de départ à la retraite (convention collective de branche)",
            )

    # Arrêt maladie dans les mois de référence : le détail de chaque indemnité
    # calculée sur le salaire de référence le dit (Cass. soc., 23 mai 2017).
    if phrase_arret:
        for bloc in (indemnite_licenciement, indemnite_rupture, indemnite_mise_retraite, indemnite_depart_retraite):
            if isinstance(bloc, dict):
                bloc["calcul"] = f"{bloc.get('calcul') or ''}. {phrase_arret}".lstrip(". ")
                bloc["salaire_reference_avant_arret"] = True

    # 6. Régime social des indemnités de rupture (BOSS, Indemnités de rupture) :
    # le bulletin en tire la part au brut, la CSG/CRDS au-delà du minimum et la
    # contribution patronale de 40 % (engine/regime_indemnites_rupture).
    if indemnite_licenciement or indemnite_rupture or indemnite_mise_retraite:
        pass_annuel, remuneration_n_1, alertes_regime = _donnees_du_regime_social(
            employee_data, exit_date, supabase_client
        )
        # Le montant versé (légal ou conventionnel de branche) est le minimum
        # du régime : seuil de la CSG/CRDS et troisième critère des limites.
        if indemnite_mise_retraite and indemnite_mise_retraite.get("montant", 0) > 0:
            indemnite_mise_retraite["regime_social"] = _regime_social(
                MISE_A_LA_RETRAITE,
                indemnite_mise_retraite["montant"],
                indemnite_mise_retraite["montant"],
                remuneration_n_1,
                pass_annuel,
                alertes_regime,
                conventionnelle=indemnite_mise_retraite.get("base_calcul") == "Conventionnelle",
            )
        if indemnite_licenciement and indemnite_licenciement.get("montant", 0) > 0:
            indemnite_licenciement["regime_social"] = _regime_social(
                LICENCIEMENT,
                indemnite_licenciement["montant"],
                indemnite_licenciement["montant"],
                remuneration_n_1,
                pass_annuel,
                alertes_regime,
                conventionnelle=indemnite_licenciement.get("base_calcul") == "Conventionnelle",
            )
        if indemnite_rupture and indemnite_rupture.get("montant_negocie", 0) > 0:
            indemnite_rupture["regime_social"] = _regime_social(
                RUPTURE_CONVENTIONNELLE,
                indemnite_rupture["montant_negocie"],
                indemnite_rupture["montant_minimum"],
                remuneration_n_1,
                pass_annuel,
                alertes_regime,
                pension_de_retraite=_pension_liquidable(exit_data),
            )

    # 7. Calculer les totaux
    total_brut = indemnite_preavis["montant"] + indemnite_conges["montant"]

    if indemnite_licenciement:
        total_brut += indemnite_licenciement["montant"]

    if indemnite_rupture:
        total_brut += indemnite_rupture.get("montant_negocie", 0)

    for indemnite_retraite in (indemnite_depart_retraite, indemnite_mise_retraite):
        if indemnite_retraite:
            total_brut += indemnite_retraite.get("montant", 0)

    # Pas de « net » ici : il dépend des cotisations du bulletin de sortie
    # (préavis et congés sont des salaires) et du régime des indemnités de
    # rupture, que le bulletin applique. Un net égal au brut était faux.
    total_net = None

    log_payroll_debug(logger, f"\n{'=' * 70}")
    log_payroll_debug(logger, 'RÉSUMÉ DES INDEMNITÉS:')
    log_payroll_debug(logger, f"  - Préavis: {indemnite_preavis['montant']:.2f} €")
    log_payroll_debug(logger, f"  - Congés payés: {indemnite_conges['montant']:.2f} €")

    if indemnite_licenciement:
        log_payroll_debug(logger, f"  - Licenciement: {indemnite_licenciement['montant']:.2f} €")

    if indemnite_rupture:
        log_payroll_debug(logger, f"  - Rupture conventionnelle: {indemnite_rupture.get('montant_negocie', 0):.2f} €")

    log_payroll_debug(logger, f'\nTOTAL BRUT: {total_brut:.2f} €')
    log_payroll_debug(logger, f"{'=' * 70}\n")

    # Construire le résultat
    result = {
        "exit_id": exit_data.get("id"),
        "employee_id": employee_data.get("id"),
        "anciennete_annees": round(anciennete, 2),
        "salaire_reference": salaire_reference,
        "indemnite_preavis": indemnite_preavis,
        "indemnite_conges": indemnite_conges,
        "total_gross_indemnities": round(total_brut, 2),
        "total_net_indemnities": total_net,
        "calculation_date": datetime.now().isoformat(),
        "calculation_details": {
            "hire_date": hire_date.isoformat(),
            "exit_date": exit_date.isoformat(),
            "exit_type": exit_type,
            "is_gross_misconduct": is_gross_misconduct,
            "salaire_ref_12_mois": salaire_ref_12,
            "salaire_ref_3_mois": salaire_ref_3,
            "fin_du_contrat": fin_du_contrat.isoformat(),
            "anciennete_mois": mois_d_anciennete,
        },
    }

    if indemnite_precarite:
        result["indemnite_precarite"] = indemnite_precarite

    # Départ volontaire (soumis, au brut) ou mise à la retraite (régime des
    # indemnités de rupture) : clés lues par le bulletin et le reçu.
    if indemnite_depart_retraite:
        result["indemnite_depart_retraite"] = indemnite_depart_retraite
    if indemnite_mise_retraite:
        result["indemnite_mise_retraite"] = indemnite_mise_retraite

    # Ajouter les indemnités spécifiques selon le type
    if indemnite_licenciement:
        result["indemnite_licenciement"] = indemnite_licenciement
    else:
        result["indemnite_licenciement"] = {
            "montant": 0.0,
            "description": "Indemnité de licenciement",
            "calcul": "Non applicable",
        }

    if indemnite_rupture:
        # `montant_negocie` et `montant_minimum` sont les clés que lisent le
        # bulletin (bulletin.creer_bulletin_sortie), le solde de tout compte
        # et l'écran ; `montant`, celle de l'attestation.
        result["indemnite_rupture_conventionnelle"] = {
            "montant": indemnite_rupture.get("montant_negocie", 0),
            "montant_negocie": indemnite_rupture.get("montant_negocie", 0),
            "montant_minimum": indemnite_rupture.get("montant_minimum", 0),
            "montant_negocie_saisi": indemnite_rupture.get("montant_negocie_saisi"),
            "description": indemnite_rupture.get(
                "description", "Indemnité de rupture conventionnelle"
            ),
            "calcul": indemnite_rupture.get("calcul", ""),
            "alertes": indemnite_rupture.get("alertes", []),
            "details": indemnite_rupture,
        }
        if indemnite_rupture.get("regime_social"):
            result["indemnite_rupture_conventionnelle"]["regime_social"] = indemnite_rupture[
                "regime_social"
            ]
    else:
        result["indemnite_rupture_conventionnelle"] = {
            "montant": 0.0,
            "description": "Indemnité de rupture conventionnelle",
            "calcul": "Non applicable",
        }

    return result
