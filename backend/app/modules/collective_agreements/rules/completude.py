"""Évaluation de la complétude d'une extraction CC pour la paie."""

from __future__ import annotations

from app.modules.collective_agreements.rules.constants import (
    EXTENDED_SALARY_IDCC,
    MULTI_ZONE_IDCC,
    SMH_NATIONAL_IDCC,
)
from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    CompletudeExtraction,
    GrilleSalaires,
    SalaireMinimum,
)


def _normalize_idcc(idcc: str) -> str:
    s = idcc.strip()
    if s.isdigit():
        return s.zfill(4) if len(s) <= 4 else s
    return s


def assess_completude(doc: CCRulesDocument) -> CompletudeExtraction:
    """Calcule le niveau de complétude et les avertissements métier."""
    warnings: list[str] = []
    idcc_norm = _normalize_idcc(doc.idcc)
    multi_zone = idcc_norm in MULTI_ZONE_IDCC or idcc_norm.lstrip("0") in {
        x.lstrip("0") for x in MULTI_ZONE_IDCC
    }

    grilles = doc.grilles_salaires
    grilles_count = len(grilles)
    has_minima = bool(doc.salaires_minima) or any(g.minima for g in grilles)
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

    if multi_zone:
        if grilles_count == 0 and doc.salaires_minima:
            warnings.append(
                "Grille unique extraite alors que cette convention prévoit "
                "des minima par région ou département."
            )
        elif grilles_count == 1:
            zone = grilles[0].zone_libelle if grilles else "inconnue"
            warnings.append(
                f"Une seule zone salariale extraite ({zone}). "
                "Vérifiez les accords régionaux manquants."
            )
        elif grilles_count < 3:
            warnings.append(
                f"{grilles_count} zone(s) salariale(s) extraite(s) — "
                "couverture géographique probablement incomplète."
            )

    if not has_minima and not has_prime:
        warnings.append("Aucune règle de rémunération extraite (minima ni prime).")
    elif not has_minima and has_prime:
        warnings.append(
            "Prime d'ancienneté extraite mais aucun minimum salarial en € — "
            "grille de paie indisponible (vérifiez classification / valeur du point)."
        )

    if has_minima and not has_prime and not multi_zone:
        pass  # certaines CC n'ont pas de prime mensuelle

    if multi_zone and grilles_count >= 5:
        niveau = "complet"
    elif multi_zone and grilles_count >= 2:
        niveau = "partiel"
    elif warnings:
        niveau = "partiel"
    elif has_minima or has_prime:
        niveau = "complet"
    else:
        niveau = "inconnu"

    return CompletudeExtraction(
        niveau=niveau,  # type: ignore[arg-type]
        avertissements=warnings,
        grilles_count=grilles_count,
        idcc_multi_zones=multi_zone,
    )


def finalize_document(doc: CCRulesDocument) -> CCRulesDocument:
    """Normalise grilles / minima plats et calcule la complétude."""
    _drop_empty_grilles(doc)
    _materialize_point_value_minima(doc)
    _drop_empty_grilles(doc)

    if doc.grilles_salaires and not doc.salaires_minima:
        if len(doc.grilles_salaires) == 1:
            doc.salaires_minima = list(doc.grilles_salaires[0].minima)
    elif doc.salaires_minima and not doc.grilles_salaires:
        doc.grilles_salaires = [
            GrilleSalaires(
                zone_type="national",
                zone_libelle="National",
                minima=list(doc.salaires_minima),
            )
        ]

    doc.completude = assess_completude(doc)
    return doc


def _drop_empty_grilles(doc: CCRulesDocument) -> None:
    doc.grilles_salaires = [g for g in doc.grilles_salaires if g.minima]


def _point_value_from_doc(doc: CCRulesDocument) -> float | None:
    prime = doc.prime_anciennete
    if prime and prime.base_de_calcul:
        base = prime.base_de_calcul
        if base.methode == "valeur_du_point" and base.valeur and base.valeur > 0:
            return float(base.valeur)

    idcc_norm = _normalize_idcc(doc.idcc)
    if idcc_norm not in EXTENDED_SALARY_IDCC and idcc_norm.lstrip("0") not in {
        x.lstrip("0") for x in EXTENDED_SALARY_IDCC
    }:
        return None

    candidates: list[float] = []
    for grille in doc.grilles_salaires:
        for m in grille.minima:
            if 0 < m.valeur <= 30:
                candidates.append(float(m.valeur))
    if not candidates:
        return None
    point = max(set(candidates), key=candidates.count)
    if candidates.count(point) >= max(2, len(candidates) // 3):
        return point
    return None


def _materialize_point_value_minima(doc: CCRulesDocument) -> None:
    """
    Métallurgie legacy / grilles en points : calcule le minimum mensuel €
    (positionnement × valeur du point) si l'IA n'a rempli que le point.

    Ignoré pour les IDCC SMH national (3248) où les minima sont déjà en €.
    """
    idcc_norm = _normalize_idcc(doc.idcc)
    if idcc_norm in SMH_NATIONAL_IDCC or idcc_norm.lstrip("0") in {
        x.lstrip("0") for x in SMH_NATIONAL_IDCC
    }:
        return
    if any(
        m.valeur >= 1000
        for g in doc.grilles_salaires
        for m in g.minima
    ):
        return
    doc_point = _point_value_from_doc(doc)

    def _apply(minima: list[SalaireMinimum]) -> None:
        for m in minima:
            if m.coefficient <= 0:
                continue
            point = doc_point
            if point is None and m.valeur > 0 and m.valeur <= 30 and m.coefficient >= 50:
                point = float(m.valeur)
            if point is None:
                continue
            monthly = round(m.coefficient * point, 2)
            if m.valeur <= 0 or m.valeur <= point * 1.01 or m.valeur < monthly * 0.5:
                m.valeur = monthly

    for grille in doc.grilles_salaires:
        _apply(grille.minima)
    _apply(doc.salaires_minima)
