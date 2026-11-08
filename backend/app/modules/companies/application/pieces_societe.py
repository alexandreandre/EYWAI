"""Lister, déposer, ouvrir et retirer les pièces de la société."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.companies.domain.overview import is_jei_company_configured
from app.modules.companies.domain.pieces_societe import (
    TYPES_DE_PIECES,
    chemin_de_la_piece,
    chemin_de_la_societe,
    dossier_du_type,
    etat_des_pieces,
    nom_affiche,
    verifier_depot,
)
from app.modules.companies.infrastructure import pieces_repository as depot


def _fichiers(company_id: str, type_piece: str) -> list[dict[str, Any]]:
    dossier = dossier_du_type(company_id, type_piece)
    return [
        {
            "chemin": f"{dossier}/{ligne['name']}",
            "nom": nom_affiche(ligne["name"]),
            "depose_le": ligne.get("created_at"),
        }
        for ligne in depot.lister_dossier(dossier)
        if ligne.get("name") and not ligne["name"].startswith(".")
    ]


def lister(company_id: str) -> dict[str, Any]:
    fichiers = {t: _fichiers(company_id, t) for t in TYPES_DE_PIECES}
    return etat_des_pieces(
        fichiers,
        a_une_convention=depot.a_une_convention(company_id),
        statut_jei=is_jei_company_configured(depot.reglages_jei(company_id)),
    )


def deposer(
    company_id: str, type_piece: str, nom: str, contenu: bytes, format_fichier: str | None
) -> None:
    verifier_depot(type_piece, contenu, format_fichier)
    chemin = chemin_de_la_piece(company_id, type_piece, nom, uuid.uuid4().hex[:12])
    depot.deposer(chemin, contenu, format_fichier or "application/octet-stream")


def lien(company_id: str, chemin: str) -> str:
    return depot.lien_signe(chemin_de_la_societe(company_id, chemin))


def retirer(company_id: str, chemin: str) -> None:
    depot.supprimer(chemin_de_la_societe(company_id, chemin))
