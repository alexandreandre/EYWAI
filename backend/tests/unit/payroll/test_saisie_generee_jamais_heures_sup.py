"""Une saisie écrite par une règle de variables n'est jamais lue comme des heures sup.

Relecture du 27/11 (L19) : `_is_heures_sup_conjoncturelle_input` lit le nom, le
code d'export, la description et l'identifiant du catalogue. Une règle de
panier nommée « Panier supplémentaire » ou codée `prime_poste_hs` (description
« Auto: prime_poste_hs ») aurait été payée en heures sup.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.payslip_generator import _is_heures_sup_conjoncturelle_input

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "nom, code",
    [
        ("Panier supplémentaire", "panier_sup"),
        ("Panier", "prime_poste_hs"),
        ("Heures sup panier", "hs_panier"),
        ("Panier", "panier_jour"),
    ],
)
def test_une_saisie_generee_n_est_jamais_des_heures_sup(nom, code):
    saisie = {"name": nom, "description": f"Auto: {code}", "amount": 114.0, "payroll_quantity": 15}
    assert _is_heures_sup_conjoncturelle_input(saisie) is False


def test_des_heures_sup_saisies_a_la_main_restent_des_heures_sup():
    saisie = {"name": "Heures sup 25 %", "description": "", "amount": 0, "payroll_quantity": 4}
    assert _is_heures_sup_conjoncturelle_input(saisie) is True
