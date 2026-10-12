"""Les documents de sortie ne se contredisent pas (relevé du 12/10/2026, vidéo H).

Le certificat de travail disait le maintien des garanties « à titre gratuit » ;
l'attestation de portabilité le disait « subordonné au paiement des cotisations
par le bénéficiaire ». La loi dit gratuit : « bénéficient du maintien à titre
gratuit de cette couverture » (CSS L911-8, loi n° 2013-504, texte adopté :
https://www.senat.fr/leg/tas12-142.html). Le 5° demande à l'ancien salarié de
justifier de sa situation auprès de l'organisme assureur ; aucun délai de dix
jours n'y figure.

Le nom de l'attestation destinée à France Travail est le même partout : la
checklist dit « Attestation France Travail », le menu et l'espace du salarié
disaient « Attestation employeur ».
"""

from __future__ import annotations

import io

import pytest
from PyPDF2 import PdfReader

from app.modules.employee_exits.infrastructure.mappers import DOCUMENT_NAME_MAP
from app.services.portability_document_generator import PortabilityDocumentGenerator

pytestmark = pytest.mark.unit


def _texte(pdf: bytes) -> str:
    texte = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    return " ".join(texte.split())


@pytest.mark.parametrize("regime", ["mutuelle", "prevoyance"])
def test_l_attestation_de_portabilite_dit_le_maintien_gratuit(regime):
    generateur = PortabilityDocumentGenerator()
    produire = getattr(generateur, f"generate_portabilite_{regime}")
    texte = _texte(
        produire(
            {"first_name": "Jeanne", "last_name": "Essai", "job_title": "Opératrice"},
            {"company_name": "Société QA"},
            "15/10/2026",
            "fin_cdd",
        )
    )
    assert "subordonné au paiement" not in texte
    assert "titre gratuit" in texte
    assert "dix jours" not in texte


def test_l_attestation_france_travail_porte_son_nom_dans_l_espace_du_salarie():
    assert DOCUMENT_NAME_MAP["attestation_pole_emploi"] == "Attestation France Travail"
