"""Diff structurel entre deux fichiers DSN plats.

Sert à mesurer l'écart entre la DSN produite par EYWAI et une DSN de référence
déjà acceptée par net-entreprises (celle du cabinet). Le comparateur de
``dsn_compare`` travaille au niveau métier (montants, effectifs) ; celui-ci
travaille au niveau rubrique, seul niveau où se juge la conformité.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

LIGNE = re.compile(r"^(S\d{2}\.G\d{2}\.\d{2}\.\d{3}),'(.*)'\s*$")

RUB_NIR = "S21.G00.30.001"
RUB_INDIVIDU_DEBUT = RUB_NIR

# Rubriques internes au builder, jamais écrites dans le fichier final.
PREFIXE_INTERNE = "_"


def _chiffres(valeur: str) -> str:
    return re.sub(r"\D", "", valeur or "")


def lire_rubriques(contenu: bytes) -> List[Tuple[str, str]]:
    """Extrait les couples (rubrique, valeur) d'un fichier DSN plat."""
    lignes: List[Tuple[str, str]] = []
    texte = contenu.decode("latin-1", errors="replace")
    for brute in texte.splitlines():
        trouve = LIGNE.match(brute.strip())
        if trouve:
            lignes.append((trouve.group(1), trouve.group(2)))
    return lignes


@dataclass
class ProfilDsn:
    """Vue comparable d'un fichier DSN."""

    rubriques: Dict[str, int] = field(default_factory=dict)
    entete: Dict[str, List[str]] = field(default_factory=dict)
    individus: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    nb_lignes: int = 0

    @property
    def codes(self) -> set:
        return set(self.rubriques)


def construire_profil(contenu: bytes) -> ProfilDsn:
    """Range les rubriques d'un fichier par établissement puis par individu."""
    profil = ProfilDsn()
    courant: Optional[Dict[str, List[str]]] = None
    for rubrique, valeur in lire_rubriques(contenu):
        profil.nb_lignes += 1
        profil.rubriques[rubrique] = profil.rubriques.get(rubrique, 0) + 1
        if rubrique == RUB_INDIVIDU_DEBUT:
            cle = _chiffres(valeur)[:13]
            courant = profil.individus.setdefault(cle, {})
        cible = courant if courant is not None else profil.entete
        cible.setdefault(rubrique, []).append(valeur)
    return profil


@dataclass
class EcartAttendu:
    """Divergence délibérée avec la référence, donc tolérée par le diff."""

    rubrique: str
    motif: str
    depuis: str

    def couvre(self, rubrique: str) -> bool:
        return rubrique == self.rubrique


@dataclass
class RapportConformite:
    manquantes: List[str] = field(default_factory=list)
    en_trop: List[str] = field(default_factory=list)
    cardinalites: List[Tuple[str, int, int]] = field(default_factory=list)
    valeurs: List[Tuple[str, str, str, str]] = field(default_factory=list)
    individus_manquants: List[str] = field(default_factory=list)
    individus_en_trop: List[str] = field(default_factory=list)
    ecarts_toleres: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def conforme(self) -> bool:
        return not (
            self.manquantes
            or self.en_trop
            or self.cardinalites
            or self.valeurs
            or self.individus_manquants
            or self.individus_en_trop
        )

    def resume(self) -> str:
        if self.conforme:
            return "conforme à la référence"
        return (
            f"{len(self.manquantes)} rubriques manquantes, "
            f"{len(self.en_trop)} en trop, "
            f"{len(self.cardinalites)} cardinalités divergentes, "
            f"{len(self.valeurs)} valeurs divergentes, "
            f"{len(self.individus_manquants)} individus absents"
        )

    def texte(self, limite: int = 40) -> str:
        lignes = [self.resume()]
        if self.manquantes:
            lignes.append("\nRubriques absentes de notre fichier :")
            lignes += [f"  - {r}" for r in self.manquantes[:limite]]
            if len(self.manquantes) > limite:
                lignes.append(f"  … {len(self.manquantes) - limite} de plus")
        if self.en_trop:
            lignes.append("\nRubriques que la référence ne contient pas :")
            lignes += [f"  - {r}" for r in self.en_trop[:limite]]
        if self.cardinalites:
            lignes.append("\nNombre d'occurrences divergent :")
            lignes += [
                f"  - {r} : nous {a}, référence {b}"
                for r, a, b in self.cardinalites[:limite]
            ]
        if self.valeurs:
            lignes.append("\nValeurs divergentes :")
            lignes += [
                f"  - {cle} {r} : nous {a!r}, référence {b!r}"
                for cle, r, a, b in self.valeurs[:limite]
            ]
            if len(self.valeurs) > limite:
                lignes.append(f"  … {len(self.valeurs) - limite} de plus")
        if self.individus_manquants:
            lignes.append(
                f"\nIndividus de la référence absents chez nous : "
                f"{len(self.individus_manquants)}"
            )
        if self.ecarts_toleres:
            lignes.append("\nÉcarts délibérés (tolérés) :")
            lignes += [f"  - {r} : {motif}" for r, motif in self.ecarts_toleres]
        return "\n".join(lignes)


