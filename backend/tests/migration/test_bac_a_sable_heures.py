"""Le run heures ne finalise aucun mouvement quand il ne persiste pas.

Même harnais que les tests de migration : un dossier de fixtures et Supabase
pour les barèmes. Les hooks qui lisent la base sont remplacés par des doublures
qui rendent des mouvements, pour vérifier que seule la persistance décide de
leur finalisation.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.migration.fixtures import build_employee_fixture_dir

EMPLOYEE_APP = "TEST_MIG_HEURES_APP"
YEAR = 2026
MONTH = 4
EMPLOYEE_ID = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "22222222-2222-4222-8222-222222222222"

_HOOK_CET = "app.modules.cet.application.payroll_hook"
_HOOK_MOD = "app.modules.modulation.application.payroll_hook"


def _needs_supabase():
    return not (
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")
    )


def _run(persister: bool) -> dict:
    from app.core.paths import payroll_engine_employee_folder, payroll_engine_root
    from app.modules.modulation.application.payroll_hook import ModulationPayrollResult
    from app.modules.payroll.documents.payslip_run_heures import (
        run_payslip_generation_heures,
    )

    engine_root: Path = payroll_engine_root()
    build_employee_fixture_dir(engine_root, EMPLOYEE_APP, YEAR, MONTH, mode="heures")
    employee_path = payroll_engine_employee_folder(EMPLOYEE_APP)

    def _inchange_avec_mouvement(*args, **kwargs):
        calendrier = args[3] if len(args) > 3 else kwargs["calendrier_etendu"]
        return calendrier, ["mvt-cet"]

    def _modulation_inchangee(*args, **kwargs):
        calendrier = args[4] if len(args) > 4 else kwargs["calendrier_etendu"]
        return calendrier, ["mvt-mod"], ModulationPayrollResult()

    appels = {}
    with patch(f"{_HOOK_MOD}.apply_modulation_hour_account_to_calendar", side_effect=_modulation_inchangee), \
         patch(f"{_HOOK_CET}.apply_cet_deposits_to_calendar", side_effect=_inchange_avec_mouvement), \
         patch(f"{_HOOK_CET}.apply_cet_withdrawals_to_calendar", side_effect=_inchange_avec_mouvement), \
         patch("app.modules.cet.infrastructure.repository.get_cet_settings_row", return_value={}), \
         patch(f"{_HOOK_MOD}.finalize_modulation_payroll_application") as fin_mod, \
         patch(f"{_HOOK_CET}.finalize_cet_payroll_application") as fin_cet, \
         patch(f"{_HOOK_CET}.apply_cet_cp_debits_for_payroll") as debits_cp:
        bulletin = run_payslip_generation_heures(
            employee_path, YEAR, MONTH, engine_root,
            company_id=COMPANY_ID, employee_id=EMPLOYEE_ID, persister=persister,
        )
        appels["finalize_modulation"] = fin_mod.call_count
        appels["finalize_cet"] = fin_cet.call_count
        appels["debits_cp"] = debits_cp.call_count
    appels["bulletin"] = bulletin
    return appels


@pytest.mark.skipif(_needs_supabase(), reason="SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
class TestBacASableHeures:
    def test_en_persistant_les_mouvements_sont_finalises(self):
        appels = _run(persister=True)

        assert appels["finalize_modulation"] == 1
        assert appels["finalize_cet"] == 2
        assert appels["debits_cp"] == 1

    def test_sans_persister_aucun_mouvement_n_est_finalise(self):
        appels = _run(persister=False)

        assert appels["finalize_modulation"] == 0
        assert appels["finalize_cet"] == 0
        assert appels["debits_cp"] == 0
        assert float(appels["bulletin"].get("salaire_brut") or 0) > 0, (
            "le bulletin est quand même calculé"
        )
