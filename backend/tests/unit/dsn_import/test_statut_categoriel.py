"""Statut conventionnel (S21.G00.40.002) → Cadre / Non-Cadre à l'import DSN.

Cahier technique DSN 2026 : seuls 03 (cadre dirigeant) et 04 (autres cadres)
sont des cadres. 05 profession intermédiaire, 06 employé, 07 ouvrier, 08 à 10
fonction publique. Un employé ou un ouvrier importé ne doit plus se retrouver
« Cadre », ni au forfait jours qui en découle.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.model import (
    ContratBlock,
    EtablissementBlock,
    IndividuBlock,
)
from app.modules.dsn_import.domain.normalize import map_statut_cadre

pytestmark = pytest.mark.unit

SIRET = "53438649500053"


@pytest.mark.parametrize("code", ["03", "04", "3", "4"])
def test_les_codes_cadres(code):
    assert map_statut_cadre(code) == "Cadre"


@pytest.mark.parametrize("code", ["01", "02", "05", "06", "07", "08", "09", "10", ""])
def test_les_autres_codes_ne_sont_pas_cadres(code):
    assert map_statut_cadre(code) == "Non-Cadre"


def _payload(statut: str) -> dict:
    individu = IndividuBlock(
        nom="FICTIF",
        prenom="Jean",
        nir="185017512345678",
        date_naissance="01011985",
        contrats=[ContratBlock(date_debut="01092026", nature="02", statut=statut)],
    )
    return map_employee_payload(individu, EtablissementBlock(siret=SIRET), SIRET)


@pytest.mark.parametrize("code", ["05", "06", "07"])
def test_un_employe_ou_un_ouvrier_importe_reste_non_cadre_hors_forfait(code):
    payload = _payload(code)
    assert payload["statut"] == "Non-Cadre"
    assert payload["is_forfait_jour"] is False
    assert payload["classification_conventionnelle"]["statut_categoriel"] == "Non-Cadre"
    assert payload["classification_conventionnelle"]["code_statut_dsn"] == code


def test_un_cadre_importe_reste_cadre():
    payload = _payload("04")
    assert payload["statut"] == "Cadre"
    assert payload["classification_conventionnelle"]["statut_categoriel"] == "Cadre"


def _payload_unite(statut: str, unite: str) -> dict:
    individu = IndividuBlock(
        nom="FICTIF",
        prenom="Jean",
        nir="185017512345678",
        date_naissance="01011985",
        contrats=[
            ContratBlock(date_debut="01092026", nature="01", statut=statut, unite_quotite=unite)
        ],
    )
    return map_employee_payload(individu, EtablissementBlock(siret=SIRET), SIRET)


@pytest.mark.parametrize(
    ("statut", "unite", "forfait"),
    [("03", "10", False), ("04", "99", False), ("06", "20", True), ("03", "20", True)],
)
def test_le_forfait_jours_vient_de_l_unite_declaree_pas_du_statut(statut, unite, forfait):
    """S21.G00.40.011 : 20 = forfait jour. Un cadre en heures n'est pas au forfait (E4, 06/11)."""
    assert _payload_unite(statut, unite)["is_forfait_jour"] is forfait
