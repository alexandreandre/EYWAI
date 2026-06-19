"""Calcul du temps retenu mensuel pour prorata de rémunération (prime d'ancienneté, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Optional, Set

from app.modules.payroll.planning_repli import mois_sans_pointage

ProrataMode = Literal["heures_contrat", "jours_forfait", "none"]


@dataclass(frozen=True)
class TempsRetenuResult:
    temps_retenu: float
    reference: float
    ratio: float
    mode: str
    detail: dict[str, Any]


def _parse_day(ev: dict[str, Any]) -> int | None:
    jour = ev.get("jour")
    if jour is not None:
        try:
            return int(jour)
        except (TypeError, ValueError):
            pass
    dc = ev.get("date_complete")
    if dc:
        try:
            return date.fromisoformat(str(dc)[:10]).day
        except (TypeError, ValueError):
            return None
    return None


def _events_in_period(
    calendrier: list[dict[str, Any]],
    date_debut: date,
    date_fin: date,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in calendrier:
        dc = ev.get("date_complete")
        if dc:
            try:
                d = date.fromisoformat(str(dc)[:10])
            except (TypeError, ValueError):
                continue
            if date_debut <= d <= date_fin:
                out.append(ev)
        else:
            jour = ev.get("jour")
            if jour is not None:
                try:
                    d = date(date_debut.year, date_debut.month, int(jour))
                    if date_debut <= d <= date_fin:
                        out.append(ev)
                except (TypeError, ValueError):
                    continue
    return out


def _heures_dues_hors_conges(
    calendrier_periode: list[dict[str, Any]],
    duree_hebdo: float,
) -> float:
    jours_ouvrables = sum(
        1
        for j in calendrier_periode
        if j.get("type") not in ("weekend", "ferie")
    )
    jours_conges = sum(
        1 for j in calendrier_periode if j.get("type") == "conges_payes"
    )
    heures_theoriques = jours_ouvrables * (duree_hebdo / 5)
    return heures_theoriques - (jours_conges * (duree_hebdo / 5))


def compute_temps_retenu_mois(
    *,
    mode: ProrataMode,
    calendrier_saisie: list[dict[str, Any]],
    duree_hebdo: float,
    date_debut: date,
    date_fin: date,
    jours_maintien: Optional[Set[int]] = None,
    inclure_heures_sup: bool = True,
    maladie_si_maintien: bool = True,
    sans_pointage_policy: str = "plein_mois",
    ratio_plafond: float | None = None,
    actual_hours_raw: list[dict[str, Any]] | None = None,
) -> TempsRetenuResult:
    """
    Calcule le ratio temps retenu / référence pour prorata mensuel.

    mode heures_contrat : heures travaillées (+ HS si inclure_heures_sup)
    + heures journalières pour jours d'arrêt avec maintien.
    """
    if mode == "none":
        return TempsRetenuResult(
            temps_retenu=1.0,
            reference=1.0,
            ratio=1.0,
            mode=mode,
            detail={"reason": "prorata_disabled"},
        )

    calendrier_periode = _events_in_period(calendrier_saisie, date_debut, date_fin)
    jours_maintien = jours_maintien or set()
    heures_jour = duree_hebdo / 5 if duree_hebdo > 0 else 7.0

    if mode == "jours_forfait":
        jours_ouvrables = sum(
            1
            for j in calendrier_periode
            if j.get("type") not in ("weekend", "ferie")
        )
        reference = float(jours_ouvrables) if jours_ouvrables > 0 else 22.0
        jours_travail = sum(
            1 for j in calendrier_periode if j.get("type") == "travail"
        )
        jours_maintien_comptes = 0
        if maladie_si_maintien:
            for ev in calendrier_periode:
                if ev.get("type") not in ("arret_maladie", "arret_travail"):
                    continue
                jour = _parse_day(ev)
                if jour is not None and jour in jours_maintien:
                    jours_maintien_comptes += 1
        temps_retenu = float(jours_travail + jours_maintien_comptes)
        ratio = temps_retenu / reference if reference > 0 else 0.0
        if ratio_plafond is not None:
            ratio = min(ratio, ratio_plafond)
        return TempsRetenuResult(
            temps_retenu=round(temps_retenu, 2),
            reference=round(reference, 2),
            ratio=round(ratio, 6),
            mode=mode,
            detail={
                "jours_travail": jours_travail,
                "jours_maintien": jours_maintien_comptes,
            },
        )

    # heures_contrat
    reference = round((duree_hebdo * 52) / 12, 2) if duree_hebdo > 0 else 151.67

    sans_pointage = False
    if actual_hours_raw is not None:
        sans_pointage = mois_sans_pointage(
            actual_hours_raw, annee=date_debut.year, mois=date_debut.month
        )

    heures_travaillees = sum(
        float(j.get("heures") or 0)
        for j in calendrier_periode
        if j.get("type") == "travail"
    )

    if sans_pointage and heures_travaillees <= 0:
        if sans_pointage_policy == "plein_mois":
            return TempsRetenuResult(
                temps_retenu=reference,
                reference=reference,
                ratio=1.0,
                mode=mode,
                detail={"sans_pointage": True, "policy": sans_pointage_policy},
            )
        return TempsRetenuResult(
            temps_retenu=0.0,
            reference=reference,
            ratio=0.0,
            mode=mode,
            detail={"sans_pointage": True, "policy": sans_pointage_policy},
        )

    heures_maintien = 0.0
    if maladie_si_maintien:
        for ev in calendrier_periode:
            if ev.get("type") not in ("arret_maladie", "arret_travail"):
                continue
            jour = _parse_day(ev)
            if jour is not None and jour in jours_maintien:
                heures_maintien += heures_jour

    heures_dues = _heures_dues_hors_conges(calendrier_periode, duree_hebdo)
    temps_retenu = heures_travaillees + heures_maintien

    ratio = temps_retenu / reference if reference > 0 else 0.0
    if ratio_plafond is not None:
        ratio = min(ratio, ratio_plafond)

    return TempsRetenuResult(
        temps_retenu=round(temps_retenu, 2),
        reference=reference,
        ratio=round(ratio, 6),
        mode=mode,
        detail={
            "heures_travaillees": round(heures_travaillees, 2),
            "heures_maintien": round(heures_maintien, 2),
            "heures_dues_hors_conges": round(heures_dues, 2),
        },
    )
