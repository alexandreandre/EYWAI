"""Prime d'assiduité perdue par une absence relevée au calendrier (domaine pur).

Retour d'Elsa du 17/11/2026 :
- Mont Blanc : 50 € par mois (25 € à mi-temps), perdus s'il y a une absence
  injustifiée ou un arrêt dans le mois ; CP, récupération, JTC et repos
  compensateur ne font rien perdre ;
- LEWIS : 6 € par semaine sans absence, mêmes exclusions.

Chez ces sociétés, les absences sont au calendrier (arrêts posés par « Arrêts
& IJ », journées non travaillées), pas dans les demandes d'absence : la règle
lit donc le calendrier prévu et réel de la fenêtre des variables.

Un jour fait perdre la prime quand :
- le prévu ou le réel est un arrêt (`arret…`), une absence injustifiée ou un
  jour « absent, type à donner » ;
- ou un jour « travail » prévu a un réel saisi à 0 (journée non faite, sans
  autre motif).
La liste des types peut être remplacée par la règle (`types_qui_font_perdre`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

from app.modules.payroll_variables.domain.jours_travailles import (
    TYPES_TRAVAIL,
    heures_du_jour,
)

#: Types qui font perdre la prime, en plus de tout type qui commence par
#: « arret ».
TYPES_QUI_FONT_PERDRE = frozenset({"absence_injustifiee", "absent_a_typer", "maladie"})

DUREE_LEGALE_HEBDO = 35.0


def _heures(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _type(entree: Mapping[str, Any] | None) -> str:
    return str((entree or {}).get("type") or "").strip().lower()


def motif_de_perte(
    prevu: Mapping[str, Any] | None,
    reel: Mapping[str, Any] | None,
    types: Iterable[str] | None = None,
) -> str | None:
    """Le motif qui fait perdre la prime ce jour-là, ou None."""
    choisis = {str(t).lower() for t in types} if types else None
    for entree in (reel, prevu):
        t = _type(entree)
        if not t:
            continue
        if choisis is not None:
            if t in choisis or ("arret" in choisis and t.startswith("arret")):
                return t
        elif t.startswith("arret") or t in TYPES_QUI_FONT_PERDRE:
            return t
    if (
        _type(prevu) in TYPES_TRAVAIL
        and (_heures((prevu or {}).get("heures_prevues")) or 0) > 0
        and _type(reel) in TYPES_TRAVAIL | {""}
        and _heures((reel or {}).get("heures_faites")) == 0
    ):
        return "journee_non_faite"
    return None


def jours_qui_font_perdre(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    debut: date,
    fin: date,
    types: Iterable[str] | None = None,
) -> dict[date, str]:
    out: dict[date, str] = {}
    jour = debut
    while jour <= fin:
        motif = motif_de_perte(prevu.get(jour), reel.get(jour), types)
        if motif:
            out[jour] = motif
        jour += timedelta(days=1)
    return out


def _a_travaille(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
) -> bool:
    jour = debut
    while jour <= fin:
        if heures_du_jour(prevu.get(jour), reel.get(jour), jour in jours_absence) > 0:
            return True
        jour += timedelta(days=1)
    return False


def evaluer_assiduite_du_mois(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    *,
    montant: float,
    duree_hebdomadaire: float | None = None,
    proratiser_temps_partiel: bool = True,
    types: Iterable[str] | None = None,
) -> dict[str, Any]:
    """`{amount, quantity, details}` pour la fenêtre [debut, fin].

    À temps partiel, le montant suit la durée du contrat (17,5 h → la moitié).
    Sans aucun jour travaillé dans la fenêtre, pas de prime.
    """
    perdus = jours_qui_font_perdre(prevu, reel, debut, fin, types)
    details: dict[str, Any] = {"du": debut.isoformat(), "au": fin.isoformat()}
    if perdus:
        details["perdue"] = [
            {"jour": j.isoformat(), "motif": m} for j, m in sorted(perdus.items())
        ]
        return {"amount": 0.0, "quantity": 0.0, "details": details}
    if not _a_travaille(prevu, reel, jours_absence, debut, fin):
        details["perdue"] = "aucun jour travaillé"
        return {"amount": 0.0, "quantity": 0.0, "details": details}
    facteur = 1.0
    duree = _heures(duree_hebdomadaire)
    if proratiser_temps_partiel and duree and 0 < duree < DUREE_LEGALE_HEBDO:
        facteur = duree / DUREE_LEGALE_HEBDO
        details["prorata_temps_partiel"] = round(facteur, 4)
    return {"amount": round(float(montant or 0) * facteur, 2), "quantity": 1.0, "details": details}


def lundis_de_la_fenetre(debut: date, fin: date) -> list[date]:
    """Les semaines dont le lundi tombe dans la fenêtre : chaque semaine est
    payée dans un seul mois, même à cheval sur deux."""
    lundi = debut + timedelta(days=(7 - debut.weekday()) % 7)
    out: list[date] = []
    while lundi <= fin:
        out.append(lundi)
        lundi += timedelta(days=7)
    return out


def evaluer_assiduite_des_semaines(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence_demandes: set[date],
    debut: date,
    fin: date,
    *,
    montant_par_semaine: float,
    types: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Semaines sans absence (calendrier et demandes d'absence des types choisis).

    Une semaine compte si le salarié y a travaillé au moins un jour et
    qu'aucun jour ne fait perdre la prime.
    """
    semaines: list[dict[str, Any]] = []
    eligibles = 0
    for lundi in lundis_de_la_fenetre(debut, fin):
        dimanche = lundi + timedelta(days=6)
        perdus = jours_qui_font_perdre(prevu, reel, lundi, dimanche, types)
        demandes = sorted(d for d in jours_absence_demandes if lundi <= d <= dimanche)
        if perdus or demandes:
            semaines.append(
                {
                    "monday": lundi.isoformat(),
                    "eligible": False,
                    "reason": "absence",
                    "jours": [d.isoformat() for d in sorted(perdus)] + [d.isoformat() for d in demandes],
                }
            )
            continue
        if not _a_travaille(prevu, reel, set(), lundi, dimanche):
            semaines.append({"monday": lundi.isoformat(), "eligible": False, "reason": "no_work"})
            continue
        eligibles += 1
        semaines.append({"monday": lundi.isoformat(), "eligible": True})
    return {
        "quantity": float(eligibles),
        "amount": round(float(montant_par_semaine or 0) * eligibles, 2),
        "details": {"weeks": semaines},
    }
