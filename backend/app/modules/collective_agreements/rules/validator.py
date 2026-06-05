"""Validation métier post-extraction IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.modules.collective_agreements.rules.schema import CCRulesDocument, GrilleSalaires


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_cc_rules(
    doc: CCRulesDocument,
    *,
    expected_idcc: str,
) -> ValidationResult:
    """Valide le document avant écriture automatique en base."""
    errors: list[str] = []

    if not doc.idcc:
        errors.append("idcc manquant")
    elif _normalize_idcc(doc.idcc) != _normalize_idcc(expected_idcc):
        errors.append(
            f"idcc incohérent: extrait={doc.idcc}, attendu={expected_idcc}"
        )

    has_prime = bool(
        doc.prime_anciennete
        and (
            doc.prime_anciennete.bareme
            or (
                doc.prime_anciennete.taux_par_classe
                and doc.prime_anciennete.base_de_calcul
            )
        )
    )
    has_minima = bool(doc.salaires_minima) or any(
        g.minima for g in doc.grilles_salaires
    )
    if not has_prime and not has_minima:
        errors.append(
            "au moins prime_anciennete.bareme ou salaires_minima / grilles_salaires requis"
        )

    if doc.prime_anciennete:
        errors.extend(_validate_bareme(doc.prime_anciennete.bareme))

    for idx, minima in enumerate(doc.salaires_minima):
        errors.extend(_validate_minima(minima, f"salaires_minima[{idx}]"))

    for g_idx, grille in enumerate(doc.grilles_salaires):
        errors.extend(_validate_grille(grille, g_idx))

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def _normalize_idcc(idcc: str) -> str:
    stripped = idcc.strip()
    if stripped.isdigit():
        return stripped.lstrip("0") or "0"
    return stripped


def _validate_minima(minima, prefix: str) -> list[str]:
    errors: list[str] = []
    if minima.valeur <= 0:
        errors.append(f"{prefix}.valeur doit être > 0")
    if minima.coefficient <= 0:
        errors.append(f"{prefix}.coefficient doit être > 0")
    return errors


def _validate_grille(grille: GrilleSalaires, index: int) -> list[str]:
    errors: list[str] = []
    if not grille.minima:
        return errors
    for m_idx, minima in enumerate(grille.minima):
        errors.extend(
            _validate_minima(minima, f"grilles_salaires[{index}].minima[{m_idx}]")
        )
    return errors


def _validate_bareme(bareme: list) -> list[str]:
    errors: list[str] = []
    if not bareme:
        return errors

    prev_annees: Optional[float] = None
    for idx, palier in enumerate(bareme):
        if palier.taux < 0:
            errors.append(f"bareme[{idx}].taux négatif")
        if palier.taux > 1:
            errors.append(f"bareme[{idx}].taux > 1 (attendu décimal, ex. 0.03)")
        if prev_annees is not None and palier.annees_min <= prev_annees:
            errors.append(
                f"bareme[{idx}].annees_min doit être strictement croissant"
            )
        prev_annees = palier.annees_min

    return errors
