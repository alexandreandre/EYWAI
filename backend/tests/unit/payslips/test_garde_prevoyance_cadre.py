"""Prévoyance que la loi impose et que la fiche n'a pas : le bulletin le dit.

ANI du 17/11/2017, art. 1er : prévoyance des cadres à la charge exclusive de
l'employeur. Audit du 03/11/2026 : un cadre de la holding payé quatre mois sans
aucune prévoyance. Jusqu'au 11/11/2026, un refus de génération ; depuis (Elsa,
R109 et R111 : un salarié multi-employeurs peut être couvert ailleurs), le
bulletin se calcule et porte l'alerte, transmise au générateur.
"""

from __future__ import annotations

import pytest

from app.modules.payslips.application.commands import generate_payslip, salarie_generable
from app.modules.payslips.application.dto import GeneratePayslipInput
from tests.unit.payslips.test_garde_heures_sur_arret import _SALARIEE, _arret_de_septembre, _generation  # noqa: F401

pytestmark = pytest.mark.unit

_LIGNE = {"libelle": "Prévoyance cadre TA", "base": "brut_plafonne", "salarial": 0.0, "patronal": 0.015}


def _cadre(prevoyance):
    return {
        **_SALARIEE,
        "statut": "Cadre",
        "specificites_paie": {"prevoyance": prevoyance},
        "classification_conventionnelle": {"statut_categoriel": "Cadre"},
    }


def _ligne_vide():
    """Septembre en arrêt, sans heure saisie : aucune autre garde ne refuse."""
    return _arret_de_septembre({})


_VUES: dict[int, list] = {}


def _toutes_les_alertes(generateur):
    """Les alertes que le générateur voit pendant son appel (variable de contexte)."""
    generateur.generate_heures.assert_called_once()
    return _VUES.get(id(generateur), [])


@pytest.fixture(autouse=True)
def _capturer_les_alertes(monkeypatch):
    from app.modules.payroll.documents.alertes_d_entree import alertes_d_entree_courantes
    from tests.unit.payslips import test_garde_heures_sur_arret as base

    origine = base._generation

    from contextlib import contextmanager

    @contextmanager
    def _generation(*args, **kwargs):
        with origine(*args, **kwargs) as generateur:
            def _vu(*a, **k):
                _VUES[id(generateur)] = alertes_d_entree_courantes()
                return generateur.generate_heures.return_value
            generateur.generate_heures.side_effect = _vu
            yield generateur

    monkeypatch.setattr(__import__(__name__, fromlist=["_generation"]), "_generation", _generation)


def _alertes_transmises(generateur):
    """Les alertes de prévoyance ; la mutuelle a ses propres tests plus bas."""
    return [a for a in _toutes_les_alertes(generateur) if a["code"].startswith("prevoyance")]


def test_un_cadre_sans_prevoyance_se_genere_avec_l_alerte():
    with _generation(_ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": False})) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    alertes = _alertes_transmises(generateur)
    assert [a["code"] for a in alertes] == ["prevoyance_cadre_absente"]
    assert alertes[0]["critique"] is False


def test_une_correction_n_est_plus_refusee():
    """`salarie_generable` est l'entrée commune de la génération et des corrections."""
    with _generation(_ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": True, "lignes_specifiques": []})):
        salarie_generable("emp-1", 2026, 9)


def test_un_cadre_sans_ligne_porte_l_alerte_sans_ligne():
    with _generation(
        _ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": True, "lignes_specifiques": []})
    ) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert [a["code"] for a in _alertes_transmises(generateur)] == ["prevoyance_cadre_sans_ligne"]


def test_un_cadre_couvert_se_genere_sans_alerte():
    employe = _cadre({"adhesion": True, "lignes_specifiques": [_LIGNE]})
    with _generation(_ligne_vide(), statut="Cadre", employee=employe) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert _alertes_transmises(generateur) == []


def test_un_non_cadre_sans_prevoyance_n_est_pas_bloque_par_cette_garde():
    with _generation(_ligne_vide()) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert _alertes_transmises(generateur) == []


_COMMANDS = "app.modules.payslips.application.commands"


def _non_cadre_plasturgie(**extra):
    return {
        **_SALARIEE,
        "hire_date": "2026-03-02",
        "contract_type": "CDD",
        "specificites_paie": {"prevoyance": {"adhesion": False}},
        **extra,
    }


def test_un_non_cadre_de_la_plasturgie_sans_prevoyance_apres_trois_mois_porte_l_alerte():
    """Accord du 29/10/2014, art. 3 : la prévoyance est due après trois mois."""
    from unittest.mock import patch

    with _generation(_ligne_vide(), employee=_non_cadre_plasturgie()) as generateur:
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value="0292"):
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    alertes = _alertes_transmises(generateur)
    assert [a["code"] for a in alertes] == ["prevoyance_plasturgie_absente"]
    assert "convention de la plasturgie" in alertes[0]["message"]


def test_hors_plasturgie_le_non_cadre_sans_prevoyance_se_genere_sans_alerte():
    from unittest.mock import patch

    with _generation(_ligne_vide(), employee=_non_cadre_plasturgie()) as generateur:
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value="3248"):
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert _alertes_transmises(generateur) == []


def test_la_convention_illisible_se_lit_sur_la_classification():
    from unittest.mock import patch

    employe = _non_cadre_plasturgie(classification_conventionnelle={"idcc": "0292"})
    with _generation(_ligne_vide(), employee=employe) as generateur:
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value=None):
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert [a["code"] for a in _alertes_transmises(generateur)] == ["prevoyance_plasturgie_absente"]


# Mutuelle (R113, 11/11/2026) : absente sans dispense, le bulletin le dit, sans refus.


def test_un_cdi_sans_mutuelle_ni_dispense_porte_l_alerte_mutuelle():
    with _generation(_ligne_vide()) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    alertes = [a for a in _toutes_les_alertes(generateur) if a["code"] == "mutuelle_absente_ou_dispense"]
    assert len(alertes) == 1
    assert alertes[0]["message"].startswith("Mutuelle absente.")
    assert alertes[0]["critique"] is False


def test_une_dispense_complete_tait_l_alerte_mutuelle():
    employe = {
        **_SALARIEE,
        "specificites_paie": {
            "mutuelle": {
                "adhesion": False,
                "dispense": {"motif": "couverture_collective", "demande_recue_le": "2026-06-01"},
            }
        },
    }
    with _generation(_ligne_vide(), employee=employe) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    assert [a for a in _toutes_les_alertes(generateur) if a["code"].startswith("mutuelle")] == []
