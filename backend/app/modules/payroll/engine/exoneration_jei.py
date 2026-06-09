"""Exonération JEI — cotisations patronales d'assurances sociales et allocations familiales."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Set

from app.core.logging import get_logger, log_payroll_debug
from app.modules.jei_settings.domain.exonerations_interfaces import (
    AbstractJeiExonerationsRepository,
)
from app.modules.payroll.engine import legal_constants as lc
from app.modules.payroll.engine.contexte import ContextePaie
from app.modules.payroll.engine.cotisations_rubriques import enrichir_ligne_cotisation

logger = get_logger("modules.payroll.engine.exoneration_jei")

# Alias d'identifiants cotisation (catalogue scrapé vs snapshots tests).
COTI_ID_ALIASES: Dict[str, str] = {
    "vieillesse_plafonnee": "retraite_secu_plafond",
    "vieillesse_deplafonnee": "retraite_secu_deplafond",
}

DEFAULT_COTISATIONS_EXONEREES = frozenset(
    {
        "securite_sociale_maladie",
        "retraite_secu_plafond",
        "retraite_secu_deplafond",
        "allocations_familiales",
    }
)


def _normaliser_coti_id(coti_id: Optional[str]) -> Optional[str]:
    if not coti_id:
        return None
    return COTI_ID_ALIASES.get(coti_id, coti_id)


def _cotisations_exonerees(config: Dict[str, Any]) -> Set[str]:
    raw = config.get("cotisations_exonerees_patronales") or list(
        DEFAULT_COTISATIONS_EXONEREES
    )
    normalised: Set[str] = set()
    for cid in raw:
        normalised.add(_normaliser_coti_id(str(cid)) or str(cid))
    return normalised


def plafond_remuneration_jei(
    contexte: ContextePaie,
    heures_remunerees_mois: float,
    facteur_smic: float = 4.5,
) -> float:
    """Plafond individuel : facteur × SMIC horaire × heures rémunérées (max durée légale)."""
    heures_legales_mois = round((lc.DUREE_LEGALE_HEBDO * 52) / 12, 2)
    heures_retenues = min(heures_remunerees_mois, heures_legales_mois)
    return round(contexte.smic_horaire * facteur_smic * heures_retenues, 2)


def mois_actifs_annuel(date_creation: date, year: int) -> int:
    """Nombre de mois actifs pour le prorata du plafond 5 PASS."""
    if date_creation.year > year:
        return 0
    if date_creation.year < year:
        return 12
    return max(0, 13 - date_creation.month)


def plafond_annuel_etablissement(
    contexte: ContextePaie,
    year: int,
    config: Dict[str, Any],
) -> float:
    """Plafond annuel d'exonération = facteur PASS × PASS annuel, proratisé si besoin."""
    facteur = float(config.get("facteur_pass_plafond_annuel", 5))
    pass_annuel = float(contexte.baremes.get("pss", {}).get("annuel", 0.0) or 0.0)
    if pass_annuel <= 0:
        return 0.0

    jei = contexte.entreprise.get("parametres_paie", {}).get("jei", {}) or {}
    date_str = jei.get("date_creation_etablissement")
    mois = 12
    if date_str:
        try:
            creation = date.fromisoformat(str(date_str)[:10])
            mois = mois_actifs_annuel(creation, year)
        except ValueError:
            mois = 12

    return round(facteur * pass_annuel * (mois / 12.0), 2)


def _montant_exonere_ligne(
    ligne: Dict[str, Any],
    plafond_remuneration: float,
    cotisations_exonerees: Set[str],
) -> float:
    coti_id = _normaliser_coti_id(ligne.get("coti_id"))
    if not coti_id or coti_id not in cotisations_exonerees:
        return 0.0

    montant_patronal = float(ligne.get("montant_patronal") or 0.0)
    if montant_patronal <= 0:
        return 0.0

    base = ligne.get("base")
    if base is None:
        return 0.0
    base_f = float(base)
    if base_f <= 0:
        return 0.0

    assiette_exoneree = min(base_f, plafond_remuneration)
    return round(montant_patronal * assiette_exoneree / base_f, 2)


