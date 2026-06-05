"""
Socle commun du reçu pour solde de tout compte.

Ces fonctions calculent les sections communes à tous les types de rupture et
renvoient des *données structurées* (sections / lignes), indépendantes du moteur
de rendu. Le rendu PDF est assuré par ``html_renderer`` (format avocat).
"""

from datetime import datetime, date
from typing import Any, Dict, Optional, Tuple

from .html_renderer import amount_row, amounts_section
from .pdf_helpers import format_currency, safe_float

_NEANT = "Néant"


def _fetch_last_payslip_extras(
    employee_id: Optional[str],
    supabase_client: Any,
) -> Dict[str, Any]:
    """HS et primes depuis le dernier bulletin validé, si disponible."""
    empty = {
        "hs_brut": 0.0,
        "hs_detail": _NEANT,
        "primes_total": 0.0,
        "primes_detail": _NEANT,
    }
    if not employee_id or not supabase_client:
        return empty
    try:
        resp = (
            supabase_client.table("payslips")
            .select("year, month, payslip_data")
            .eq("employee_id", employee_id)
            .order("year", desc=True)
            .order("month", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        row = resp.data if resp and hasattr(resp, "data") else None
        if not row:
            return empty
        pdata = row.get("payslip_data") or {}
        hs_brut = safe_float(
            pdata.get("remuneration_brute_heures_supp")
            or pdata.get("remuneration_hs")
            or 0
        )
        hs_hours = safe_float(
            pdata.get("total_heures_supp") or pdata.get("heures_supplementaires") or 0
        )
        primes_total = safe_float(pdata.get("total_primes") or 0)
        period = f"{row.get('month', '—'):02d}/{row.get('year', '—')}"
        hs_detail = (
            f"{hs_hours:.2f} h — bulletin {period}"
            if hs_brut > 0 or hs_hours > 0
            else _NEANT
        )
        primes_detail = (
            f"Bulletin {period}" if primes_total > 0 else _NEANT
        )
        return {
            "hs_brut": hs_brut,
            "hs_detail": hs_detail,
            "primes_total": primes_total,
            "primes_detail": primes_detail,
        }
    except Exception:
        return empty


def get_salary_prorata(
    employee_data: Dict[str, Any], exit_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Calcule le prorata du salaire du dernier mois"""
    try:
        salaire_base_obj = employee_data.get("salaire_de_base", {})
        if isinstance(salaire_base_obj, dict):
            salaire_base = safe_float(salaire_base_obj.get("valeur", 0))
        else:
            salaire_base = safe_float(salaire_base_obj, 0)

        # Date de fin du contrat
        exit_date_str = exit_data.get("last_working_day", "")
        if isinstance(exit_date_str, str):
            exit_date = datetime.fromisoformat(
                exit_date_str.replace("Z", "+00:00")
            ).date()
        else:
            exit_date = exit_date_str

        # Date de début du mois
        mois_debut = date(exit_date.year, exit_date.month, 1)

        # Nombre de jours dans le mois
        if exit_date.month == 12:
            mois_fin = date(exit_date.year + 1, 1, 1)
        else:
            mois_fin = date(exit_date.year, exit_date.month + 1, 1)
        jours_dans_mois = (mois_fin - mois_debut).days

        # Nombre de jours travaillés dans le mois
        jours_travailles = (exit_date - mois_debut).days + 1

        # Prorata
        salaire_prorata = (
            (salaire_base / jours_dans_mois) * jours_travailles
            if jours_dans_mois > 0
            else 0
        )

        return {
            "base_mensuelle": salaire_base,
            "jours_dans_mois": jours_dans_mois,
            "jours_travailles": jours_travailles,
            "montant_brut": salaire_prorata,
            "cotisations": 0.0,  # À calculer si nécessaire
            "net": salaire_prorata,  # Approximation
        }
    except Exception:
        return {
            "base_mensuelle": 0.0,
            "jours_dans_mois": 0,
            "jours_travailles": 0,
            "montant_brut": 0.0,
            "cotisations": 0.0,
            "net": 0.0,
        }


def compute_remunerations_section(
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    section_title: str = "RÉMUNÉRATIONS ACQUISES",
    employee_id: Optional[str] = None,
    supabase_client: Any = None,
) -> Tuple[Dict[str, Any], float, float, float]:
    """
    Calcule la section « Rémunérations acquises ».

    Returns:
        Tuple ``(section, total_brut, total_cotisations, total_net)`` où ``section``
        est une section de montants prête pour ``html_renderer``.
    """
    rows = []

    total_brut_remun = 0.0
    total_cotisations_remun = 0.0
    total_net_remun = 0.0

    # 1. Salaire du dernier mois (proratisé)
    salaire_data = get_salary_prorata(employee_data, exit_data)
    base_mensuelle = safe_float(salaire_data.get("base_mensuelle", 0))
    jours_trav = salaire_data.get("jours_travailles", 0)
    jours_mois = salaire_data.get("jours_dans_mois", 0)
    brut_salaire = safe_float(salaire_data.get("montant_brut", 0))
    cotis_salaire = safe_float(salaire_data.get("cotisations", 0))
    net_salaire = safe_float(salaire_data.get("net", brut_salaire))

    if base_mensuelle == 0:
        detail_salaire = _NEANT
    else:
        detail_salaire = (
            f"Base : {format_currency(base_mensuelle)} / {jours_mois} jours "
            f"× {jours_trav} jours travaillés"
        )

    rows.append(amount_row("Salaire du dernier mois", detail_salaire, brut_salaire))
    total_brut_remun += brut_salaire
    total_cotisations_remun += cotis_salaire
    total_net_remun += net_salaire

    payslip_extras = _fetch_last_payslip_extras(
        employee_id or employee_data.get("id"),
        supabase_client,
    )
    hs_brut = safe_float(payslip_extras.get("hs_brut", 0))
    rows.append(
        amount_row(
            "Heures supplémentaires / complémentaires",
            payslip_extras.get("hs_detail", _NEANT),
            hs_brut,
        )
    )
    total_brut_remun += hs_brut

    primes_total = safe_float(payslip_extras.get("primes_total", 0))
    rows.append(
        amount_row(
            "Primes et variables acquises",
            payslip_extras.get("primes_detail", _NEANT),
            primes_total,
        )
    )
    total_brut_remun += primes_total

    avantages_total = 0.0
    rows.append(amount_row("Avantages en nature", _NEANT, avantages_total))
    total_brut_remun += avantages_total

    section = amounts_section(section_title, rows)
    return section, total_brut_remun, total_cotisations_remun, total_net_remun


def compute_conges_section(
    indemnities: Dict[str, Any],
    section_title: str = "CONGÉS PAYÉS",
    include_cp_preavis: bool = False,
    cp_preavis_detail: str = _NEANT,
    montant_cp_preavis: float = 0.0,
) -> Tuple[Dict[str, Any], float]:
    """
    Calcule la section « Congés payés ».

    Returns:
        Tuple ``(section, montant_total_conges)``.
    """
    indemnite_conges = indemnities.get("indemnite_conges", {})
    jours_restants = safe_float(indemnite_conges.get("jours_restants", 0))
    montant_conges = safe_float(indemnite_conges.get("montant", 0))
    details_conges = indemnite_conges.get("details", {})
    methode = (
        details_conges.get("methode_retenue", "maintien")
        if details_conges
        else "maintien"
    )
    cp_acquis = details_conges.get("conges_acquis") if details_conges else None
    cp_pris = details_conges.get("conges_pris") if details_conges else None

    detail_conges_text = f"{jours_restants:.2f} jours restants"
    if cp_acquis is not None and cp_pris is not None:
        detail_conges_text += f" ({cp_acquis:.0f} acquis − {cp_pris:.0f} pris)"
    detail_conges_text += f" — Méthode : {methode}"
    if jours_restants == 0 and montant_conges == 0:
        detail_conges_text = _NEANT

    rows = [
        amount_row(
            "Indemnité compensatrice de congés payés",
            detail_conges_text,
            montant_conges,
        )
    ]

    if include_cp_preavis:
        rows.append(
            amount_row(
                "Congés payés afférents au préavis",
                cp_preavis_detail,
                montant_cp_preavis,
            )
        )

    section = amounts_section(section_title, rows)
    return section, montant_conges + montant_cp_preavis


def compute_autres_regularisations_section(
    section_title: str = "AUTRES RÉGULARISATIONS",
) -> Dict[str, Any]:
    """Section « Autres régularisations » (RTT / frais professionnels)."""
    rows = [
        amount_row("RTT / repos compensateurs", _NEANT, None),
        amount_row("Frais professionnels", _NEANT, None),
    ]
    return amounts_section(section_title, rows)


def compute_retenues_section(
    section_title: str = "RETENUES ÉVENTUELLES",
) -> Dict[str, Any]:
    """Section « Retenues éventuelles »."""
    rows = [amount_row("Retenues sur salaire", _NEANT, None)]
    return amounts_section(section_title, rows)
