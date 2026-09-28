"""POST /api/payslips/{id}/edit : périmètre, conflit et réponse.

Audit du 28/09 : la route de modification ne résolvait pas le bulletin dans le
périmètre de la RH (permission « payslips.edit »), contrairement à /validate et
/preview.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.payslips.application.dto import PayslipConflictError
from app.modules.payslips.domain.corrections import CorrectionsBulletin
from app.modules.users.schemas.responses import CompanyAccess, User

MA_SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE_SOCIETE = "99999999-9999-9999-9999-999999999999"
BULLETIN = "33333333-3333-3333-3333-333333333333"
SALARIE = "44444444-4444-4444-4444-444444444444"

LIGNE = {
    "id": BULLETIN,
    "employee_id": SALARIE,
    "company_id": MA_SOCIETE,
    "name": "Bulletin_08-2026.pdf",
    "month": 8,
    "year": 2026,
    "url": "https://pdf/nouveau",
    "pdf_storage_path": "co/emp/bulletin.pdf",
    "payslip_data": {"net_a_payer": 1800},
    "edit_history": [{"version": 1, "edited_at": "2026-09-14T19:34:00", "edited_by": None,
                      "edited_by_name": None, "changes_summary": "x", "previous_payslip_data": {}}],
}


def _rh() -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=MA_SOCIETE, company_name="Ma société", role="rh", is_primary=True)
        ],
        active_company_id=MA_SOCIETE,
    )


def _corriger(societe_du_bulletin=MA_SOCIETE, corps=None, **edition):
    app.dependency_overrides[get_current_user] = _rh
    try:
        with (
            patch("app.modules.payslips.api.router.get_payslip_meta_for_access") as meta,
            patch("app.modules.payslips.api.router.access_control_service") as acces,
            patch("app.modules.payslips.api.router.resolve_employee_id_for_user_account", return_value=None),
            patch("app.modules.payslips.api.router.edit_payslip_for_user", **edition) as corriger,
        ):
            meta.return_value = {"company_id": societe_du_bulletin, "employee_id": SALARIE}
            acces.require_employee_access.return_value = None
            reponse = TestClient(app).post(
                f"/api/payslips/{BULLETIN}/edit",
                json=corps if corps is not None else {"corrections": {"heures_sup": {"hs25": 4, "hs50": 0}}},
            )
        return reponse, corriger, acces
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_un_bulletin_d_une_autre_societe_est_introuvable():
    reponse, corriger, _ = _corriger(AUTRE_SOCIETE)
    assert reponse.status_code == 404
    corriger.assert_not_called()


def test_la_permission_de_modifier_est_verifiee_sur_le_salarie():
    _, _, acces = _corriger(return_value={"payslip": LIGNE, "new_pdf_url": "u", "recalcule": True})
    assert acces.require_employee_access.call_args.args[2] == "payslips.edit"


def test_la_correction_arrive_au_service_en_objets_du_domaine():
    reponse, corriger, _ = _corriger(
        return_value={"payslip": LIGNE, "new_pdf_url": "u", "recalcule": True, "recalcul_erreur": None}
    )
    assert reponse.status_code == 200
    assert corriger.call_args.args[1] == CorrectionsBulletin(heures_sup=(4.0, 0.0))
    corps = reponse.json()
    assert corps["recalcule"] is True and corps["message"] == "Bulletin corrigé et recalculé."


def test_un_echec_du_recalcul_est_rendu():
    reponse, _, _ = _corriger(
        return_value={"payslip": LIGNE, "new_pdf_url": "u", "recalcule": False, "recalcul_erreur": "Barème"}
    )
    corps = reponse.json()
    assert reponse.status_code == 200
    assert corps["recalcul_erreur"] == "Barème" and corps["recalcule"] is False


def test_un_bulletin_modifie_entre_temps_rend_409():
    reponse, _, _ = _corriger(side_effect=PayslipConflictError("Le bulletin a changé"))
    assert reponse.status_code == 409


def test_un_bulletin_envoye_tel_quel_est_refuse():
    reponse, corriger, _ = _corriger(corps={"payslip_data": {"net_a_payer": 1}, "changes_summary": "x"})
    assert reponse.status_code == 422
    corriger.assert_not_called()
