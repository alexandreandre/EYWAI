"""
Résolution temporelle des salaires (salary_history → paie).

Méthode de prorata : 30èmes, date d'effet inclusive (jour J au nouveau taux).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, TypedDict

JOURS_BASE_PRORATA = 30


class ProrataSalaireMois(TypedDict):
    ancien: float
    nouveau: float
    jours_ancien: int
    jours_nouveau: int
    montant_mois: float


class RappelSalaire(TypedDict):
    montant: float
    periode_debut: str | None
    periode_fin: str | None


class EvolutionSalaireMois(TypedDict):
    salaire_debut_mois: float
    salaire_fin_mois: float
    prorata: ProrataSalaireMois | None
    rappel: RappelSalaire


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _extract_valeur(salaire: Any) -> float:
    if salaire is None:
        return 0.0
    if isinstance(salaire, dict):
        try:
            return float(salaire.get("valeur") or 0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(salaire)
    except (TypeError, ValueError):
        return 0.0


def _tri_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        timeline,
        key=lambda e: (_parse_date(e.get("effective_date")) or date.min, str(e.get("id", ""))),
    )


def salaire_actif_a_date(
    timeline: list[dict[str, Any]],
    as_of: date,
    salaire_initial: float | None = None,
) -> float:
    """Dernier nouveau_salaire dont effective_date <= as_of."""
    applicable = [
        e
        for e in _tri_timeline(timeline)
        if (d := _parse_date(e.get("effective_date"))) is not None and d <= as_of
    ]
    if not applicable:
        futures = [
            e
            for e in _tri_timeline(timeline)
            if (d := _parse_date(e.get("effective_date"))) is not None and d > as_of
        ]
        if futures:
            ancien = _extract_valeur(futures[0].get("ancien_salaire"))
            if ancien > 0:
                return ancien
        return float(salaire_initial or 0.0)
    last = applicable[-1]
    return _extract_valeur(last.get("nouveau_salaire"))


def changements_dans_mois(
    timeline: list[dict[str, Any]],
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Entrées dont la date d'effet tombe dans le mois (tri chronologique)."""
    debut = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    fin = date(year, month, last_day)
    out: list[dict[str, Any]] = []
    for entry in _tri_timeline(timeline):
        eff = _parse_date(entry.get("effective_date"))
        if eff is not None and debut <= eff <= fin:
            out.append(entry)
    return out


def calculer_salaire_mois_prorata(
    ancien: float,
    nouveau: float,
    effective_date: date,
    year: int,
    month: int,
) -> float:
    """Prorata 30èmes pour un changement en cours de mois (date inclusive)."""
    debut_mois = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    fin_mois = date(year, month, last_day)

    if effective_date < debut_mois or effective_date > fin_mois:
        return round(ancien, 2)
    if effective_date == debut_mois:
        return round(nouveau, 2)

    jours_ancien = effective_date.day - 1
    jours_nouveau = JOURS_BASE_PRORATA - jours_ancien
    return round(
        (ancien * jours_ancien / JOURS_BASE_PRORATA)
        + (nouveau * jours_nouveau / JOURS_BASE_PRORATA),
        2,
    )


