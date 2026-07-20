"""
Pipeline moteur de paie pour les simulations (heures, sans I/O fichiers).
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine import legal_constants as lc
from app.modules.payroll.engine.contexte import ContextePaie


def _weekday_calendrier(
    year: int, month: int, heures_par_jour: float
) -> List[Dict[str, Any]]:
    _, num_days = calendar.monthrange(year, month)
    out: List[Dict[str, Any]] = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:
            out.append(
                {
                    "date_complete": d.isoformat(),
                    "type": "travail",
                    "heures": heures_par_jour,
                }
            )
    return out


def _primes_from_saisies(saisies: Dict[str, Any]) -> List[Dict[str, Any]]:
    primes: List[Dict[str, Any]] = []
    for entry in saisies.get("primes") or []:
        if not isinstance(entry, dict):
            continue
        montant = float(entry.get("montant") or entry.get("amount") or 0)
        if montant <= 0:
            continue
        primes.append(
            {
                "libelle": entry.get("libelle") or entry.get("name") or "Prime",
                "montant": montant,
                "prime_id": entry.get("prime_id") or "prime_simulation",
            }
        )
    return primes


def run_simulation_bulletin_pipeline(
    contexte: ContextePaie,
    *,
    month: int,
    year: int,
    saisies: Optional[Dict[str, Any]] = None,
    calendrier: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Exécute le moteur de paie complet et retourne un bulletin_final (dict).
    """
    contexte.year = year
    saisies = saisies or {}
    date_debut = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    date_fin = date(year, month, num_days)

    duree_hebdo = contexte.duree_hebdo_contrat or 35.0
    heures_jour = round(duree_hebdo / 5, 2)
    cal = calendrier or _weekday_calendrier(year, month, heures_jour)

    brut_res = calculer_salaire_brut(
        contexte,
        calendrier_saisie=cal,
        date_debut_periode=date_debut,
        date_fin_periode=date_fin,
        primes_saisies=_primes_from_saisies(saisies),
    )
    salaire_brut = brut_res["salaire_brut_total"]
    details_brut = brut_res["lignes_composants_brut"]
    remuneration_hs = brut_res["remuneration_brute_heures_supp"]
    total_heures_supp = brut_res["total_heures_supp"]

    lignes_cotisations, total_salarial = calculer_cotisations(
        contexte, salaire_brut, remuneration_hs, total_heures_supp
    )
    # SMIC de référence de la réduction : heures rémunérées TOTALES = base
    # normale + TOUTES les heures supp + heures complémentaires. On prend la base
    # LÉGALE (min contrat/légal) et on ajoute `total_heures_supp` (fiable, tous
    # canaux — calendrier ET saisies manuelles) pour ne pas double-compter les HS
    # structurelles déjà incluses dans l'horaire contractuel. Sans les HS, le
    # SMIC de référence est sous-évalué et la réduction générale trop faible.
    heures_mois = (duree_hebdo * 52) / 12
    heures_legales_mois = (lc.DUREE_LEGALE_HEBDO * 52) / 12
    heures_remunerees_reduction = (
        min(heures_mois, heures_legales_mois)
        + float(total_heures_supp or 0.0)
        + float(brut_res.get("heures_complementaires", 0.0) or 0.0)
    )
    ligne_reduction = calculer_reduction_generale(
        contexte, salaire_brut, heures_remunerees_reduction
    )
    if ligne_reduction:
        lignes_cotisations.append(ligne_reduction)

    montant_acompte = float(saisies.get("acompte") or 0)
    resultats_nets = calculer_net_et_impot(
        contexte,
        salaire_brut,
        lignes_cotisations,
        total_salarial,
        [],
        remuneration_hs,
        montant_acompte,
        [],
    )

    return creer_bulletin_final(
        contexte,
        salaire_brut,
        details_brut,
        lignes_cotisations,
        resultats_nets,
        [],
        year,
        month,
    )
