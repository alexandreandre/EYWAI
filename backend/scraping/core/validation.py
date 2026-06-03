"""Validation métier avant persistance."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""


def require_year_current(sections: dict, *, key: str = "annee", slack: int = 1) -> ValidationResult:
    """L'année extraite doit être l'année courante ou N-1 (publication décalée)."""
    raw = sections.get(key)
    if raw is None:
        return ValidationResult(True)
    try:
        y = int(raw)
    except (TypeError, ValueError):
        return ValidationResult(False, f"Année invalide: {raw!r}")
    cy = datetime.now().year
    if y < cy - slack or y > cy + 1:
        return ValidationResult(
            False,
            f"Année {y} hors plage attendue [{cy - slack}, {cy + 1}]",
        )
    return ValidationResult(True)


def require_float_range(
    value: Any,
    *,
    name: str,
    min_v: float,
    max_v: float,
) -> ValidationResult:
    if value is None:
        return ValidationResult(False, f"{name} manquant")
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ValidationResult(False, f"{name} non numérique: {value!r}")
    if not (min_v <= f <= max_v):
        return ValidationResult(False, f"{name}={f} hors [{min_v}, {max_v}]")
    return ValidationResult(True)


def require_patronal_rate(value: Any, *, name: str = "patronal") -> ValidationResult:
    return require_float_range(value, name=name, min_v=0.0, max_v=0.5)


def require_non_null_patronal(valeurs: dict) -> ValidationResult:
    pat = valeurs.get("patronal") if isinstance(valeurs, dict) else None
    if pat is None:
        return ValidationResult(False, "patronal manquant ou null")
    return require_patronal_rate(pat)


def validate_all(checks: list[Callable[[], ValidationResult]]) -> ValidationResult:
    for check in checks:
        r = check()
        if not r.ok:
            return r
    return ValidationResult(True)


def _smic_monthly_hours() -> float:
    return 35.0 * 52.0 / 12.0


def normalize_smic_sections(sections: dict) -> dict:
    """Aligne cas_general et smic_horaire_brut sur une seule valeur horaire."""
    out = dict(sections)
    cg = out.get("cas_general")
    sh = out.get("smic_horaire_brut")
    hourly = cg if cg is not None else sh
    if hourly is not None:
        h = float(hourly)
        out["cas_general"] = h
        out["smic_horaire_brut"] = h
    return out


def smic_hourly_rate(sections: dict) -> float | None:
    raw = sections.get("cas_general")
    if raw is None:
        raw = sections.get("smic_horaire_brut")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def validate_smic_sections(sections: dict) -> ValidationResult:
    sections = normalize_smic_sections(sections)
    hourly = smic_hourly_rate(sections)
    checks: list[Callable[[], ValidationResult]] = [
        lambda: require_year_current(sections),
        lambda: require_float_range(hourly, name="smic_horaire", min_v=10.0, max_v=15.0),
    ]
    cg = hourly
    j17 = sections.get("jeune_17_ans")
    jm = sections.get("jeune_moins_17_ans")
    mensuel = sections.get("smic_mensuel_brut")
    if cg is not None and j17 is not None and jm is not None:
        try:
            if float(j17) > float(cg) or float(jm) > float(cg):
                return ValidationResult(
                    False,
                    "Les taux jeunes doivent être <= au cas général",
                )
        except (TypeError, ValueError):
            pass
    if cg is not None and mensuel is not None:
        try:
            expected = float(cg) * _smic_monthly_hours()
            actual = float(mensuel)
            if expected > 0 and abs(actual - expected) / expected > 0.03:
                return ValidationResult(
                    False,
                    "Incohérence horaire/mensuel (territoire ou révision mélangés)",
                )
        except (TypeError, ValueError):
            pass
    return validate_all(checks)


def validate_pss_sections(sections: dict) -> ValidationResult:
    return validate_all(
        [
            lambda: require_year_current(sections),
            lambda: require_float_range(
                sections.get("annuel"), name="annuel", min_v=40000, max_v=60000
            ),
            lambda: require_float_range(
                sections.get("mensuel"), name="mensuel", min_v=3000, max_v=5000
            ),
        ]
    )


def validate_dialogue_social(valeurs: dict) -> ValidationResult:
    return require_non_null_patronal(valeurs)


def validate_csg_valeurs(valeurs: dict) -> ValidationResult:
    sal = valeurs.get("salarial") or {}
    nd = sal.get("non_deductible")
    ded = sal.get("deductible")
    return validate_all(
        [
            lambda: require_float_range(nd, name="non_deductible", min_v=0.02, max_v=0.05),
            lambda: require_float_range(ded, name="deductible", min_v=0.05, max_v=0.10),
        ]
    )


def validate_ij_plafonds(data: dict) -> ValidationResult:
    for key in ("maladie", "maternite_paternite", "at_mp", "at_mp_majoree"):
        v = data.get(key)
        if v is None:
            return ValidationResult(False, f"Plafond IJ manquant: {key}")
        if not (35 <= float(v) <= 500):
            return ValidationResult(False, f"{key}={v} hors plage [35, 500]")
    return ValidationResult(True)


def compare_signatures_float(
    a: dict,
    b: dict,
    keys: list[str],
    *,
    rel_tol: float = 0.01,
    abs_tol: float = 1e-6,
) -> bool:
    for key in keys:
        va, vb = a.get(key), b.get(key)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if not math.isclose(float(va), float(vb), rel_tol=rel_tol, abs_tol=abs_tol):
            return False
    return True
