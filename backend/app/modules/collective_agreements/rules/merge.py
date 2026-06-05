"""Fusion de résultats d'extraction multi-chunks."""

from __future__ import annotations

from typing import Any

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    GrilleSalaires,
    PalierAnciennete,
    PrimeAnciennete,
    SalaireMinimum,
    parse_base_calcul_safe,
    parse_extraction_result,
)


def merge_extraction_results(
    results: list[dict[str, Any]],
    *,
    idcc: str,
) -> CCRulesDocument:
    """Fusionne plusieurs extractions partielles en un document unique."""
    if not results:
        return CCRulesDocument(idcc=idcc)

    if len(results) == 1:
        doc = parse_extraction_result(results[0])
        doc.idcc = idcc
        _dedupe_flat_minima(doc)
        _dedupe_grilles(doc)
        return doc

    all_baremes: list[PalierAnciennete] = []
    best_base: dict[str, Any] | None = None
    minima_by_coeff: dict[float, SalaireMinimum] = {}
    grilles_by_key: dict[str, GrilleSalaires] = {}
    all_citations: list[dict[str, str]] = []
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    best_confidence = "low"

    for raw in results:
        doc = parse_extraction_result(raw)
        if doc.prime_anciennete:
            all_baremes.extend(doc.prime_anciennete.bareme)
            if doc.prime_anciennete.base_de_calcul and not best_base:
                best_base = doc.prime_anciennete.base_de_calcul.model_dump()
        for m in doc.salaires_minima:
            minima_by_coeff[m.coefficient] = m
        for grille in doc.grilles_salaires:
            key = _grille_key(grille)
            existing = grilles_by_key.get(key)
            if existing:
                by_coeff = {m.coefficient: m for m in existing.minima}
                for m in grille.minima:
                    by_coeff[m.coefficient] = m
                existing.minima = list(by_coeff.values())
            else:
                grilles_by_key[key] = grille
        if doc.meta:
            all_citations.extend([c.model_dump() for c in doc.meta.citations])
            conf = doc.meta.confidence
            if confidence_rank.get(conf, 0) > confidence_rank.get(best_confidence, 0):
                best_confidence = conf

    merged_bareme = _dedupe_bareme(all_baremes)
    prime = None
    if merged_bareme or best_base:
        base_obj = parse_base_calcul_safe(best_base) if best_base else None
        prime = PrimeAnciennete(bareme=merged_bareme, base_de_calcul=base_obj)

    grilles = list(grilles_by_key.values())
    flat_minima = list(minima_by_coeff.values())
    if grilles and not flat_minima and len(grilles) == 1:
        flat_minima = list(grilles[0].minima)

    merged = parse_extraction_result(
        {
            "idcc": idcc,
            "prime_anciennete": (
                {
                    "bareme": [
                        {"annees_min": p.annees_min, "taux": p.taux}
                        for p in merged_bareme
                    ],
                    "base_de_calcul": best_base,
                }
                if prime
                else None
            ),
            "salaires_minima": [
                {
                    "coefficient": m.coefficient,
                    "valeur": m.valeur,
                    "libelle": m.libelle,
                }
                for m in flat_minima
            ],
            "grilles_salaires": [
                {
                    "zone_type": g.zone_type,
                    "zone_libelle": g.zone_libelle,
                    "departements": g.departements,
                    "regions": g.regions,
                    "date_effet": g.date_effet,
                    "source_titre": g.source_titre,
                    "minima": [
                        {
                            "coefficient": m.coefficient,
                            "valeur": m.valeur,
                            "libelle": m.libelle,
                        }
                        for m in g.minima
                    ],
                }
                for g in grilles
            ],
            "confidence": best_confidence,
            "citations": all_citations,
        }
    )
    merged.idcc = idcc
    return merged


def _grille_key(grille: GrilleSalaires) -> str:
    deps = ",".join(sorted(grille.departements))
    regs = ",".join(sorted(grille.regions))
    return f"{grille.zone_type}|{grille.zone_libelle.lower()}|{deps}|{regs}"


def _dedupe_flat_minima(doc: CCRulesDocument) -> None:
    if doc.salaires_minima:
        by_coeff: dict[float, SalaireMinimum] = {}
        for m in doc.salaires_minima:
            by_coeff[m.coefficient] = m
        doc.salaires_minima = list(by_coeff.values())


def _dedupe_grilles(doc: CCRulesDocument) -> None:
    if not doc.grilles_salaires:
        return
    by_key: dict[str, GrilleSalaires] = {}
    for grille in doc.grilles_salaires:
        key = _grille_key(grille)
        by_key[key] = grille
    doc.grilles_salaires = list(by_key.values())


def _dedupe_bareme(baremes: list[PalierAnciennete]) -> list[PalierAnciennete]:
    by_year: dict[float, PalierAnciennete] = {}
    for p in baremes:
        existing = by_year.get(p.annees_min)
        if existing is None or p.taux > existing.taux:
            by_year[p.annees_min] = p
    return sorted(by_year.values(), key=lambda x: x.annees_min)
