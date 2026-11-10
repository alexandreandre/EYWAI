"""Filtre « pas trop sensible », tenu par le serveur et non par le modèle.

L'IA dit « à regarder », la ligne et la raison. Elle ne crée aucun chiffre : tout
nombre qu'elle cite doit déjà être dans la fiche, sinon le signalement est écarté.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Iterable

GRAVITES = ("important", "a_verifier")
_RANG_GRAVITE = {g: i for i, g in enumerate(GRAVITES)}

_PART_DES_BULLETINS = 0.10
_PLAFOND_MINIMUM = 3
_LONGUEUR_LIGNE = 200
_LONGUEUR_RAISON = 1000

_RE_NOMBRE = re.compile(r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
_CENTIME = Decimal("0.01")


def _vers_decimal(texte: str) -> Decimal | None:
    propre = re.sub(r"[   ]", "", texte).replace(",", ".")
    try:
        return abs(Decimal(propre))
    except InvalidOperation:
        return None


def _nombres_du_texte(texte: str) -> list[Decimal]:
    trouves = (_vers_decimal(m.group(0)) for m in _RE_NOMBRE.finditer(texte))
    return [n for n in trouves if n is not None]


def nombres_de_la_fiche(valeur: Any) -> set[Decimal]:
    """Tous les nombres de la fiche, valeurs exactes et arrondies au centime."""
    nombres: set[Decimal] = set()

    def ajouter(nombre: Decimal) -> None:
        nombres.add(nombre.normalize())
        nombres.add(nombre.quantize(_CENTIME, rounding=ROUND_HALF_UP).normalize())

    def parcourir(element: Any) -> None:
        if isinstance(element, dict):
            for contenu in element.values():
                parcourir(contenu)
        elif isinstance(element, (list, tuple)):
            for contenu in element:
                parcourir(contenu)
        elif isinstance(element, bool):
            return
        elif isinstance(element, (int, float)):
            if math.isfinite(element):
                ajouter(abs(Decimal(str(element))))
        elif isinstance(element, str):
            for nombre in _nombres_du_texte(element):
                ajouter(nombre)

    parcourir(valeur)
    return nombres


def normaliser_ligne(ligne: str) -> str:
    """Clé d'une ligne de bulletin, stable d'un mois à l'autre."""
    decompose = unicodedata.normalize("NFD", str(ligne or ""))
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", sans_accents.lower()).split())


def _chiffres_du_signalement(signalement: dict[str, Any]) -> list[Decimal]:
    chiffres: list[Decimal] = []
    for cite in signalement.get("chiffres_cites") or []:
        chiffres.extend(_nombres_du_texte(str(cite)))
    chiffres.extend(_nombres_du_texte(str(signalement.get("raison") or "")))
    chiffres.extend(_nombres_du_texte(str(signalement.get("ligne") or "")))
    return chiffres


@dataclass
class ResultatGarde:
    retenus: list[dict[str, Any]] = field(default_factory=list)
    ecartes: dict[str, int] = field(default_factory=dict)

    def compter(self, motif: str) -> None:
        self.ecartes[motif] = self.ecartes.get(motif, 0) + 1


def garder_signalements(
    signalements: Iterable[dict[str, Any]],
    fiche: dict[str, Any],
    *,
    code: str,
    vus: set[str] | frozenset[str] = frozenset(),
) -> ResultatGarde:
    """Écarte ce que le serveur ne peut pas confirmer. Le reste, nettoyé."""
    resultat = ResultatGarde()
    connus = nombres_de_la_fiche(fiche)
    par_ligne: dict[str, dict[str, Any]] = {}

    for brut in signalements:
        gravite = brut.get("gravite")
        ligne = str(brut.get("ligne") or "").strip()
        raison = str(brut.get("raison") or "").strip()
        if gravite not in _RANG_GRAVITE or not ligne or not raison:
            resultat.compter("incomplet")
            continue
        if not brut.get("chiffres_cites"):
            resultat.compter("sans_chiffre")
            continue
        if any(n.normalize() not in connus for n in _chiffres_du_signalement(brut)):
            resultat.compter("chiffre_absent_de_la_fiche")
            continue
        cle = normaliser_ligne(ligne)
        if cle in vus:
            resultat.compter("deja_vu")
            continue
        retenu = {
            "gravite": gravite,
            "ligne": ligne[:_LONGUEUR_LIGNE],
            "raison": raison.replace(code, "ce salarié")[:_LONGUEUR_RAISON],
            "chiffres_cites": [str(c) for c in brut["chiffres_cites"]],
        }
        deja = par_ligne.get(cle)
        if deja is None:
            par_ligne[cle] = retenu
            continue
        resultat.compter("doublon")
        if _RANG_GRAVITE[gravite] < _RANG_GRAVITE[deja["gravite"]]:
            par_ligne[cle] = retenu

    resultat.retenus = list(par_ligne.values())
    return resultat


def plafond_pour(nombre_de_bulletins: int) -> int:
    """10 % des bulletins de la société, arrondi au-dessus, au moins 3."""
    return max(_PLAFOND_MINIMUM, math.ceil(nombre_de_bulletins * _PART_DES_BULLETINS - 1e-9))


def appliquer_plafond(
    points: list[dict[str, Any]], nombre_de_bulletins: int
) -> tuple[list[dict[str, Any]], int]:
    """Les plus graves d'abord, jusqu'au plafond. Rend aussi le nombre de points laissés."""
    classes = sorted(points, key=lambda p: _RANG_GRAVITE.get(p.get("gravite"), len(GRAVITES)))
    plafond = plafond_pour(nombre_de_bulletins)
    return classes[:plafond], max(0, len(classes) - plafond)
