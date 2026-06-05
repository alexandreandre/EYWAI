"""Résolution des grilles salariales CC selon la localisation de l'établissement."""

from __future__ import annotations

from typing import Any, Optional


def departement_from_code_postal(code_postal: str | None) -> Optional[str]:
    """Déduit le code département depuis un code postal français."""
    cp = (code_postal or "").strip()
    if len(cp) < 2:
        return None
    if cp.startswith(("97", "98")):
        return cp[:3]
    if cp.startswith("20"):
        return "2A"
    dept = cp[:2]
    return dept.lstrip("0") or dept


def _normalize_dept(value: str) -> str:
    return value.strip().upper().lstrip("0") or "0"


def _dept_matches(departements: list[str], dept: str) -> bool:
    target = _normalize_dept(dept)
    for raw in departements:
        if _normalize_dept(str(raw)) == target:
            return True
        if str(raw).strip().upper() == dept.strip().upper():
            return True
    return False


def resolve_salaires_minima(
    rules: dict[str, Any],
    *,
    code_postal: str | None = None,
    departement: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retourne la grille de minima applicable (liste coefficient → €).

    Priorité : département explicite → département depuis CP → grille nationale
    → grille unique → liste plate legacy `salaires_minima`.
    """
    grilles = rules.get("grilles_salaires") or []
    if not grilles:
        legacy = rules.get("salaires_minima") or []
        return list(legacy) if isinstance(legacy, list) else []

    dept = departement or departement_from_code_postal(code_postal)
    if dept:
        for grille in grilles:
            if not isinstance(grille, dict):
                continue
            deps = grille.get("departements") or []
            if deps and _dept_matches(deps, dept):
                minima = grille.get("minima") or []
                return list(minima) if isinstance(minima, list) else []

        dept_norm = _normalize_dept(dept)
        for grille in grilles:
            if not isinstance(grille, dict):
                continue
            libelle = str(grille.get("zone_libelle") or "").lower()
            if dept_norm in libelle or dept in libelle:
                minima = grille.get("minima") or []
                if minima:
                    return list(minima)

    for grille in grilles:
        if isinstance(grille, dict) and grille.get("zone_type") == "national":
            minima = grille.get("minima") or []
            return list(minima) if isinstance(minima, list) else []

    if len(grilles) == 1 and isinstance(grilles[0], dict):
        minima = grilles[0].get("minima") or []
        return list(minima) if isinstance(minima, list) else []

    legacy = rules.get("salaires_minima") or []
    return list(legacy) if isinstance(legacy, list) else []


def code_postal_from_entreprise(entreprise: dict[str, Any]) -> Optional[str]:
    """Lit le code postal établissement depuis le dict entreprise paie."""
    for key in ("adresse_code_postal", "code_postal"):
        val = entreprise.get(key)
        if val:
            return str(val).strip()
    adresse = entreprise.get("adresse")
    if isinstance(adresse, dict):
        cp = adresse.get("code_postal")
        if cp:
            return str(cp).strip()
    return None
