"""Garde de génération : un jour « absent, type à donner » bloque le bulletin,
sans forçage possible (retour d'Elsa du 28/10/2026)."""

from __future__ import annotations

import pytest

from app.modules.payslips.application.commands import generate_payslip
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipAbsentATyperError,
)
from tests.unit.payslips.test_garde_heures_sur_arret import _generation
from tests.unit.schedules.test_absent_a_typer import _septembre

pytestmark = pytest.mark.unit


def _ligne(absents):
    prevu, reel = _septembre(absents)[(2026, 9)]
    return {"planned_calendar": {"calendrier_prevu": prevu}, "actual_hours": {"calendrier_reel": reel}}


def test_un_jour_absent_sans_type_refuse_la_generation():
    with _generation(_ligne((9, 10))) as generateur:
        with pytest.raises(PayslipAbsentATyperError) as exc:
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_not_called()
    assert exc.value.code == "absent_a_typer"
    assert exc.value.http_status == 422
    assert exc.value.details == {"jours": ["2026-09-09", "2026-09-10"]}
    assert str(exc.value).startswith("Octavie a des jours marqués « absent » sans type")


def test_aucun_forcage_ne_passe_la_garde():
    cmd = GeneratePayslipInput(
        employee_id="emp-1", year=2026, month=9,
        force_calendrier_incomplet=True, regenerer_bulletin_valide=True,
    )
    with _generation(_ligne((9,))) as generateur:
        with pytest.raises(PayslipAbsentATyperError):
            generate_payslip(cmd)

    generateur.generate_heures.assert_not_called()


def test_une_fois_le_type_donne_la_generation_passe():
    with _generation(_ligne(())) as generateur:
        generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

    generateur.generate_heures.assert_called_once()
