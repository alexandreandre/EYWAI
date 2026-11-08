"""Attestations à la demande (05/11/2026) : la commande refuse et prépare avant toute écriture.

Deux lettres seulement (décision d'Alexandre) : l'attestation d'emploi et
l'attestation de salaire. Les sept autres types disaient la même chose que
l'attestation d'emploi, ou reprenaient le salaire de la fiche au lieu des
bulletins ; leur libellé reste pour les documents déjà générés.
"""
from __future__ import annotations

from datetime import date

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
    assert DOCUMENT_TYPE_LABELS["attestation_emploi"] == "Attestation d'emploi"


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
    lecteurs = {"bulletins": [], "salarie": dict(JEANNE), "depart": None}

    monkeypatch.setattr(commands, "_load_employee", lambda *_: dict(lecteurs["salarie"]))
    monkeypatch.setattr(commands, "_load_company", lambda *_: {"company_name": "Société Exemple"})
    monkeypatch.setattr(
        commands.attestation_queries,
        "bulletins_remis_du_salarie",
        lambda employee_id, company_id: list(lecteurs["bulletins"]),
    )
    monkeypatch.setattr(
        commands.attestation_queries,
        "dernier_jour_de_depart",
        lambda employee_id, company_id: lecteurs["depart"],
    )
    monkeypatch.setattr(commands, "aujourd_hui_local", lambda: date(2026, 11, 5))

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


def test_l_attestation_d_emploi_ne_prepare_rien_de_plus_que_le_modele(generation):
    """Le modèle de la cliente (06/11/2026) ne parle ni de période d'essai ni de départ."""
    _, appels = generation
    commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert appels[0]["context"] == {}
    assert not hasattr(commands.attestation_queries, "fin_de_periode_d_essai_en_cours")


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


# --- Une lettre signée ne dit jamais faux : 27 fiches du test au 05/11 ------------


def test_un_dernier_jour_passe_vaut_un_depart_meme_si_la_fiche_dit_en_sortie(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(employment_status="en_sortie", hire_date="2024-01-15")
    lecteurs["depart"] = date(2026, 10, 31)
    with pytest.raises(ValueError, match="Jeanne Essai a quitté l'entreprise le 31 octobre 2026 : c'est le certificat"):
        commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert appels == []


def test_un_contrat_fini_sur_une_fiche_active_dit_quoi_corriger(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(contract_type="CDD", hire_date="2024-01-15", contract_end_date="2026-06-30")
    with pytest.raises(ValueError) as refus:
        commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    message = str(refus.value)
    assert "le contrat de Jeanne Essai a pris fin le 30 juin 2026" in message
    assert "certificat de travail" in message
    assert "Modifier la fiche" in message
    assert appels == []


def test_un_depart_a_venir_n_empeche_pas_l_attestation(generation):
    """Encore dans les effectifs le jour de la lettre : c'est ce que dit le modèle."""
    lecteurs, appels = generation
    lecteurs["salarie"].update(employment_status="en_sortie", hire_date="2024-01-15")
    lecteurs["depart"] = date(2026, 11, 30)
    commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert len(appels) == 1


def test_le_dernier_jour_du_contrat_est_encore_dans_les_effectifs(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(contract_type="CDD", hire_date="2024-01-15", contract_end_date="2026-11-05")
    commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert len(appels) == 1


def test_un_salarie_revenu_garde_son_attestation(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(contract_type="CDI", hire_date="2024-01-15")
    lecteurs["depart"] = date(2023, 6, 30)
    commands.generate_document("soc-1", "rh-1", _demande("attestation_emploi"))
    assert "depart_prevu" not in appels[0]["context"]


def test_l_attestation_de_salaire_sait_si_le_salarie_est_parti(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(employment_status="parti", hire_date="2024-01-15")
    lecteurs["depart"] = date(2026, 10, 31)
    lecteurs["bulletins"] = [_bulletin(2026, 9)]
    commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire"))
    contexte = appels[0]["context"]
    assert contexte["a_quitte"] is True
    assert contexte["date_de_sortie"] == "2026-10-31"


def test_l_attestation_de_salaire_d_un_salarie_en_poste(generation):
    lecteurs, appels = generation
    lecteurs["salarie"].update(hire_date="2024-01-15")
    lecteurs["bulletins"] = [_bulletin(2026, 9)]
    commands.generate_document("soc-1", "rh-1", _demande("attestation_salaire"))
    assert appels[0]["context"]["a_quitte"] is False
