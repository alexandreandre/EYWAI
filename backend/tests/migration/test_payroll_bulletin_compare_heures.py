"""
Génération bulletin HEURES via app.modules.payroll (source de vérité).

Vérifie que l'app produit un bulletin valide avec des montants cohérents.
Pas d'appel au script legacy (évite la dépendance à l'écriture PDF sur disque).
Nécessite Supabase (barèmes) ; sinon les tests sont ignorés.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.migration.fixtures import build_employee_fixture_dir

EMPLOYEE_APP = "TEST_MIG_HEURES_APP"
YEAR = 2026
MONTH = 4


def _engine_root() -> Path:
    from app.core.paths import payroll_engine_root

    return payroll_engine_root()


def _employee_path() -> Path:
    from app.core.paths import payroll_engine_employee_folder

    return payroll_engine_employee_folder(EMPLOYEE_APP)


def _needs_supabase():
    return not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


@pytest.mark.skipif(_needs_supabase(), reason="SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
class TestPayrollBulletinCompareHeures:
    """Compare sortie app vs legacy pour un bulletin heures (avril 2026)."""

    def test_run_app_heures_produces_bulletin(self):
        """L'app produit un bulletin avec les champs attendus."""
        engine_root = _engine_root()
        build_employee_fixture_dir(engine_root, EMPLOYEE_APP, YEAR, MONTH, mode="heures")
        employee_path = _employee_path()

        from app.modules.payroll.documents.payslip_run_heures import run_payslip_generation_heures

        bulletin = run_payslip_generation_heures(employee_path, YEAR, MONTH, engine_root)

        assert isinstance(bulletin, dict)
        assert "salaire_brut" in bulletin
        assert "net_a_payer" in bulletin
        assert "synthese_net" in bulletin

    def test_app_heures_key_figures_coherent(self):
        """L'app produit un bulletin heures avec des montants cohérents (brut > 0, net < brut)."""
        engine_root = _engine_root()
        build_employee_fixture_dir(engine_root, EMPLOYEE_APP, YEAR, MONTH, mode="heures")
        employee_path = _employee_path()

        from app.modules.payroll.documents.payslip_run_heures import run_payslip_generation_heures

        bulletin = run_payslip_generation_heures(employee_path, YEAR, MONTH, engine_root)

        brut = float(bulletin.get("salaire_brut", 0) or 0)
        net_a_payer = float(bulletin.get("net_a_payer", 0) or 0)
        net_imposable = float((bulletin.get("synthese_net") or {}).get("net_imposable", 0) or 0)

        assert brut > 0, "Salaire brut attendu > 0"
        assert net_a_payer > 0, "Net à payer attendu > 0"
        assert net_a_payer < brut, "Net à payer doit être inférieur au brut"
        assert net_imposable >= net_a_payer, "Net imposable cohérent avec net à payer"