def _avancer_mois(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def calculer_rappel_mois_anterieurs(
    timeline: list[dict[str, Any]],
    year: int,
    month: int,
) -> RappelSalaire:
    """
    Différentiel dû pour les mois strictement antérieurs au bulletin (year, month).
    Versé en une ligne sur le bulletin courant.
    """
    debut_bulletin = date(year, month, 1)
    entries = [
        e
        for e in _tri_timeline(timeline)
        if (eff := _parse_date(e.get("effective_date"))) is not None and eff < debut_bulletin
        and not bool(
            (e.get("nouveau_salaire") or {}).get("rappel_deja_verse")
            if isinstance(e.get("nouveau_salaire"), dict)
            else False
        )
    ]
    if not entries:
        return RappelSalaire(montant=0.0, periode_debut=None, periode_fin=None)

    total = 0.0
    periode_debut: date | None = None
    periode_fin = debut_bulletin - timedelta(days=1)

    for entry in entries:
        eff = _parse_date(entry.get("effective_date"))
        if eff is None:
            continue
        ancien = _extract_valeur(entry.get("ancien_salaire"))
        nouveau = _extract_valeur(entry.get("nouveau_salaire"))
        if ancien <= 0 < nouveau:
            # Première rémunération contractuelle : ce n'est ni une hausse,
            # ni un rappel dû avant l'embauche.
            continue
        diff = nouveau - ancien
        if diff <= 0:
            continue

        if periode_debut is None or eff < periode_debut:
            periode_debut = eff

        cursor = date(eff.year, eff.month, 1)
        while cursor < debut_bulletin:
            if cursor.year == eff.year and cursor.month == eff.month:
                jours_nouveau = JOURS_BASE_PRORATA - (eff.day - 1)
                total += diff * jours_nouveau / JOURS_BASE_PRORATA
            else:
                total += diff
            cursor = _avancer_mois(cursor)

    return RappelSalaire(
        montant=round(total, 2),
        periode_debut=periode_debut.isoformat() if periode_debut else None,
        periode_fin=periode_fin.isoformat() if total > 0 else None,
    )


def construire_evolution_salaire_mois(
    timeline: list[dict[str, Any]],
    year: int,
    month: int,
    salaire_initial: float | None = None,
) -> EvolutionSalaireMois:
    """Bloc remuneration.evolution_salaire_mois pour le moteur paie."""
    debut_mois = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    fin_mois = date(year, month, last_day)
    veille = debut_mois - timedelta(days=1)

    salaire_debut = salaire_actif_a_date(timeline, veille, salaire_initial)
    changes = changements_dans_mois(timeline, year, month)

    prorata: ProrataSalaireMois | None = None
    if changes:
        last_change = changes[-1]
        eff = _parse_date(last_change.get("effective_date"))
        if eff is not None:
            ancien = _extract_valeur(last_change.get("ancien_salaire"))
            nouveau = _extract_valeur(last_change.get("nouveau_salaire"))
            if ancien <= 0 < nouveau:
                return EvolutionSalaireMois(
                    salaire_debut_mois=nouveau,
                    salaire_fin_mois=nouveau,
                    prorata=None,
                    rappel=calculer_rappel_mois_anterieurs(timeline, year, month),
                )
            if eff == debut_mois:
                salaire_fin = nouveau
            else:
                jours_ancien = eff.day - 1
                jours_nouveau = JOURS_BASE_PRORATA - jours_ancien
                montant = calculer_salaire_mois_prorata(ancien, nouveau, eff, year, month)
                prorata = ProrataSalaireMois(
                    ancien=ancien,
                    nouveau=nouveau,
                    jours_ancien=jours_ancien,
                    jours_nouveau=jours_nouveau,
                    montant_mois=montant,
                )
                salaire_fin = nouveau
            return EvolutionSalaireMois(
                salaire_debut_mois=salaire_debut,
                salaire_fin_mois=salaire_fin,
                prorata=prorata,
                rappel=calculer_rappel_mois_anterieurs(timeline, year, month),
            )

    salaire_fin = salaire_actif_a_date(timeline, fin_mois, salaire_initial)
    return EvolutionSalaireMois(
        salaire_debut_mois=salaire_debut,
        salaire_fin_mois=salaire_fin,
        prorata=None,
        rappel=calculer_rappel_mois_anterieurs(timeline, year, month),
    )


def est_augmentation_planifiee(effective_date: date, as_of: date | None = None) -> bool:
    """True si la date d'effet est strictement postérieure à as_of (défaut : aujourd'hui)."""
    ref = as_of or date.today()
    return effective_date > ref


__all__ = [
    "JOURS_BASE_PRORATA",
    "ProrataSalaireMois",
    "RappelSalaire",
    "EvolutionSalaireMois",
    "salaire_actif_a_date",
    "changements_dans_mois",
    "calculer_salaire_mois_prorata",
    "calculer_rappel_mois_anterieurs",
    "construire_evolution_salaire_mois",
    "est_augmentation_planifiee",
]
