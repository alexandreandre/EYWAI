"""Reconstruction des cumuls de paie depuis les DSN importées."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import payroll_engine_employee_folder
from app.modules.dsn_import.domain.model import IndividuBlock, ParsedDsnSet
from app.modules.dsn_import.domain.rubriques import (
    BASE_ASSUJETTIE_BRUT_CODES,
    REDUCTION_GENERALE_COT_CODES,
    REMUNERATION_BRUT_TYPES,
)


def _month_from_period(period: Optional[str]) -> Optional[int]:
    if not period or len(period) < 7:
        return None
    try:
        return int(period.split("-")[1])
    except ValueError:
        return None


def _normalize_rem_type(type_code: str) -> str:
    """Normalise le code type rémunération DSN (001 ou '001 - Libellé')."""
    if not type_code:
        return ""
    val = type_code.strip()
    if " - " in val:
        val = val.split(" - ", 1)[0].strip()
    clean = val.replace(" ", "")
    if clean.isdigit():
        return clean.zfill(3)[:3]
    return val


def _looks_like_dsn_date(value: str) -> bool:
    clean = (value or "").replace(" ", "").replace("-", "")
    return len(clean) == 8 and clean.isdigit()


def _remuneration_montant(rem) -> float:
    """Montant d'une ligne rémunération (.013 ou champ parsé)."""
    if rem.montant > 0:
        return rem.montant
    for key, val in (rem.rubriques or {}).items():
        if key.endswith(".013"):
            try:
                return float(str(val).replace(",", ".").replace(" ", ""))
            except ValueError:
                pass
    return 0.0


def _is_brut_remuneration(type_code: str, montant: float) -> bool:
    """Indique si la ligne rémunération contribue au brut."""
    normalized = _normalize_rem_type(type_code)
    if normalized in REMUNERATION_BRUT_TYPES:
        return True
    # Fichiers mal typés (type = date en .001 norme courante) mais montant présent
    if montant > 0 and (_looks_like_dsn_date(type_code) or not normalized):
        return True
    return False


def _brut_from_bases(versement) -> float:
    bases = versement.rubriques.get("bases") if versement.rubriques else None
    if not isinstance(bases, dict):
        return 0.0
    for code in sorted(BASE_ASSUJETTIE_BRUT_CODES):
        val = bases.get(code)
        if val and float(val) > 0:
            return round(float(val), 2)
    return 0.0


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
            ver_brut = 0.0
            for rem in ver.remunerations:
                montant = _remuneration_montant(rem)
                if _is_brut_remuneration(rem.type_code, montant):
                    ver_brut += montant
                heures += rem.heures
            if ver_brut <= 0:
                ver_brut = _brut_from_bases(ver)
            brut += ver_brut
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
            siret = ParsedDsnSet._resolve_etab_siret(etab, dsn_file)
            if not siret:
                continue
            for ind in etab.individus:
                if not ind.identifiant:
                    continue
                key = (siret, ind.identifiant)
                totals = extract_monthly_totals(ind)
                prev = running.get(key)
                cumuls_doc = build_cumuls_for_month(prev, totals, month)
                running[key] = cumuls_doc
                items.append(
                    {
                        "item_type": "cumul",
                        "source_ref": f"cumul:{siret}:{ind.identifiant}:{period}",
                        "action": "create",
                        "mapped_payload": {
                            "siret": siret,
                            "nir": ind.nir,
                            "employee_key": ind.identifiant,
                            "period": period,
                            "month": month,
                            "cumuls_document": cumuls_doc,
                            "month_totals": totals,
                        },
                        "label": f"Cumuls {period} — {ind.prenom} {ind.nom}".strip(),
                    }
                )
    return items


def build_cumuls_summary(cumul_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les stats de cumuls pour l'écran preview (par période + totaux)."""
    if not cumul_items:
        return {
            "period_count": 0,
            "employee_count": 0,
            "entry_count": 0,
            "by_period": [],
            "totals": {},
        }

    by_period: Dict[str, Dict[str, Any]] = {}
    employees: set = set()

    for it in cumul_items:
        payload = it.get("mapped_payload") or {}
        period = str(payload.get("period") or "")
        if not period:
            continue
        month_totals = payload.get("month_totals") or {}
        emp_key = payload.get("employee_key") or payload.get("nir") or it.get("source_ref")
        employees.add(emp_key)

        bucket = by_period.setdefault(
            period,
            {
                "period": period,
                "employee_count": 0,
                "employees_with_brut": 0,
                "employees_without_brut": 0,
                "brut": 0.0,
                "net_imposable": 0.0,
                "pas": 0.0,
                "heures": 0.0,
                "reduction_generale_patronale": 0.0,
            },
        )
        bucket["employee_count"] += 1
        brut = float(month_totals.get("brut") or 0)
        if brut > 0:
            bucket["employees_with_brut"] += 1
        else:
            bucket["employees_without_brut"] += 1
        bucket["brut"] = round(bucket["brut"] + brut, 2)
        bucket["net_imposable"] = round(
            bucket["net_imposable"] + float(month_totals.get("net_imposable") or 0), 2
        )
        bucket["pas"] = round(bucket["pas"] + float(month_totals.get("pas") or 0), 2)
        bucket["heures"] = round(bucket["heures"] + float(month_totals.get("heures") or 0), 2)
        bucket["reduction_generale_patronale"] = round(
            bucket["reduction_generale_patronale"]
            + float(month_totals.get("reduction_generale_patronale") or 0),
            2,
        )

    periods_sorted = sorted(by_period.keys())
    by_period_list = []
    for period in periods_sorted:
        row = by_period[period]
        ec = row["employee_count"]
        row["avg_brut"] = round(row["brut"] / ec, 2) if ec else 0.0
        by_period_list.append(row)

    totals = {
        "brut": round(sum(r["brut"] for r in by_period_list), 2),
        "net_imposable": round(sum(r["net_imposable"] for r in by_period_list), 2),
        "pas": round(sum(r["pas"] for r in by_period_list), 2),
        "heures": round(sum(r["heures"] for r in by_period_list), 2),
        "reduction_generale_patronale": round(
            sum(r["reduction_generale_patronale"] for r in by_period_list), 2
        ),
    }

    return {
        "period_count": len(by_period_list),
        "employee_count": len(employees),
        "entry_count": len(cumul_items),
        "by_period": by_period_list,
        "totals": totals,
    }


def write_cumuls_file(employee_folder_name: str, month: int, document: Dict[str, Any]) -> Path:
    """Écrit cumuls/MM.json sur disque."""
    folder = payroll_engine_employee_folder(employee_folder_name)
    cumuls_dir = folder / "cumuls"
    cumuls_dir.mkdir(parents=True, exist_ok=True)
    path = cumuls_dir / f"{month:02d}.json"
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
