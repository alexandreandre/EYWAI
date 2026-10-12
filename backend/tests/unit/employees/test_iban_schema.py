"""La fiche salarié s'enregistre avec un IBAN dont la clé ou la longueur est fausse.

Lot 33 : la fiche refusait (422) un IBAN à la clé fausse, et avec lui tous les
autres changements de la fiche. Depuis le 12/10/2026 (alerte plutôt que refus),
l'écran avertit et le serveur enregistre : le blocage reste au virement, dont
l'aperçu porte déjà l'IBAN faux en anomalie bloquante.
"""

import pytest

from app.modules.employees.schemas.requests import NewFullEmployee, UpdateEmployee

pytestmark = pytest.mark.unit

IBAN_VALIDE = "FR7630001007941234567890185"
IBAN_CLE_FAUSSE = "FR7630001007941234567890186"


def test_iban_valide_accepte():
    m = UpdateEmployee(coordonnees_bancaires={"iban": IBAN_VALIDE, "bic": "BNPAFRPP"})
    assert m.coordonnees_bancaires["iban"] == IBAN_VALIDE


def test_iban_avec_espaces_accepte():
    UpdateEmployee(coordonnees_bancaires={"iban": "FR76 3000 1007 9412 3456 7890 185"})


def test_cle_fausse_enregistree_avec_les_autres_changements():
    m = UpdateEmployee(
        coordonnees_bancaires={"iban": IBAN_CLE_FAUSSE}, job_title="Opératrice"
    )
    assert m.coordonnees_bancaires["iban"] == IBAN_CLE_FAUSSE
    assert m.job_title == "Opératrice"


def test_longueur_fausse_enregistree():
    m = UpdateEmployee(coordonnees_bancaires={"iban": "FR76300010079412"})
    assert m.coordonnees_bancaires["iban"] == "FR76300010079412"


def test_a_la_creation_aussi():
    champs = {
        "first_name": "Jeanne", "last_name": "Essai", "email": "jeanne@essai.fr",
        "hire_date": "2026-09-14", "contract_type": "CDI", "statut": "Non-Cadre",
        "job_title": "Préparatrice", "is_temps_partiel": False, "duree_hebdomadaire": 35,
        "salaire_de_base": {"valeur": 1900},
    }
    try:
        m = NewFullEmployee(**champs, coordonnees_bancaires={"iban": IBAN_CLE_FAUSSE})
    except Exception as exc:  # noqa: BLE001 — un autre champ requis : on ne teste que l'IBAN
        assert "IBAN" not in str(exc) and "Clé de contrôle" not in str(exc)
    else:
        assert m.coordonnees_bancaires["iban"] == IBAN_CLE_FAUSSE


def test_iban_vide_ou_absent_accepte():
    UpdateEmployee(coordonnees_bancaires={"iban": "", "bic": ""})
    UpdateEmployee(coordonnees_bancaires=None)
    UpdateEmployee(coordonnees_bancaires={})
