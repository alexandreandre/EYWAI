"""Reconstruction des cumuls de paie depuis les DSN importées."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import payroll_engine_employee_folder
from app.modules.dsn_import.domain.model import IndividuBlock, ParsedDsnSet
from app.modules.dsn_import.domain.rubriques import REDUCTION_GENERALE_COT_CODES, REMUNERATION_BRUT_TYPES


def _month_from_period(period: Optional[str]) -> Optional[int]:
    if not period or len(period) < 7:
        return None
    try:
        return int(period.split("-")[1])
    except ValueError:
        return None


def extract_monthly_totals(ind: IndividuBlock) -> Dict[str, float]:
    """Extrait brut, net imposable, PAS, heures, réduction générale d'un individu."""
    brut = 0.0
    net_imposable = 0.0
    pas = 0.0
    heures = 0.0
    reduction_pat = 0.0

    for contrat in ind.contrats:
        for ver in contrat.versements:
            net_imposable += ver.net_fiscal
            pas += ver.pas
            for rem in ver.remunerations:
                if rem.type_code in REMUNERATION_BRUT_TYPES or rem.type_code in ("", "001"):
                    brut += rem.montant
                heures += rem.heures
            for cot in ver.cotisations:
                if cot.code in REDUCTION_GENERALE_COT_CODES:
                    reduction_pat += abs(cot.montant_patronal)

    return {
        "brut": round(brut, 2),
        "net_imposable": round(net_imposable, 2),
        "pas": round(pas, 2),
        "heures": round(heures, 2),
        "reduction_generale_patronale": round(-reduction_pat, 2) if reduction_pat else 0.0,
    }


def build_cumuls_for_month(
    previous: Optional[Dict[str, Any]], month_totals: Dict[str, float], month: int
) -> Dict[str, Any]:
    """Construit le fichier cumuls/MM.json cumulé."""
    prev_cumuls = {}
    if previous and isinstance(previous.get("cumuls"), dict):
        prev_cumuls = previous["cumuls"]

    cumuls = {
        "brut_total": round(prev_cumuls.get("brut_total", 0.0) + month_totals["brut"], 2),
        "net_imposable": round(
            prev_cumuls.get("net_imposable", 0.0) + month_totals["net_imposable"], 2
        ),
        "impot_preleve_a_la_source": round(
            prev_cumuls.get("impot_preleve_a_la_source", 0.0) + month_totals["pas"], 2
        ),
        "heures_supplementaires_remunerees": prev_cumuls.get(
            "heures_supplementaires_remunerees", 0.0
        ),
        "heures_remunerees": round(
            prev_cumuls.get("heures_remunerees", 0.0) + month_totals["heures"], 2
        ),
        "reduction_generale_patronale": month_totals["reduction_generale_patronale"]
        if month_totals["reduction_generale_patronale"]
        else prev_cumuls.get("reduction_generale_patronale", 0.0),
    }
    return {"cumuls": cumuls, "periode": {"dernier_mois_calcule": month}}


def plan_cumul_items(parsed: ParsedDsnSet) -> List[Dict[str, Any]]:
    """Planifie les items cumuls par salarié et par mois (ordre chronologique)."""
    files_sorted = sorted(
        parsed.files,
        key=lambda f: f.envoi.periode or "",
    )
    # Accumulateur par (siret, nir) -> cumuls courants
    running: Dict[Tuple[str, str], Dict[str, Any]] = {}
    items: List[Dict[str, Any]] = []

    for dsn_file in files_sorted:
        period = ParsedDsnSet._period_from_file(dsn_file)
        month = _month_from_period(period)
        if not month:
            continue
        etabs = ParsedDsnSet._etablissements_from_file(dsn_file)
        for etab in etabs:
            siret = etab.siret
            for ind in etab.individus:
                if not ind.nir:
                    continue
                key = (siret, ind.nir)
                totals = extract_monthly_totals(ind)
                prev = running.get(key)
                cumuls_doc = build_cumuls_for_month(prev, totals, month)
                running[key] = cumuls_doc
                items.append(
                    {
                        "item_type": "cumul",
                        "source_ref": f"cumul:{siret}:{ind.nir}:{period}",
                        "action": "create",
                        "mapped_payload": {
                            "siret": siret,
                            "nir": ind.nir,
                            "period": period,
                            "month": month,
                            "cumuls_document": cumuls_doc,
                            "month_totals": totals,
                        },
                        "label": f"Cumuls {period} — {ind.prenom} {ind.nom}",
                    }
                )
    return items


def write_cumuls_file(employee_folder_name: str, month: int, document: Dict[str, Any]) -> Path:
    """Écrit cumuls/MM.json sur disque."""
    folder = payroll_engine_employee_folder(employee_folder_name)
    cumuls_dir = folder / "cumuls"
    cumuls_dir.mkdir(parents=True, exist_ok=True)
    path = cumuls_dir / f"{month:02d}.json"
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