def _appliquer_plafond_etablissement(
    montant_calcule: float,
    contexte: ContextePaie,
    config: Dict[str, Any],
    *,
    company_id: Optional[str],
    employee_id: Optional[str],
    year: Optional[int],
    month: Optional[int],
    exonerations_repo: Optional[AbstractJeiExonerationsRepository],
) -> float:
    if montant_calcule <= 0 or not all([company_id, employee_id, year, month]):
        return montant_calcule

    plafond = plafond_annuel_etablissement(contexte, int(year), config)
    if plafond <= 0:
        return montant_calcule

    if exonerations_repo is None:
        return montant_calcule

    cumul = exonerations_repo.sum_annual_excluding_month(
        str(company_id), int(year), str(employee_id), int(month)
    )
    disponible = max(0.0, round(plafond - cumul, 2))
    final = round(min(montant_calcule, disponible), 2)

    exonerations_repo.upsert_monthly(
        str(company_id), int(year), int(month), str(employee_id), final
    )
    if final < montant_calcule:
        log_payroll_debug(
            logger,
            f"INFO JEI: plafond 5 PASS — exonération écrêtée {montant_calcule:.2f} → {final:.2f} € "
            f"(cumul annuel {cumul:.2f} / plafond {plafond:.2f})",
        )
    return final


def calculer_exoneration_jei(
    contexte: ContextePaie,
    lignes_cotisations: List[Dict[str, Any]],
    heures_remunerees_mois: float,
    *,
    company_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    exonerations_repo: Optional[AbstractJeiExonerationsRepository] = None,
) -> Optional[Dict[str, Any]]:
    """
    Calcule l'exonération JEI sur les cotisations patronales éligibles.

    Retourne une ligne de bulletin (montant patronal négatif) ou None si non applicable.
    """
    config = contexte.baremes.get("jei", {}) or {}
    if not config.get("actif", False):
        return None

    payroll_year = year or getattr(contexte, "year", None)
    payroll_month = month or getattr(contexte, "month", None)
    if payroll_year is None or payroll_month is None:
        return None

    if not contexte.jei_entreprise_active(int(payroll_year), int(payroll_month)):
        return None

    if not contexte.is_personnel_rd_eligible_jei:
        return None

    facteur_smic = float(config.get("facteur_smic_plafond", 4.5))
    plafond_rem = plafond_remuneration_jei(contexte, heures_remunerees_mois, facteur_smic)
    cotisations_exonerees = _cotisations_exonerees(config)

    montant_brut = 0.0
    for ligne in lignes_cotisations:
        montant_brut += _montant_exonere_ligne(ligne, plafond_rem, cotisations_exonerees)

    jei_params = contexte.entreprise.get("parametres_paie", {}).get("jei", {}) or {}
    taux = float(jei_params.get("taux_exoneration", 1.0) or 1.0)
    montant_brut = round(montant_brut * taux, 2)

    if montant_brut <= 0:
        return None

    montant_final = _appliquer_plafond_etablissement(
        montant_brut,
        contexte,
        config,
        company_id=company_id,
        employee_id=employee_id,
        year=int(payroll_year),
        month=int(payroll_month),
        exonerations_repo=exonerations_repo,
    )

    if montant_final <= 0:
        return None

    log_payroll_debug(
        logger,
        f"INFO JEI: exonération {montant_final:.2f} € "
        f"(plafond rémunération {plafond_rem:.2f} €, taux {taux:.0%})",
    )

    _, num_days = calendar.monthrange(int(payroll_year), int(payroll_month))
    return enrichir_ligne_cotisation(
        {
            "libelle": "Exonération JEI (cotisations patronales)",
            "base": round(min(plafond_rem, contexte.salaire_base_mensuel), 2),
            "taux_salarial": None,
            "montant_salarial": 0.0,
            "taux_patronal": None,
            "montant_patronal": -montant_final,
            "jei_plafond_remuneration": plafond_rem,
            "jei_montant_brut": montant_brut,
        },
        coti_id="exoneration_jei",
    )


def jei_applicable(contexte: ContextePaie, year: int, month: int) -> bool:
    """Indique si l'exonération JEI peut s'appliquer (sans calculer le montant)."""
    config = contexte.baremes.get("jei", {}) or {}
    if not config.get("actif", False):
        return False
    return (
        contexte.jei_entreprise_active(year, month)
        and contexte.is_personnel_rd_eligible_jei
    )
