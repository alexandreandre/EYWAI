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
from datetime import date, datetime
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
    indemnite_compensatrice_due,
    jours_de_preavis_restants,
    phrase_execution_preavis,
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
            f"Rémunération qu'il aurait perçue : {remuneration_mensuelle:.2f} € par mois"
            f"{origine} / 30 × {jours} jours de préavis restant = {indemnite:.2f} €"
        ),
    }


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
    reference = calculer_salaire_de_reference(mois, repli_contrat=habituel, mois_d_anciennete=3)
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

    if anciennete_annees < (8 / 12):  # Moins de 8 mois
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
        "calcul": f"Tranche 1: {annees_tranche1:.2f} ans × 1/4 mois ({indemnite_tranche1:.2f} €)"
        + (
            f" + Tranche 2: {annees_tranche2:.2f} ans × 1/3 mois ({indemnite_tranche2:.2f} €)"
            if annees_tranche2 > 0
            else ""
        ),
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

    # Minimum légal = indemnité de licenciement
    indemnite_licenciement = calculer_indemnite_licenciement(
        anciennete_annees, salaire_reference, is_gross_misconduct=False
    )

    montant_minimum = indemnite_licenciement["montant"]
    if montant_negocie_saisi is None:
        montant_negocie = montant_minimum
        calcul = f"Minimum légal = {montant_minimum:.2f} € (indemnité de licenciement)"
    else:
        montant_negocie = round(float(montant_negocie_saisi), 2)
        calcul = (
            f"Montant de la convention saisi : {montant_negocie:.2f} € "
            f"(minimum légal estimé : {montant_minimum:.2f} €)"
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
    return indemnite_fin_de_contrat(periodes, taux=taux, valeur_jour=valeur_jour), periodes


def calculer_indemnite_conges_restants(
    employee_data: Dict[str, Any], exit_data: Dict[str, Any], supabase_client=None
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

    # 1. Calculer l'ancienneté
    anciennete = calculer_anciennete_annees(hire_date, exit_date)

    # 2. Déterminer le salaire de référence
    salaire_ref_12 = calculer_salaire_reference_12_mois(employee_data)
    salaire_ref_3 = calculer_salaire_reference_3_mois(employee_data)

    # Prendre le plus avantageux pour le salarié
    salaire_reference = max(salaire_ref_12, salaire_ref_3)

    log_payroll_debug(logger, f'\nSalaire référence (12 mois): {salaire_ref_12:.2f} €')
    log_payroll_debug(logger, f'Salaire référence (3 mois): {salaire_ref_3:.2f} €')
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
    else:
        indemnite_preavis = calculer_indemnite_preavis(
            0.0,
            notice_period_days or 0,
            notice_indemnity_type,
            is_gross_misconduct=bool(is_gross_misconduct),
        )

    # 4. Calculer les congés payés restants
    indemnite_conges = calculer_indemnite_conges_restants(
        employee_data, exit_data, supabase_client
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

    if exit_type == "licenciement":
        indemnite_licenciement = calculer_indemnite_licenciement(
            anciennete, salaire_reference, is_gross_misconduct
        )

    elif exit_type == "rupture_conventionnelle":
        indemnite_rupture = calculer_indemnite_rupture_conventionnelle(
            anciennete, salaire_reference, _montant_negocie_saisi(exit_data)
        )

    # 6. Calculer les totaux
    total_brut = indemnite_preavis["montant"] + indemnite_conges["montant"]

    if indemnite_licenciement:
        total_brut += indemnite_licenciement["montant"]

    if indemnite_rupture:
        total_brut += indemnite_rupture.get("montant_negocie", 0)

    # Calcul du net (simplifié - en réalité, certaines indemnités sont exonérées)
    # TODO: Appliquer les règles fiscales et sociales spécifiques
    # - Indemnité de licenciement: exonérée jusqu'à 2× le salaire annuel brut ou 50% de l'indemnité versée
    # - Indemnité de rupture: exonérée jusqu'à 8 000 €
    total_net = total_brut  # Temporaire

    log_payroll_debug(logger, f"\n{'=' * 70}")
    log_payroll_debug(logger, 'RÉSUMÉ DES INDEMNITÉS:')
    log_payroll_debug(logger, f"  - Préavis: {indemnite_preavis['montant']:.2f} €")
    log_payroll_debug(logger, f"  - Congés payés: {indemnite_conges['montant']:.2f} €")

    if indemnite_licenciement:
        log_payroll_debug(logger, f"  - Licenciement: {indemnite_licenciement['montant']:.2f} €")

    if indemnite_rupture:
        log_payroll_debug(logger, f"  - Rupture conventionnelle: {indemnite_rupture.get('montant_negocie', 0):.2f} €")

    log_payroll_debug(logger, f'\nTOTAL BRUT: {total_brut:.2f} €')
    log_payroll_debug(logger, f'TOTAL NET (estimé): {total_net:.2f} €')
    log_payroll_debug(logger, f"{'=' * 70}\n")

    # Construire le résultat
    result = {
        "exit_id": exit_data.get("id"),
        "employee_id": employee_data.get("id"),
        "anciennete_annees": anciennete,
        "salaire_reference": salaire_reference,
        "indemnite_preavis": indemnite_preavis,
        "indemnite_conges": indemnite_conges,
        "total_gross_indemnities": round(total_brut, 2),
        "total_net_indemnities": round(total_net, 2),
        "calculation_date": datetime.now().isoformat(),
        "calculation_details": {
            "hire_date": hire_date.isoformat(),
            "exit_date": exit_date.isoformat(),
            "exit_type": exit_type,
            "is_gross_misconduct": is_gross_misconduct,
            "salaire_ref_12_mois": salaire_ref_12,
            "salaire_ref_3_mois": salaire_ref_3,
        },
    }

    if indemnite_precarite:
        result["indemnite_precarite"] = indemnite_precarite

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
            "details": indemnite_rupture,
        }
    else:
        result["indemnite_rupture_conventionnelle"] = {
            "montant": 0.0,
            "description": "Indemnité de rupture conventionnelle",
            "calcul": "Non applicable",
        }

    return result
