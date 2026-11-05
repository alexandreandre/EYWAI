"""Attestations à la demande (05/11/2026) : la commande refuse et prépare avant toute écriture.

Deux lettres seulement (décision d'Alexandre) : l'attestation de travail et
l'attestation de salaire. Les sept autres types disaient la même chose que
l'attestation de travail, ou reprenaient le salaire de la fiche au lieu des
bulletins ; leur libellé reste pour les documents déjà générés.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.document_library.schemas.requests import (
    ATTESTATIONS_RETIREES,
    DOCUMENT_TYPE_LABELS,
    KNOWN_DOCUMENT_TYPES,
)
from app.modules.documents.application import commands
from app.modules.documents.schemas.requests import GenerateDocumentRequest

pytestmark = pytest.mark.unit


def _demande(document_type: str, **autres) -> GenerateDocumentRequest:
    return GenerateDocumentRequest(
        employee_id="sal-1",
        document_type=document_type,
        category="attestation_courante",
        **autres,
    )


def test_deux_types_seulement_les_autres_gardent_leur_libelle():
    assert {"attestation_emploi", "attestation_salaire"} <= KNOWN_DOCUMENT_TYPES
    assert not (ATTESTATIONS_RETIREES & KNOWN_DOCUMENT_TYPES)
    assert len(ATTESTATIONS_RETIREES) == 7
    for type_retire in ATTESTATIONS_RETIREES:
        assert DOCUMENT_TYPE_LABELS[type_retire]
    assert DOCUMENT_TYPE_LABELS["attestation_emploi"] == "Attestation de travail"


@pytest.mark.parametrize("type_retire", sorted(ATTESTATIONS_RETIREES))
def test_un_type_retire_est_refuse_avec_un_message_clair(type_retire):
    with pytest.raises(ValueError, match="Ce type d'attestation n'existe plus"):
        commands.generate_document("soc-1", "rh-1", _demande(type_retire))


@pytest.mark.parametrize("nombre", [0, 13])
def test_le_nombre_de_mois_va_de_1_a_12(nombre):
    with pytest.raises(ValidationError):
        _demande("attestation_salaire", nombre_mois=nombre)
    assert _demande("attestation_salaire", nombre_mois=12).nombre_mois == 12
