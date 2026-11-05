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


# --- La commande prépare la lettre, ou refuse avant toute écriture ---------------

JEANNE = {
    "id": "sal-1",
    "first_name": "Jeanne",
    "last_name": "Essai",
    "employment_status": "actif",
}


@pytest.fixture
def generation(monkeypatch):
    """Lecteurs et service remplacés ; renvoie les appels faits au service."""
    appels: list[dict] = []
    lecteurs = {"bulletins": [], "fin_essai": None, "salarie": dict(JEANNE)}

    monkeypatch.setattr(commands, "_load_employee", lambda *_: dict(lecteurs["salarie"]))
    monkeypatch.setattr(commands, "_load_company", lambda *_: {"company_name": "Société Exemple"})
    monkeypatch.setattr(
        commands.attestation_queries,
        "bulletins_remis_du_salarie",
        lambda employee_id, company_id: list(lecteurs["bulletins"]),
    )
    monkeypatch.setattr(
        commands.attestation_queries,
        "fin_de_periode_d_essai_en_cours",
        lambda employee_id, company_id: lecteurs["fin_essai"],
    )

    def _generer(**kwargs):
        appels.append(kwargs)
        return {"document_id": "doc-1"}

    monkeypatch.setattr(commands.document_service, "generate_document", _generer)
    monkeypatch.setattr(commands.documents_repository, "get_by_id", lambda *_: {"id": "doc-1"})
    return lecteurs, appels


def _bulletin(year: int, month: int) -> dict:
    return {
        "year": year,
        "month": month,
        "payslip_data": {"salaire_brut": 2000.0, "synthese_net": {"net_social_avant_impot": 1500.0}},
    }


def test_un_salarie_parti_n_a_pas_d_attestation_de_travail(generation):
    lecteurs, appels = generation
    lecteurs["salarie"]["employment_status"] = "parti"
    with pytest.raises(ValueError, match="Jeanne Essai a quitté l'entreprise : c'est le certificat"):
        commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert appels == []


def test_la_periode_d_essai_en_cours_est_passee_a_la_lettre(generation):
    lecteurs, appels = generation
    lecteurs["fin_essai"] = "2026-12-01"
    commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert appels[0]["context"]["periode_essai_fin"] == "2026-12-01"


def test_sans_bulletin_remis_pas_d_attestation_de_salaire(generation):
    _, appels = generation
    with pytest.raises(ValueError, match="Aucun bulletin remis à Jeanne Essai"):
        commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire"))
    assert appels == []


def test_le_nombre_de_mois_demande_est_respecte(generation):
    lecteurs, appels = generation
    lecteurs["bulletins"] = [_bulletin(2026, m) for m in (7, 8, 9, 10)]
    commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire", nombre_mois=2))
    contexte = appels[0]["context"]
    assert [ligne["month"] for ligne in contexte["mois_de_paie"]] == [9, 10]
    assert contexte["nombre_mois_demande"] == 2


def test_trois_mois_sans_precision(generation):
    lecteurs, appels = generation
    lecteurs["bulletins"] = [_bulletin(2026, m) for m in (7, 8, 9, 10)]
    commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire"))
    assert len(appels[0]["context"]["mois_de_paie"]) == 3


def test_un_salarie_parti_garde_son_attestation_de_salaire(generation):
    lecteurs, appels = generation
    lecteurs["salarie"]["employment_status"] = "parti"
    lecteurs["bulletins"] = [_bulletin(2026, 9)]
    commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire"))
    assert len(appels) == 1
