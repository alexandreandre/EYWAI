"""Garde de génération : un cadre sans prévoyance n'a pas de bulletin.

ANI du 17/11/2017, art. 1er : prévoyance des cadres à la charge exclusive de
l'employeur. Audit du 03/11/2026 : un cadre de la holding payé quatre mois sans
aucune prévoyance. Le refus vient avant tout calcul et toute écriture, il vaut
pour une correction comme pour une génération, et aucun forçage ne le passe :
la seule sortie est de cocher la prévoyance sur la fiche. Le bac à sable n'y
passe pas.
"""

from __future__ import annotations

import pytest

from app.modules.payslips.application.commands import generate_payslip, salarie_generable
from app.modules.payslips.application.dto import GeneratePayslipInput, PayslipBadRequestError
from tests.unit.payslips.test_garde_heures_sur_arret import _SALARIEE, _arret_de_septembre, _generation

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


def test_un_cadre_sans_prevoyance_ne_se_genere_pas():
    with _generation(_ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": False})) as generateur:
        with pytest.raises(PayslipBadRequestError) as exc:
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_not_called()
    generateur.generate_forfait.assert_not_called()
    assert str(exc.value).startswith("Bulletin non généré : Octavie est cadre, sans prévoyance")


def test_aucun_forcage_ne_passe_la_garde():
    cmd = GeneratePayslipInput(
        employee_id="emp-1", year=2026, month=9,
        force_calendrier_incomplet=True, regenerer_bulletin_valide=True,
        partir_de_cumuls_a_zero=True,
    )
    with _generation(_ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": False})) as generateur:
        with pytest.raises(PayslipBadRequestError):
            generate_payslip(cmd)

    generateur.generate_heures.assert_not_called()


def test_une_correction_est_refusee_aussi():
    """`salarie_generable` est l'entrée commune de la génération et des corrections."""
    with _generation(_ligne_vide(), statut="Cadre", employee=_cadre({"adhesion": True, "lignes_specifiques": []})):
        with pytest.raises(PayslipBadRequestError) as exc:
            salarie_generable("emp-1", 2026, 9)

    assert "aucune ligne" in str(exc.value)


def test_un_cadre_couvert_se_genere():
    employe = _cadre({"adhesion": True, "lignes_specifiques": [_LIGNE]})
    with _generation(_ligne_vide(), statut="Cadre", employee=employe) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_called_once()


def test_un_non_cadre_sans_prevoyance_n_est_pas_bloque_par_cette_garde():
    with _generation(_ligne_vide()) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_called_once()


_COMMANDS = "app.modules.payslips.application.commands"


def _non_cadre_plasturgie(**extra):
    return {
        **_SALARIEE,
        "hire_date": "2026-03-02",
        "contract_type": "CDD",
        "specificites_paie": {"prevoyance": {"adhesion": False}},
        **extra,
    }


def test_un_non_cadre_de_la_plasturgie_sans_prevoyance_apres_trois_mois_ne_se_genere_pas():
    """Accord du 29/10/2014, art. 3 : la prévoyance est due après trois mois."""
    from unittest.mock import patch

    with _generation(_ligne_vide(), employee=_non_cadre_plasturgie()) as generateur:
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value="0292"):
            with pytest.raises(PayslipBadRequestError) as exc:
                generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_not_called()
    assert "convention de la plasturgie" in str(exc.value)


def test_hors_plasturgie_le_non_cadre_sans_prevoyance_se_genere():
    from unittest.mock import patch

    with _generation(_ligne_vide(), employee=_non_cadre_plasturgie()) as generateur:
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value="3248"):
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_called_once()


def test_la_convention_illisible_se_lit_sur_la_classification():
    from unittest.mock import patch

    employe = _non_cadre_plasturgie(classification_conventionnelle={"idcc": "0292"})
    with _generation(_ligne_vide(), employee=employe):
        with patch(f"{_COMMANDS}.resolve_employee_idcc", return_value=None):
            with pytest.raises(PayslipBadRequestError):
                salarie_generable("emp-1", 2026, 9)
