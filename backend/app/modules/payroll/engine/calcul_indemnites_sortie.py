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

from typing import Dict, Any
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from app.modules.payroll.engine.cp_solde_sortie import get_cp_solde_a_la_sortie
from app.modules.payroll.engine.iccp_arbitrage import (
    arbitrer_iccp_complet,
    lire_parametres_conges,
)
from app.modules.payroll.engine.reference_remuneration import (
    calculer_base_reference_dixieme,
    calculer_iccp_l1243_8,
    estimer_extras_fin_contrat,
    lire_brut_total_contrat,
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
    salaire_mensuel_brut: float, notice_period_days: int, notice_indemnity_type: str
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de préavis

    Formule: (salaire mensuel brut / 30) × nombre de jours de préavis

    Args:
        salaire_mensuel_brut: Salaire mensuel brut de référence
        notice_period_days: Nombre de jours de préavis
        notice_indemnity_type: 'paid', 'waived', 'not_applicable'

    Returns:
        Dict contenant le montant et les détails du calcul
    """
    log_payroll_debug(logger, '\n  [PRÉAVIS]')
    log_payroll_debug(logger, f'    Salaire mensuel: {salaire_mensuel_brut:.2f} €')
    log_payroll_debug(logger, f'    Jours de préavis: {notice_period_days}')
    log_payroll_debug(logger, f'    Type: {notice_indemnity_type}')

    if notice_indemnity_type != "paid" or notice_period_days == 0:
        return {
            "montant": 0.0,
            "jours_preavis": notice_period_days,
            "type": notice_indemnity_type,
            "description": "Indemnité de préavis",
            "calcul": "Non applicable ou dispensé",
        }

    # Calcul: (salaire mensuel brut / 30) × nombre de jours
    indemnite = (salaire_mensuel_brut / 30) * notice_period_days

    log_payroll_debug(logger, f'    Indemnité: ({salaire_mensuel_brut} / 30) × {notice_period_days} = {indemnite:.2f} €')

    return {
        "montant": round(indemnite, 2),
        "jours_preavis": notice_period_days,
        "salaire_reference": salaire_mensuel_brut,
        "type": notice_indemnity_type,
        "description": f"Indemnité compensatrice de préavis ({notice_period_days} jours)",
        "calcul": f"({salaire_mensuel_brut:.2f} / 30) × {notice_period_days} jours = {indemnite:.2f} €",
    }


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
    anciennete_annees: float, salaire_reference: float
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de rupture conventionnelle

    Minimum légal = indemnité légale de licenciement
    En pratique, souvent négociée au-dessus du minimum

    Args:
        anciennete_annees: Ancienneté en années
        salaire_reference: Salaire de référence

    Returns:
        Dict contenant le montant minimum et les détails
    """
    log_payroll_debug(logger, '\n  [RUPTURE CONVENTIONNELLE]')

    # Minimum légal = indemnité de licenciement
    indemnite_licenciement = calculer_indemnite_licenciement(
        anciennete_annees, salaire_reference, is_gross_misconduct=False
    )

    montant_minimum = indemnite_licenciement["montant"]

    log_payroll_debug(logger, f'    Minimum légal: {montant_minimum:.2f} € (= indemnité licenciement)')
    log_payroll_debug(logger, f'    Montant négocié: {montant_minimum:.2f} € (utiliser le minimum par défaut)')

    return {
        "montant_minimum": montant_minimum,
        "montant_negocie": montant_minimum,  # Par défaut, peut être ajusté
        "anciennete": anciennete_annees,
        "salaire_reference": salaire_reference,
        "description": "Indemnité de rupture conventionnelle",
        "calcul": f"Minimum légal = {montant_minimum:.2f} € (indemnité de licenciement)",
        "details_licenciement": indemnite_licenciement,
    }


# ============================================================================
# CONGÉS PAYÉS RESTANTS
# ============================================================================


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

    if employee_id and supabase_client:
        solde = get_cp_solde_a_la_sortie(str(employee_id), exit_date, supabase_client)
        if solde:
            jours_restants = solde.jours_restants
            cp_acquis = solde.conges_acquis
            cp_pris = solde.conges_pris
            log_payroll_debug(logger, f'    Congés acquis: {cp_acquis} jours')
            log_payroll_debug(logger, f'    Congés pris: {cp_pris} jours')
            log_payroll_debug(logger, f'    Solde restant: {jours_restants} jours')

    baremes = employee_data.get("baremes") or {}
    if not baremes and supabase_client:
        try:
            baremes = _charger_baremes_paie(supabase_client)
        except Exception:
            baremes = {}

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
        )

    params = lire_parametres_conges(baremes)
    taux_journalier = salaire_base / params["taux_journalier_diviseur"] if salaire_base > 0 else 0.0

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
    iccp_l1243_8 = None

    if (is_cdd or is_interim) and supabase_client and employee_id:
        brut_l1243 = brut_total_contrat
        prec_l1243 = montant_precarite
        ifm_l1243 = montant_ifm
        if brut_l1243 <= 0:
            brut_l1243 = max(ref_rem.base_totale - ref_rem.prime_precarite_incluse, 0.0)
            if prec_l1243 <= 0:
                prec_l1243 = ref_rem.prime_precarite_incluse
        iccp_l1243_8 = calculer_iccp_l1243_8(
            brut_l1243,
            montant_precarite=prec_l1243,
            montant_ifm=ifm_l1243,
        )
        if iccp_l1243_8 > indemnite:
            indemnite = iccp_l1243_8
            arbitrage.methode_retenue = "dixieme"

    methode_label = (
        "maintien"
        if arbitrage.methode_retenue == "maintien"
        else "dixieme"
    )
    if iccp_l1243_8 is not None and iccp_l1243_8 >= indemnite and jours_restants == 0:
        methode_label = "l1243_8"

    log_payroll_debug(logger, f'    Indemnité (maintien): {arbitrage.indemnite_maintien:.2f} €')
    log_payroll_debug(logger, f'    Indemnité (1/10ème): {arbitrage.indemnite_dixieme:.2f} €')
    if iccp_l1243_8 is not None:
        log_payroll_debug(logger, f'    Indemnité L1243-8: {iccp_l1243_8:.2f} €')
    log_payroll_debug(logger, f'    Indemnité retenue: {indemnite:.2f} €')

    calcul_txt = (
        f"{jours_restants} jours restants — méthode "
        f"{'maintien' if methode_label == 'maintien' else '1/10ème' if methode_label == 'dixieme' else 'L1243-8'} "
        f"retenue = {indemnite:.2f} € "
        f"(maintien: {arbitrage.indemnite_maintien:.2f} €, "
        f"1/10ème: {arbitrage.indemnite_dixieme:.2f} €"
    )
    if iccp_l1243_8 is not None:
        calcul_txt += f", L1243-8: {iccp_l1243_8:.2f} €"
    calcul_txt += ")"

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
            "iccp_l1243_8": iccp_l1243_8,
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

    # 3. Calculer l'indemnité de préavis
    indemnite_preavis = calculer_indemnite_preavis(
        salaire_reference, notice_period_days, notice_indemnity_type
    )

    # 4. Calculer les congés payés restants
    indemnite_conges = calculer_indemnite_conges_restants(
        employee_data, exit_data, supabase_client
    )

    # 5. Calculer l'indemnité spécifique selon le type de sortie
    indemnite_licenciement = None
    indemnite_rupture = None

    if exit_type == "licenciement":
        indemnite_licenciement = calculer_indemnite_licenciement(
            anciennete, salaire_reference, is_gross_misconduct
        )

    elif exit_type == "rupture_conventionnelle":
        indemnite_rupture = calculer_indemnite_rupture_conventionnelle(
            anciennete, salaire_reference
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
        result["indemnite_rupture_conventionnelle"] = {
            "montant": indemnite_rupture.get("montant_negocie", 0),
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
