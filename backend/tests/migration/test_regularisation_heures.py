"""Une régularisation posée dans les saisies du mois traverse tout le pipeline heures."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from tests.migration.fixtures import build_employee_fixture_dir

EMPLOYEE_APP = "TEST_MIG_REGUL"
YEAR, MONTH = 2026, 4
EMPLOYEE_ID = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "22222222-2222-4222-8222-222222222222"
_HOOK_CET = "app.modules.cet.application.payroll_hook"
_HOOK_MOD = "app.modules.modulation.application.payroll_hook"


def _needs_supabase():
    return not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _generer(regularisations: list[dict] | None):
    from app.core.paths import payroll_engine_employee_folder, payroll_engine_root
    from app.modules.modulation.application.payroll_hook import ModulationPayrollResult
    from app.modules.payroll.documents.payslip_run_heures import run_payslip_generation_heures
    from app.modules.payroll.engine.corrections_manuelles import CLE_REGULARISATIONS_COTISATION

    racine = payroll_engine_root()
    build_employee_fixture_dir(racine, EMPLOYEE_APP, YEAR, MONTH, mode="heures")
    dossier = payroll_engine_employee_folder(EMPLOYEE_APP)
    if regularisations:
        chemin = dossier / "saisies" / f"{MONTH:02d}.json"
        saisie = json.loads(chemin.read_text(encoding="utf-8"))
        saisie[CLE_REGULARISATIONS_COTISATION] = regularisations
        chemin.write_text(json.dumps(saisie), encoding="utf-8")

    def _inchange(*args, **kwargs):
        calendrier = args[3] if len(args) > 3 else kwargs["calendrier_etendu"]
        return calendrier, []

    def _modulation(*args, **kwargs):
        calendrier = args[4] if len(args) > 4 else kwargs["calendrier_etendu"]
        return calendrier, [], ModulationPayrollResult()

    with (
        patch(f"{_HOOK_MOD}.apply_modulation_hour_account_to_calendar", side_effect=_modulation),
        patch(f"{_HOOK_CET}.apply_cet_deposits_to_calendar", side_effect=_inchange),
        patch(f"{_HOOK_CET}.apply_cet_withdrawals_to_calendar", side_effect=_inchange),
        patch("app.modules.cet.infrastructure.repository.get_cet_settings_row", return_value={}),
        patch(f"{_HOOK_MOD}.finalize_modulation_payroll_application"),
        patch(f"{_HOOK_CET}.finalize_cet_payroll_application"),
        patch(f"{_HOOK_CET}.apply_cet_cp_debits_for_payroll"),
    ):
        bulletin = run_payslip_generation_heures(
            dossier,
            YEAR,
            MONTH,
            racine,
            company_id=COMPANY_ID,
            employee_id=EMPLOYEE_ID,
            persister=False,
        )
    cumuls = json.loads((dossier / "cumuls" / f"{MONTH:02d}.json").read_text(encoding="utf-8"))["cumuls"]
    return bulletin, cumuls


def _premiere_ligne_a_taux_salarial(bulletin):
    for rubrique in bulletin["cotisations_officielles"]:
        for ligne in rubrique["lignes"]:
            if ligne.get("coti_id") and (ligne.get("taux_salarial") or 0) > 0 and not ligne.get("regularisation"):
                return ligne
    raise AssertionError("aucune cotisation salariale à taux")


@pytest.mark.skipif(_needs_supabase(), reason="SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
def test_une_regularisation_salariale_change_les_cotisations_et_le_net_social_d_autant():
    avant, cumuls_avant = _generer(None)
    cible = _premiere_ligne_a_taux_salarial(avant)
    regul = {
        "type": "regularisation_cotisation",
        "coti_id": cible["coti_id"],
        "libelle": cible["libelle"],
        "motif": "Essai de régularisation",
        "base": 100.0,
        "taux_salarial": cible["taux_salarial"],
        "taux_patronal": cible.get("taux_patronal") or 0.0,
        "saisie_id": "s-essai",
    }
    apres, cumuls_apres = _generer([regul])

    delta = round(100.0 * cible["taux_salarial"], 2)
    assert apres["structure_cotisations"]["total_salarial"] == pytest.approx(
        avant["structure_cotisations"]["total_salarial"] + delta, abs=0.005
    )
    assert apres["synthese_net"]["net_social_avant_impot"] == pytest.approx(
        avant["synthese_net"]["net_social_avant_impot"] - delta, abs=0.005
    )
    assert apres["salaire_brut"] == avant["salaire_brut"]
    assert cumuls_apres["net_imposable"] <= cumuls_avant["net_imposable"]
    regularisees = [ligne for rubrique in apres["cotisations_officielles"] for ligne in rubrique["lignes"] if ligne.get("regularisation")]
    assert [ligne["libelle"] for ligne in regularisees] == [f"Régularisation – {cible['libelle']}"]
