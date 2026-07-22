"""Helpers tests paie — contexte injecté sans Supabase."""

from __future__ import annotations

import json
import calendar
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.contexte import ContextePaie

from .fixtures.baremes_snapshot import baremes_snapshot, entreprise_snapshot


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build_test_contexte(
    *,
    statut: str = "Non-Cadre",
    salaire_base: float = 2500.0,
    duree_hebdo: float = 35.0,
    effectif: int = 10,
    taux_pas: float = 0.0,
    baremes: Optional[Dict[str, Any]] = None,
    type_contrat: str = "",
    date_debut_execution: str = "",
    date_conclusion_contrat: str = "",
    date_naissance: str = "",
    date_entree: str = "2020-01-01",
    date_fin_contrat: str = "",
    prior_service_months: int | None = None,
    maintien_regime_apprenti: bool = False,
    cumuls: Optional[Dict[str, Any]] = None,
    specificites_extra: Optional[Dict[str, Any]] = None,
    is_temps_partiel: bool = False,
    proratiser_plafond_ss: bool = False,
    jei_enabled: bool = False,
    date_creation_etablissement: str | None = None,
    taux_exoneration_jei: float = 1.0,
) -> ContextePaie:
    tmp = Path(tempfile.mkdtemp(prefix="payroll_test_"))
    contrat = {
        "salarie": {
            "nom": "Test",
            "prenom": "Jean",
            "nir": "",
            "date_naissance": date_naissance,
        },
        "contrat": {
            "date_entree": date_entree,
            "date_fin_contrat": date_fin_contrat,
            "prior_service_months": prior_service_months,
            "statut": statut,
            "emploi": "Employé",
            "type_contrat": type_contrat,
            "date_debut_execution": date_debut_execution,
            "date_conclusion_contrat": date_conclusion_contrat,
            "temps_travail": {
                "duree_hebdomadaire": duree_hebdo,
                "is_temps_partiel": is_temps_partiel,
                "proratiser_plafond_ss": proratiser_plafond_ss,
            },
        },
        "remuneration": {
            "salaire_de_base": {"valeur": salaire_base},
            "classification_conventionnelle": {},
            "avantages_en_nature": {},
        },
        "specificites_paie": {
            "prevoyance": "NON",
            "prelevement_a_la_source": {"taux": taux_pas},
            "is_alsace_moselle": False,
            "maintien_regime_apprenti": maintien_regime_apprenti,
            **(specificites_extra or {}),
        },
    }
    entreprise = {
        "entreprise": entreprise_snapshot(
            effectif,
            jei_enabled=jei_enabled,
            date_creation_etablissement=date_creation_etablissement,
            taux_exoneration=taux_exoneration_jei,
        )
    }
    _write_json(tmp / "contrat.json", contrat)
    _write_json(tmp / "entreprise.json", entreprise)
    _write_json(tmp / "cumuls.json", {"cumuls": cumuls or {}})
    return ContextePaie(
        chemin_contrat=str(tmp / "contrat.json"),
        chemin_entreprise=str(tmp / "entreprise.json"),
        chemin_cumuls=str(tmp / "cumuls.json"),
        chemin_data_dir=str(tmp),
        baremes_override=baremes or baremes_snapshot(),
    )


def _weekday_calendrier(
    year: int, month: int, heures: float = 7.0
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
                    "heures": heures,
                }
            )
    return out


def run_bulletin_pipeline_heures(
    contexte: ContextePaie,
    *,
    year: int = 2026,
    month: int = 4,
    primes_soumises: Optional[List[Dict[str, Any]]] = None,
    calendrier: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    contexte.year = year
    date_debut = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    date_fin = date(year, month, num_days)
    cal = calendrier or _weekday_calendrier(year, month)
    brut_res = calculer_salaire_brut(
        contexte,
        calendrier_saisie=cal,
        date_debut_periode=date_debut,
        date_fin_periode=date_fin,
        primes_saisies=primes_soumises or [],
    )
    brut = brut_res["salaire_brut_total"]
    hs = brut_res["remuneration_brute_heures_supp"]
    ths = brut_res["total_heures_supp"]
    lignes, total_sal = calculer_cotisations(contexte, brut, hs, ths)
    heures_mois = (contexte.duree_hebdo_contrat * 52) / 12
    red = calculer_reduction_generale(contexte, brut, heures_mois)
    if red:
        lignes.append(red)
    nets = calculer_net_et_impot(
        contexte, brut, lignes, total_sal, [], hs, 0.0, []
    )
    total_pat = sum(l.get("montant_patronal", 0) or 0 for l in lignes)
    return {
        "brut": round(brut, 2),
        "total_cotisations_salariales": round(total_sal, 2),
        "total_cotisations_patronales": round(total_pat, 2),
        "net_imposable": nets["net_imposable"],
        "net_a_payer": nets["net_a_payer"],
        "cout_employeur": round(brut + total_pat, 2),
    }


def run_bulletin_pipeline_forfait(
    contexte: ContextePaie,
    *,
    year: int = 2026,
    month: int = 4,
    primes_soumises: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    contexte.year = year
    date_debut = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    date_fin = date(year, month, num_days)
    _, num_days = calendar.monthrange(year, month)
    cal = [
        {"date_complete": date(year, month, day).isoformat(), "type": "travail", "heures": 1.0}
        for day in range(1, num_days + 1)
        if date(year, month, day).weekday() < 5
    ]
    brut_res = calculer_salaire_brut_forfait(
        contexte,
        calendrier_saisie=cal,
        date_debut_periode=date_debut,
        date_fin_periode=date_fin,
        primes_saisies=primes_soumises or [],
    )
    brut = brut_res["salaire_brut_total"]
    hs = brut_res["remuneration_brute_heures_supp"]
    ths = brut_res["total_heures_supp"]
    lignes, total_sal = calculer_cotisations(contexte, brut, hs, ths)
    jours = brut_res.get("nombre_jours_travailles", 0)
    red = calculer_reduction_generale(contexte, brut, jours * 7.0)
    if red:
        lignes.append(red)
    nets = calculer_net_et_impot(
        contexte, brut, lignes, total_sal, [], hs, 0.0, []
    )
    total_pat = sum(l.get("montant_patronal", 0) or 0 for l in lignes)
    return {
        "brut": round(brut, 2),
        "total_cotisations_salariales": round(total_sal, 2),
        "total_cotisations_patronales": round(total_pat, 2),
        "net_imposable": nets["net_imposable"],
        "net_a_payer": nets["net_a_payer"],
        "cout_employeur": round(brut + total_pat, 2),
    }
