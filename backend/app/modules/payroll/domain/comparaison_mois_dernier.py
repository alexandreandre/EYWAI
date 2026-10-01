"""Ce qui a changé par rapport au bulletin du même salarié le mois précédent.

Compare uniquement des montants déjà calculés (brut, net, heures sup, absences).
S'il n'y a pas de bulletin le mois dernier, aucun chiffre n'est inventé.
"""

from __future__ import annotations

from typing import Any, Mapping

TEXTE_ABSENT = "Pas de bulletin le mois dernier"

_MOT_HS = "Heures suppl."
_MOT_MAJOR = "major"


def mois_precedent_civil(annee: int, mois: int) -> tuple[int, int]:
    if mois == 1:
        return annee - 1, 12
    return annee, mois - 1


def comparer_au_mois_dernier(
    actuel: Mapping[str, Any] | None,
    precedent: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(precedent, Mapping):
        return {"present": False, "texte": TEXTE_ABSENT}
    actuel = actuel if isinstance(actuel, Mapping) else {}

    brut = _paire(_nombre(precedent.get("salaire_brut")), _nombre(actuel.get("salaire_brut")))
    net = _paire(_nombre(precedent.get("net_a_payer")), _nombre(actuel.get("net_a_payer")))
    heures_sup = _paire(_heures_sup(precedent), _heures_sup(actuel))
    absences = _paire(_heures_absences(precedent), _heures_absences(actuel))

    morceaux: list[str] = []
    if brut:
        morceaux.append(f"Brut : {_euro(brut['avant'])} → {_euro(brut['apres'])}")
    if net:
        morceaux.append(f"Net : {_euro(net['avant'])} → {_euro(net['apres'])}")
    if heures_sup:
        morceaux.append(
            f"Heures sup : {_heures_fr(heures_sup['avant'])} h → {_heures_fr(heures_sup['apres'])} h"
        )
    if absences:
        morceaux.append(
            f"Absences : {_heures_fr(absences['avant'])} h → {_heures_fr(absences['apres'])} h"
        )

    resultat: dict[str, Any] = {"present": True, "texte": " · ".join(morceaux)}
    if brut:
        resultat["brut"] = brut
    if net:
        resultat["net"] = net
    if heures_sup:
        resultat["heures_sup"] = heures_sup
    if absences:
        resultat["absences"] = absences
    return resultat


def _paire(avant: float | None, apres: float | None) -> dict[str, float] | None:
    if avant is None or apres is None:
        return None
    return {"avant": avant, "apres": apres}


def _heures_sup(data: Mapping[str, Any]) -> float:
    total = 0.0
    vu = False
    for ligne in data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "")
        if _MOT_HS not in libelle or _MOT_MAJOR not in libelle.lower():
            continue
        quantite = _nombre(ligne.get("quantite"))
        if quantite is None:
            continue
        total += quantite
        vu = True
    return round(total, 2) if vu else 0.0


def _heures_absences(data: Mapping[str, Any]) -> float:
    total = 0.0
    for section in ("details_absences", "details_conges"):
        for ligne in data.get(section) or []:
            if not isinstance(ligne, dict):
                continue
            quantite = _nombre(ligne.get("quantite"))
            if quantite is None:
                continue
            total += quantite
    return round(total, 2)


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _euro(valeur: float) -> str:
    texte = f"{valeur:.2f}"
    signe = ""
    if texte.startswith("-"):
        signe = "−"
        texte = texte[1:]
    entier, frac = texte.split(".")
    groupes: list[str] = []
    while entier:
        groupes.append(entier[-3:])
        entier = entier[:-3]
    return f"{signe}{' '.join(reversed(groupes))},{frac} €"


def _heures_fr(valeur: float) -> str:
    texte = f"{round(float(valeur), 2):.2f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")
