"""Construction des blocs rémunération DSN (S21.G00.51) depuis un bulletin EYWAI."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.model import RemunerationBlock


@dataclass
class RemunerationBuildResult:
    remunerations: List[RemunerationBlock]
    activites: List[Dict[str, Any]]
    heures_activite: float
    salaire_base: float
    hs_structurelles_montant: float
    hs_structurelles_heures: float
    hs_aleatoires_montant: float
    hs_aleatoires_heures: float
    salaire_retabli: float


def _f(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _lib(line: Dict[str, Any]) -> str:
    return str(line.get("libelle") or "").strip().lower()


def _is_sous_total(line: Dict[str, Any]) -> bool:
    if line.get("is_sous_total"):
        return True
    lib = _lib(line)
    return lib.startswith("sous-total") or lib.startswith("sous total")


def _is_hs_structurelle(lib: str) -> bool:
    return "suppl" in lib and "structurell" in lib


def _is_hs_aleatoire(lib: str) -> bool:
    if "suppl" not in lib and "heure" not in lib:
        return False
    if "structurell" in lib:
        return False
    return bool(
        re.search(r"heures?\s+suppl|h\.?\s*s\.?|compl[eé]mentaires?", lib, re.I)
    )


def _iter_brut_lines(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    calc = payslip_data.get("calcul_du_brut")
    if isinstance(calc, list):
        return [x for x in calc if isinstance(x, dict)]
    if isinstance(calc, dict):
        lines = calc.get("lignes") or calc.get("lines") or []
        if isinstance(lines, list):
            return [x for x in lines if isinstance(x, dict)]
    return []


def _sum_absence_pertes(payslip_data: Dict[str, Any]) -> float:
    total = 0.0
    for key in ("details_absences", "details_conges"):
        rows = payslip_data.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                total += _f(row.get("perte"))
    return round(total, 2)


def _rem_block(
    *,
    type_code: str,
    montant: float,
    period_start: str,
    period_end: str,
    heures: float = 0.0,
    contrat_ref: str = "00000",
) -> RemunerationBlock:
    rubriques: Dict[str, str] = {
        "S21.G00.51.001": period_start,
        "S21.G00.51.002": period_end,
        "S21.G00.51.010": contrat_ref,
        "S21.G00.51.011": type_code,
        "S21.G00.51.013": f"{round(montant, 2):.2f}",
    }
    if heures > 0:
        rubriques["S21.G00.51.012"] = f"{round(heures, 2):.2f}"
    return RemunerationBlock(
        type_code=type_code,
        montant=round(montant, 2),
        heures=round(heures, 2) if heures > 0 else 0.0,
        rubriques=rubriques,
    )


def analyze_calcul_du_brut(payslip_data: Dict[str, Any]) -> Dict[str, float]:
    """Agrège le détail brut pour ventiler les types DSN."""
    salaire_base = 0.0
    sous_total_contractuel = 0.0
    hs_struct_m = hs_struct_h = 0.0
    hs_alea_m = hs_alea_h = 0.0
    autres_gains = 0.0
    heures_base = 0.0

    for line in _iter_brut_lines(payslip_data):
        lib = _lib(line)
        gain = _f(line.get("gain"))
        quantite = _f(line.get("quantite"))
        if _is_sous_total(line):
            if "contractuel" in lib or sous_total_contractuel <= 0:
                sous_total_contractuel = gain
            continue
        if "salaire de base" in lib or lib.startswith("salaire base"):
            salaire_base += gain
            heures_base += quantite
            continue
        if _is_hs_structurelle(lib):
            hs_struct_m += gain
            hs_struct_h += quantite
            continue
        if _is_hs_aleatoire(lib):
            hs_alea_m += gain
            hs_alea_h += quantite
            continue
        # Primes et autres éléments positifs (hors pertes)
        if gain:
            autres_gains += gain

    # Repli : si pas de sous-total, reconstituer
    if sous_total_contractuel <= 0:
        sous_total_contractuel = round(salaire_base + hs_struct_m, 2)

    return {
        "salaire_base": round(salaire_base, 2),
        "sous_total_contractuel": round(sous_total_contractuel, 2),
        "hs_structurelles_montant": round(hs_struct_m, 2),
        "hs_structurelles_heures": round(hs_struct_h, 2),
        "hs_aleatoires_montant": round(hs_alea_m, 2),
        "hs_aleatoires_heures": round(hs_alea_h, 2),
        "autres_gains": round(autres_gains, 2),
        "heures_base": round(heures_base, 2),
        "absence_pertes": _sum_absence_pertes(payslip_data),
    }


def build_remunerations_from_payslip(
    payslip_data: Dict[str, Any],
    *,
    brut: float,
    period_start: str,
    period_end: str,
    period: str,
    contrat_ref: str = "00000",
) -> RemunerationBuildResult:
    """Produit les types 001/002/003/010/017/018/028/029 alignés sur Cegid."""
    parts = analyze_calcul_du_brut(payslip_data)
    brut_r = round(float(brut or 0), 2)

    # 010 = salaire de base contractuel (sous-total Cegid)
    montant_010 = parts["sous_total_contractuel"] or parts["salaire_base"] or brut_r

    # 017 / 018 depuis le détail
    m_017, h_017 = parts["hs_aleatoires_montant"], parts["hs_aleatoires_heures"]
    m_018, h_018 = parts["hs_structurelles_montant"], parts["hs_structurelles_heures"]

    # 003 salaire rétabli : sans absences = brut ; avec absences = gains avant pertes
    retabli = brut_r
    if parts["absence_pertes"] > 0.005:
        retabli = round(
            parts["sous_total_contractuel"]
            + parts["hs_aleatoires_montant"]
            + parts["autres_gains"],
            2,
        )
        if retabli < brut_r:
            retabli = brut_r
    elif parts["sous_total_contractuel"] > 0 and parts["autres_gains"] >= 0:
        # Cas normal Cegid : 003 = 001 = brut
        retabli = brut_r

    remus: List[RemunerationBlock] = [
        _rem_block(
            type_code="001",
            montant=brut_r,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="002",
            montant=brut_r,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="003",
            montant=retabli,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="010",
            montant=round(montant_010, 2),
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
    ]
    if m_017 > 0 or h_017 > 0:
        remus.append(
            _rem_block(
                type_code="017",
                montant=m_017,
                heures=h_017,
                period_start=period_start,
                period_end=period_end,
                contrat_ref=contrat_ref,
            )
        )
    if m_018 > 0 or h_018 > 0:
        remus.append(
            _rem_block(
                type_code="018",
                montant=m_018,
                heures=h_018,
                period_start=period_start,
                period_end=period_end,
                contrat_ref=contrat_ref,
            )
        )
    # 028 ~ assiette CSG déclarée comme rémunération (Cegid = 001)
    remus.append(
        _rem_block(
            type_code="028",
            montant=brut_r,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        )
    )
    # 029 suit le rétabli quand distinct, sinon le brut (comportement Cegid)
    remus.append(
        _rem_block(
            type_code="029",
            montant=retabli,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        )
    )

    # Activités : jours calendaires (unité 40) + heures payées (base + HS)
    try:
        year, month = [int(x) for x in period.split("-")[:2]]
        days = calendar.monthrange(year, month)[1]
    except Exception:
        days = 30
    heures_activite = round(
        (parts["heures_base"] or 0)
        + parts["hs_structurelles_heures"]
        + parts["hs_aleatoires_heures"],
        2,
    )
    if heures_activite <= 0:
        heures_activite = round(
            _f(payslip_data.get("heures_remunerees"))
            or _f(payslip_data.get("heures_travaillees"))
            or 151.67,
            2,
        )

    activites: List[Dict[str, Any]] = [
        {"type": "01", "mesure": float(days), "unite": "40"},
        {"type": "01", "mesure": heures_activite, "unite": ""},
    ]

    return RemunerationBuildResult(
        remunerations=remus,
        activites=activites,
        heures_activite=heures_activite,
        salaire_base=parts["salaire_base"],
        hs_structurelles_montant=m_018,
        hs_structurelles_heures=h_018,
        hs_aleatoires_montant=m_017,
        hs_aleatoires_heures=h_017,
        salaire_retabli=retabli,
    )
