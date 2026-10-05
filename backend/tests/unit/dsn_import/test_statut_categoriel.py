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