def _valeurs_egales(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a.replace(",", ".")) - float(b.replace(",", "."))) < 0.005
    except (TypeError, ValueError):
        return False


def _hors_perimetre(rubrique: str, hors: Sequence[str]) -> bool:
    """Vrai si la rubrique est exclue, par égalité ou par préfixe de bloc."""
    return any(rubrique == h or rubrique.startswith(h) for h in hors)


def _compare_valeurs(
    cle: str,
    notre: Dict[str, List[str]],
    reference: Dict[str, List[str]],
    tolerees: Sequence[EcartAttendu],
    rapport: RapportConformite,
    rubriques_a_ignorer: Sequence[str],
) -> None:
    for rubrique, attendues in reference.items():
        if _hors_perimetre(rubrique, rubriques_a_ignorer):
            continue
        obtenues = notre.get(rubrique)
        if obtenues is None:
            continue  # déjà signalé au niveau des rubriques absentes
        toleree = next((e for e in tolerees if e.couvre(rubrique)), None)
        if len(obtenues) != len(attendues) and toleree is None:
            rapport.cardinalites.append((f"{cle} {rubrique}", len(obtenues), len(attendues)))
        restantes = list(obtenues)
        for attendue in attendues:
            trouve = next(
                (v for v in restantes if _valeurs_egales(v, attendue)), None
            )
            if trouve is None:
                if toleree is not None:
                    rapport.ecarts_toleres.append((rubrique, toleree.motif))
                    continue
                rapport.valeurs.append(
                    (cle, rubrique, ", ".join(obtenues[:3]), attendue)
                )
            else:
                restantes.remove(trouve)


def comparer(
    notre_contenu: bytes,
    contenu_reference: bytes,
    *,
    ecarts_attendus: Sequence[EcartAttendu] = (),
    rubriques_hors_perimetre: Sequence[str] = (),
    comparer_les_valeurs: bool = True,
    comparer_les_individus: bool = True,
) -> RapportConformite:
    """Compare notre fichier à une référence acceptée par net-entreprises.

    ``rubriques_hors_perimetre`` permet de clore un lot sans être bloqué par les
    rubriques que les lots suivants apporteront.
    """
    notre = construire_profil(notre_contenu)
    reference = construire_profil(contenu_reference)
    hors = set(rubriques_hors_perimetre)
    rapport = RapportConformite()

    for rubrique in sorted(reference.codes - notre.codes):
        if _hors_perimetre(rubrique, hors):
            continue
        toleree = next((e for e in ecarts_attendus if e.couvre(rubrique)), None)
        if toleree is not None:
            rapport.ecarts_toleres.append((rubrique, toleree.motif))
            continue
        rapport.manquantes.append(rubrique)

    for rubrique in sorted(notre.codes - reference.codes):
        if rubrique.startswith(PREFIXE_INTERNE) or _hors_perimetre(rubrique, hors):
            continue
        toleree = next((e for e in ecarts_attendus if e.couvre(rubrique)), None)
        if toleree is not None:
            rapport.ecarts_toleres.append((rubrique, toleree.motif))
            continue
        rapport.en_trop.append(rubrique)

    # Le périmètre des individus ne se juge que si leur bloc est livré et que
    # les sortants sont traités : le cabinet déclare encore, le mois de leur
    # solde, des salariés que nous ne produisons pas.
    if comparer_les_individus and not _hors_perimetre(RUB_NIR, hors):
        for cle in sorted(set(reference.individus) - set(notre.individus)):
            rapport.individus_manquants.append(cle)
        for cle in sorted(set(notre.individus) - set(reference.individus)):
            rapport.individus_en_trop.append(cle)

    if comparer_les_valeurs:
        _compare_valeurs(
            "établissement",
            notre.entete,
            reference.entete,
            ecarts_attendus,
            rapport,
            list(hors),
        )
        for cle in sorted(set(notre.individus) & set(reference.individus)):
            _compare_valeurs(
                cle,
                notre.individus[cle],
                reference.individus[cle],
                ecarts_attendus,
                rapport,
                list(hors),
            )

    return rapport
