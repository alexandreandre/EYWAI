"""Lecture des taux PAS dans un fichier à blocs DSN.

Une DSN mensuelle et un compte rendu métier net-entreprises partagent la même
structure : des rubriques `Sxx.Gyy.zz.nnn` à plat, un bloc individu S21.G00.30 et
un bloc versement S21.G00.50 qui porte le taux. On lit donc les deux avec le
parser du module d'import DSN, sans dupliquer sa connaissance des rubriques.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from app.modules.dsn_import.application.mapping import extract_pas
from app.modules.dsn_import.domain.model import DsnFile, ParsedDsnSet
from app.modules.dsn_import.domain.parser import parse_dsn_content


@dataclass
class TauxFichier:
    """Un taux lu dans un fichier, avant tout rapprochement avec la base."""

    nir: str
    nom: str
    prenom: str
    matricule: str
    taux: Optional[float]
    type_taux: Optional[str]
    identifiant_taux: Optional[str]


def normaliser_nom(valeur: str) -> str:
    """Majuscules sans accent ni ponctuation, pour rapprocher deux graphies."""
    sans_accent = unicodedata.normalize("NFD", valeur or "")
    sans_accent = "".join(c for c in sans_accent if unicodedata.category(c) != "Mn")
    nettoye = "".join(c if c.isalnum() or c.isspace() else " " for c in sans_accent)
    return " ".join(nettoye.upper().split())


def lire_fichier(content: bytes, file_name: str) -> DsnFile:
    return parse_dsn_content(content, file_name=file_name)


def extraire_taux(dsn_file: DsnFile) -> List[TauxFichier]:
    """Un enregistrement par individu porteur d'un prélèvement à la source."""
    ensemble = ParsedDsnSet(files=[dsn_file])
    out: List[TauxFichier] = []
    for etab in ensemble.etablissements_by_siret().values():
        for individu in etab.individus:
            contrat = individu.contrats[0] if individu.contrats else None
            if contrat is None:
                continue
            pas = extract_pas(contrat)
            if not pas:
                continue
            taux = pas.get("taux")
            out.append(
                TauxFichier(
                    nir=(individu.nir or "").strip(),
                    nom=(individu.nom or "").strip(),
                    prenom=(individu.prenom or "").strip(),
                    matricule=(individu.matricule or "").strip(),
                    taux=None if taux is None else float(taux),
                    type_taux=pas.get("type_taux") or None,
                    identifiant_taux=pas.get("identifiant_taux") or None,
                )
            )
    return out


def periode_du_fichier(dsn_file: DsnFile) -> Optional[str]:
    return ParsedDsnSet(files=[dsn_file]).period_max


def siren_du_fichier(dsn_file: DsnFile) -> Optional[str]:
    return ParsedDsnSet(files=[dsn_file]).siren
