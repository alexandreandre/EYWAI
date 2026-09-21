"""Indemnité compensatrice de congés payés de fin de contrat : la règle légale.

À la fin d'un CDD ou d'une mission d'intérim, les congés acquis et non pris
sont payés. Pour chaque période de référence, l'indemnité vaut le plus
favorable du dixième (10 % de la rémunération brute de la période, précarité
comprise, ramené aux jours restants) et du maintien (les jours restants × la
valeur d'un jour). Les jours déjà pris ont été payés à leur date : seuls les
jours restants comptent.

Recette : Aurélien Demory, juillet 2026 — période 2025-2026 : 10 % de 4 171,35
× 2,78/3,78 = 306,78 (maintien 273,77) ; période 2026-2027 : 10 % de 4 596,09
= 459,61 (maintien 409,68) ; total 766,39. Spec
2026-09-21-indemnite-cp-fin-de-contrat-legale-design.md. Module pur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from . import legal_constants as lc
from .iccp_arbitrage import calculer_maintien_horaire


def valeur_jour_maintien(
    taux_horaire_base: float, duree_hebdo: float, majoration_hs25: float
) -> float:
    """Ce que vaut un jour de congé au maintien : la règle de `calcul_conges`
    (à 39 h : 7 h de base + 0,8 h structurelle majorée)."""
    heures_normales = min(duree_hebdo, lc.DUREE_LEGALE_HEBDO) / 5
    heures_structurelles = max(0.0, (duree_hebdo - lc.DUREE_LEGALE_HEBDO) / 5)
    return calculer_maintien_horaire(
        1.0,
        taux_horaire_base,
        heures_normales_par_jour=heures_normales,
        heures_supp_par_jour=heures_structurelles,
        majoration_hs=majoration_hs25,
    ).total


@dataclass(frozen=True)
class PeriodeConges:
    """Une période de référence : sa rémunération brute (None si inconnue),
    les droits de la période (jours pris + restants) et les jours restants."""

    libelle: str
    brut: float | None
    droits: float
    restants: float


@dataclass(frozen=True)
class DetailPeriode:
    periode: PeriodeConges
    dixieme: float | None
    maintien: float
    retenu: float
    methode: str  # dixieme | maintien | maintien_seul | rien

    def resume(self) -> dict[str, Any]:
        return {
            "libelle": self.periode.libelle,
            "brut": None if self.periode.brut is None else round(self.periode.brut, 2),
            "droits": round(self.periode.droits, 2),
            "restants": round(self.periode.restants, 2),
            "dixieme": self.dixieme,
            "maintien": self.maintien,
            "retenu": self.retenu,
            "methode": self.methode,
        }


def indemnite_par_periode(
    periode: PeriodeConges, *, taux: float, valeur_jour: float
) -> DetailPeriode:
    restants = max(float(periode.restants or 0.0), 0.0)
    if restants <= 0:
        return DetailPeriode(periode, None, 0.0, 0.0, "rien")
    maintien = round(restants * float(valeur_jour), 2)
    droits = float(periode.droits or 0.0)
    if periode.brut is None or droits <= 0:
        return DetailPeriode(periode, None, maintien, maintien, "maintien_seul")
    dixieme = round(float(periode.brut) * float(taux) * restants / droits, 2)
    if dixieme >= maintien:
        return DetailPeriode(periode, dixieme, maintien, dixieme, "dixieme")
    return DetailPeriode(periode, dixieme, maintien, maintien, "maintien")


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")


def _nombre(valeur: float) -> str:
    return f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",") or "0"


@dataclass(frozen=True)
class IndemniteFinDeContrat:
    periodes: tuple[DetailPeriode, ...]
    taux: float
    valeur_jour: float

    @property
    def total(self) -> float:
        return round(sum(p.retenu for p in self.periodes), 2)

    @property
    def mention(self) -> str:
        pour_cent = f"{self.taux * 100:g} %"
        morceaux = []
        for d in self.periodes:
            p = d.periode
            tete = (
                f"période {p.libelle}, {_nombre(p.restants)} j restants sur "
                f"{_nombre(p.droits)} : "
            )
            maintien = f"maintien {_euros(d.maintien)} ({_nombre(p.restants)} j × {_euros(self.valeur_jour)})"
            if d.dixieme is None:
                corps = f"rémunération de la période inconnue, maintien seul {_euros(d.maintien)} ({_nombre(p.restants)} j × {_euros(self.valeur_jour)})"
            else:
                corps = (
                    f"dixième {_euros(d.dixieme)} ({pour_cent} de {_euros(p.brut or 0.0)} × "
                    f"{_nombre(p.restants)}/{_nombre(p.droits)}) ou {maintien}"
                )
            morceaux.append(f"{tete}{corps} → {_euros(d.retenu)}")
        return (
            "Indemnité de congés payés de fin de contrat : "
            + " ; ".join(morceaux)
            + f". Total {_euros(self.total)}."
        )

    def resume(self) -> dict[str, Any]:
        return {
            "methode": "par_periode",
            "taux": self.taux,
            "valeur_jour": round(self.valeur_jour, 2),
            "periodes": [d.resume() for d in self.periodes],
            "total": self.total,
            "mention": self.mention,
        }


def indemnite_fin_de_contrat(
    periodes: Iterable[PeriodeConges], *, taux: float, valeur_jour: float
) -> IndemniteFinDeContrat:
    """Les périodes sans jour restant n'apparaissent pas."""
    details = tuple(
        d
        for d in (indemnite_par_periode(p, taux=taux, valeur_jour=valeur_jour) for p in periodes)
        if d.methode != "rien"
    )
    return IndemniteFinDeContrat(details, float(taux), float(valeur_jour))


__all__ = [
    "DetailPeriode",
    "IndemniteFinDeContrat",
    "PeriodeConges",
    "indemnite_fin_de_contrat",
    "indemnite_par_periode",
    "valeur_jour_maintien",
]
