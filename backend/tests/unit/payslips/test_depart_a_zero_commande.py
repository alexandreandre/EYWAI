"""[B12] La sortie « Générer quand même, en partant de cumuls à zéro », côté commande.

Le choix part de l'écran (`partir_de_cumuls_a_zero`), est daté et signé (qui,
quand), et passe au générateur. Un bulletin déjà généré ainsi garde son choix à
chaque recalcul (correction, régénération, recalcul en chaîne) : la question n'est
pas reposée, la trace d'origine reste. Sans choix ni trace, rien ne passe.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payslips.application import commands as mod
from app.modules.payslips.application.dto import GeneratePayslipInput
from tests.unit.payslips.test_generation_gardes import _COMPLETE_EMPLOYEE, _periode_vide

pytestmark = pytest.mark.unit

TRACE_D_ORIGINE = {"par": "RH Essai", "par_id": "user-rh-1", "le": "2026-10-12T18:05:00+00:00"}


def _generer(cmd: GeneratePayslipInput, existant: dict | None) -> MagicMock:
    with (
        patch.object(mod, "_employee_repository") as repo,
        patch.object(mod, "employee_statut_reader") as lecteur,
        patch.object(mod, "payslip_generator_provider") as fournisseur,
        patch.object(mod, "_periode_a_saisir", return_value=_periode_vide()),
        patch.object(mod, "_fetch_existing_payslip", return_value=existant),
        patch.object(mod, "_archive_before_regeneration"),
        patch.object(mod, "mois_suivant_a_recalculer", return_value=None),
    ):
        repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
        lecteur.get_employee_statut.return_value = "Non-Cadre"
        fournisseur.generate_heures.return_value = {
            "status": "success", "message": "OK", "download_url": "u",
        }
        mod.generate_payslip(cmd)
    return fournisseur


def test_le_choix_de_l_ecran_est_signe_et_date_puis_passe_au_generateur():
    cmd = GeneratePayslipInput(
        employee_id="emp-1", year=2026, month=10, partir_de_cumuls_a_zero=True,
        requested_by="user-rh-2", requested_by_name="RH Seconde",
    )
    fournisseur = _generer(cmd, None)
    trace = fournisseur.generate_heures.call_args.kwargs["depart_a_zero"]
    assert trace["par"] == "RH Seconde" and trace["par_id"] == "user-rh-2"
    assert datetime.fromisoformat(trace["le"]).tzinfo is not None


def test_un_bulletin_deja_parti_de_zero_garde_son_choix_au_recalcul():
    existant = {
        "id": "p-1", "status": "brouillon", "url": "u",
        "payslip_data": {"depart_a_zero_force": TRACE_D_ORIGINE},
    }
    cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=10)
    fournisseur = _generer(cmd, existant)
    assert fournisseur.generate_heures.call_args.kwargs["depart_a_zero"] == TRACE_D_ORIGINE


def test_sans_choix_ni_trace_le_generateur_ne_recoit_rien():
    existant = {"id": "p-1", "status": "brouillon", "url": "u", "payslip_data": {}}
    cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=10)
    fournisseur = _generer(cmd, existant)
    assert "depart_a_zero" not in fournisseur.generate_heures.call_args.kwargs


def _rh_user():
    from app.modules.users.schemas.responses import CompanyAccess, User

    access = CompanyAccess(company_id="co-1", company_name="Co", role="rh", is_primary=True)
    return User(
        id="user-rh-1", email="rh@test.co", first_name="RH", last_name="Essai",
        is_platform_admin=False, is_group_admin=False,
        accessible_companies=[access], active_company_id="co-1",
    )


def test_la_route_transmet_le_choix_et_son_auteur():
    from app.core.security import get_current_user

    client = TestClient(app)
    with patch("app.modules.payslips.api.router.generate_payslip") as gen, patch(
        "app.modules.payslips.api.router.access_control_service.require_employee_access"
    ):
        gen.return_value = MagicMock(
            status="success", message="OK", download_url="u", payslip_id="ps-1", warnings=[],
        )
        app.dependency_overrides[get_current_user] = _rh_user
        try:
            reponse = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-1", "year": 2026, "month": 10, "partir_de_cumuls_a_zero": True},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
    assert reponse.status_code == 200
    cmd = gen.call_args[0][0]
    assert cmd.partir_de_cumuls_a_zero is True
    assert cmd.requested_by_name == "RH Essai"
