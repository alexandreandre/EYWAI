"""La fiche salarié refuse un IBAN dont la clé ou la longueur est fausse."""

import pytest
from pydantic import ValidationError

from app.modules.employees.schemas.requests import UpdateEmployee

pytestmark = pytest.mark.unit

IBAN_VALIDE = "FR7630001007941234567890185"
IBAN_CLE_FAUSSE = "FR7630001007941234567890186"


def test_iban_valide_accepte():
    m = UpdateEmployee(coordonnees_bancaires={"iban": IBAN_VALIDE, "bic": "BNPAFRPP"})
    assert m.coordonnees_bancaires["iban"] == IBAN_VALIDE


def test_iban_avec_espaces_accepte():
    UpdateEmployee(coordonnees_bancaires={"iban": "FR76 3000 1007 9412 3456 7890 185"})


def test_cle_fausse_refusee_avec_message():
    with pytest.raises(ValidationError) as exc:
        UpdateEmployee(coordonnees_bancaires={"iban": IBAN_CLE_FAUSSE})
    assert "Clé de contrôle" in str(exc.value)


def test_longueur_fausse_refusee():
    with pytest.raises(ValidationError) as exc:
        UpdateEmployee(coordonnees_bancaires={"iban": "FR76300010079412"})
    assert "27 caractères attendus" in str(exc.value)


def test_iban_vide_ou_absent_accepte():
    UpdateEmployee(coordonnees_bancaires={"iban": "", "bic": ""})
    UpdateEmployee(coordonnees_bancaires=None)
    UpdateEmployee(coordonnees_bancaires={})
