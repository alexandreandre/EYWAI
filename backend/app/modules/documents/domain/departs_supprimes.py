"""Les brouillons de documents de sortie d'un départ supprimé ne s'affichent plus.

Un départ génère ses documents (certificat de travail, attestation France
Travail, reçu pour solde de tout compte, portabilités) et en range une copie
dans les documents du salarié (`generation_context.exit_id`). Supprimer le
départ retire ses documents de sortie mais laissait ces copies : la liste du
salarié montrait deux séries de brouillons, dont une décrivant un départ qui
n'existe plus (réunion du 10/11/2026, Colorplast, F.A.O.). Un brouillon ne
sert qu'à être revu puis envoyé : celui d'un départ supprimé est un piège.

Rien n'est effacé : ils sortent seulement de la liste. Un document déjà envoyé
ou signé reste affiché, trace de ce que le salarié a reçu.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

#: Sources posées par la génération des documents d'un départ.
SOURCES_DE_DEPART = ("employee_exit_bundle", "employee_exit_bundle_portability")


def depart_du_document(document: Mapping[str, Any]) -> str | None:
    """L'identifiant du départ qui a généré ce document, s'il en vient."""
    contexte = document.get("generation_context")
    if not isinstance(contexte, Mapping):
        return None
    if contexte.get("source") not in SOURCES_DE_DEPART:
        return None
    exit_id = contexte.get("exit_id")
    return str(exit_id) if exit_id else None


def departs_cites(documents: Iterable[Mapping[str, Any]]) -> set[str]:
    return {d for d in (depart_du_document(doc) for doc in documents) if d}


def sans_les_brouillons_de_departs_supprimes(
    documents: Iterable[Mapping[str, Any]], departs_existants: Iterable[str]
) -> list:
    """Les documents, sans les brouillons d'un départ qui n'existe plus."""
    existants = {str(d) for d in departs_existants}
    gardes = []
    for document in documents:
        depart = depart_du_document(document)
        if (
            depart is not None
            and depart not in existants
            and str(document.get("status") or "") == "brouillon"
        ):
            continue
        gardes.append(document)
    return gardes


__all__ = [
    "SOURCES_DE_DEPART",
    "depart_du_document",
    "departs_cites",
    "sans_les_brouillons_de_departs_supprimes",
]
