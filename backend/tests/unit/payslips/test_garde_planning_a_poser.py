"""Garde de génération : des heures pointées sans planning prévu ne se forcent pas
(contrôle du 10/11/2026 : sans prévu, tout partait en heures supplémentaires)."""

from __future__ import annotations

import pytest

from app.modules.payslips.application.commands import generate_payslip
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipCalendarIncompleteError,
    PayslipPlanningAPoserError,
)
from tests.unit.payslips.test_garde_heures_sur_arret import _generation

pytestmark = pytest.mark.unit


def _ligne(pointes, prevus=()):
    return {
        "planned_calendar": {
            "calendrier_prevu": [{"jour": j, "type": t, "heures_prevues": 7.0 if t == "travail" else 0} for j, t in prevus]
        },
        "actual_hours": {"calendrier_reel": [{"jour": j, "heures_faites": 8.0} for j in pointes]},
    }


def _cmd(**kw):
    return GeneratePayslipInput(employee_id="emp-1", year=2026, month=9, **kw)


def test_le_forcage_ne_passe_pas_quand_les_jours_pointes_n_ont_pas_de_prevu():
    with _generation(_ligne((7, 8, 9, 10))) as generateur:
        with pytest.raises(PayslipPlanningAPoserError) as exc:
            generate_payslip(_cmd(force_calendrier_incomplet=True))

    generateur.generate_heures.assert_not_called()
    assert exc.value.code == "planning_a_poser"
    assert exc.value.http_status == 422
    assert exc.value.details == {"jours": ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10"]}
    assert str(exc.value).startswith("Octavie n'a pas de planning prévu pour 4 jours pointés (07/09–10/09).")
    assert "heures supplémentaires" in str(exc.value)


def test_le_message_arrive_des_le_premier_essai_sans_forcage():
    with _generation(_ligne((7, 8, 9))):
        with pytest.raises(PayslipPlanningAPoserError):
            generate_payslip(_cmd())


def test_deux_jours_en_plus_restent_un_calendrier_incomplet_ordinaire():
    with _generation(_ligne((7, 8))) as generateur:
        with pytest.raises(PayslipCalendarIncompleteError):
            generate_payslip(_cmd())
        generate_payslip(_cmd(force_calendrier_incomplet=True))

    generateur.generate_heures.assert_called_once()


def test_un_jour_de_repos_travaille_n_est_pas_un_planning_a_poser():
    prevus = [(7, "repos"), (8, "repos"), (9, "repos")]
    with _generation(_ligne((7, 8, 9), prevus)) as generateur:
        generate_payslip(_cmd(force_calendrier_incomplet=True))

    generateur.generate_heures.assert_called_once()


def test_une_fois_le_planning_pose_le_refus_disparait():
    prevus = [(7, "travail"), (8, "travail"), (9, "travail")]
    with _generation(_ligne((7, 8, 9), prevus)) as generateur:
        generate_payslip(_cmd(force_calendrier_incomplet=True))

    generateur.generate_heures.assert_called_once()
