"""Les pièces de la société : ce que Martine attend, et où elles sont rangées.

Une pièce est un fichier déposé par la RH (contrat de prévoyance, justificatif
du statut JEI…). Rien ici ne touche au calcul de la paie : Martine range et
signale ce qui manque, le stockage fait foi (aucune table).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

PREFIXE = "pieces-societe"
TAILLE_MAX = 15 * 1024 * 1024
FORMATS_ACCEPTES = frozenset({"application/pdf", "image/jpeg", "image/png"})

TYPES_DE_PIECES: dict[str, dict[str, str]] = {
    "kbis": {
        "libelle": "Kbis et statuts",
        "pourquoi": "Ils établissent l'activité de la société, donc sa convention collective.",
    },
    "contrat_mutuelle": {
        "libelle": "Contrat de mutuelle",
        "pourquoi": "Il fixe l'organisme, les garanties et les cotisations déclarées.",
    },
    "contrat_prevoyance": {
        "libelle": "Contrat et notice de prévoyance",
        "pourquoi": "Ils fixent les taux, et ce que l'assureur verse en cas d'arrêt.",
    },
    "adhesion_branche": {
        "libelle": "Attestation d'adhésion à la fédération de branche",
        "pourquoi": "Certains minima et accords ne s'imposent qu'aux adhérents.",
    },
    "justificatif_jei": {
        "libelle": "Justificatif du statut de jeune entreprise innovante",
        "pourquoi": "Martine applique l'exonération : le statut et sa date doivent être prouvés.",
    },
    "accord_temps_travail": {
        "libelle": "Accord ou décision sur le temps de travail",
        "pourquoi": (
            "Sans convention de branche, le forfait en jours et le paiement des heures "
            "en repos reposent sur cet écrit."
        ),
    },
    "autre": {
        "libelle": "Autre pièce",
        "pourquoi": "Tout autre document utile à la paie ou au contrôle.",
    },
}


def _attendue(type_piece: str, *, a_une_convention: bool, statut_jei: bool) -> bool:
    if type_piece == "autre":
        return False
    if type_piece == "adhesion_branche":
        return a_une_convention
    if type_piece == "accord_temps_travail":
        return not a_une_convention
    if type_piece == "justificatif_jei":
        return statut_jei
    return True


def etat_des_pieces(
    fichiers: dict[str, list[dict[str, Any]]],
    *,
    a_une_convention: bool,
    statut_jei: bool,
) -> dict[str, Any]:
    """Une ligne par type, les pièces attendues d'abord, et le nombre de manquantes."""
    pieces = [
        {
            "type": type_piece,
            "libelle": piece["libelle"],
            "pourquoi": piece["pourquoi"],
            "attendue": _attendue(
                type_piece, a_une_convention=a_une_convention, statut_jei=statut_jei
            ),
            "fichiers": fichiers.get(type_piece, []),
        }
        for type_piece, piece in TYPES_DE_PIECES.items()
    ]
    pieces.sort(key=lambda p: not p["attendue"])
    return {
        "pieces": pieces,
        "manquantes": sum(1 for p in pieces if p["attendue"] and not p["fichiers"]),
    }


def _nom_sur(nom: str) -> str:
    """Le nom de fichier sans chemin, accents ni caractères que le stockage refuse."""
    base = nom.replace("\\", "/").rsplit("/", 1)[-1]
    ascii_seul = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    propre = re.sub(r"[^a-zA-Z0-9._-]+", "-", ascii_seul).strip("-.")
    return (propre[:180] or "document").lower()


def dossier_du_type(company_id: str, type_piece: str) -> str:
    return f"{PREFIXE}/{company_id}/{type_piece}"


def chemin_de_la_piece(company_id: str, type_piece: str, nom: str, jeton: str) -> str:
    return f"{dossier_du_type(company_id, type_piece)}/{jeton}_{_nom_sur(nom)}"


def nom_affiche(nom_stocke: str) -> str:
    """Le nom déposé, sans le jeton qui évite les collisions."""
    return nom_stocke.split("_", 1)[-1]


def chemin_de_la_societe(company_id: str, chemin: str) -> str:
    """Refuse tout chemin qui sortirait du dossier de la société active."""
    if ".." in chemin or not chemin.startswith(f"{PREFIXE}/{company_id}/"):
        raise ValueError("Cette pièce n'appartient pas à la société active.")
    return chemin


def verifier_depot(type_piece: str, contenu: bytes, format_fichier: str | None) -> None:
    if type_piece not in TYPES_DE_PIECES:
        raise ValueError("Type de pièce inconnu.")
    if not contenu:
        raise ValueError("Le fichier est vide.")
    if format_fichier not in FORMATS_ACCEPTES:
        raise ValueError("Formats acceptés : PDF, JPG ou PNG.")
    if len(contenu) > TAILLE_MAX:
        raise ValueError("Le fichier dépasse 15 Mo.")
