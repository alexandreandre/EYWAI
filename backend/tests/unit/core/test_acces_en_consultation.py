"""Accès en consultation : le compte voit tout et le serveur lui refuse toute modification."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import security
from app.core.consultation import MESSAGE_CONSULTATION, envoi_permis_en_consultation
from app.modules.exports.application import commands as exports_commands
from app.modules.users.schemas.responses import CompanyAccess, User


class _Requete:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows, count=len(self._rows))


def _acces(company_id, *, lecture_seule):
    return {
        "company_id": company_id,
        "role": "rh",
        "is_primary": company_id == "co-a",
        "lecture_seule": lecture_seule,
        "companies": {"id": company_id, "company_name": company_id, "siret": None,
                      "logo_url": None, "logo_scale": 1.0, "group_id": None,
                      "company_groups": None},
    }


def _client(lecture_seule):
    client = MagicMock()
    tables = {
        "profiles": [{"first_name": "A", "last_name": "B", "must_change_password": False}],
        "super_admins": [],
        "user_company_accesses": [_acces("co-a", lecture_seule=lecture_seule),
                                  _acces("co-b", lecture_seule=lecture_seule)],
    }
    client.table.side_effect = lambda name: _Requete(tables[name])
    return client


def _app():
    app = FastAPI()

    @app.get("/api/payslips/x")
    def lire(u: User = Depends(security.get_current_user)):
        return {"consultation": u.consultation}

    @app.post("/api/payslips/x/validate")
    def valider(u: User = Depends(security.get_current_user)):
        return {"ok": True}

    @app.post("/api/exports/preview")
    def apercu(u: User = Depends(security.get_current_user)):
        return {"ok": True}

    @app.post("/api/payroll-variables/generate")
    def variables(u: User = Depends(security.get_current_user)):
        return {"ok": True}

    return app


@pytest.fixture
def appeler():
    def _appeler(lecture_seule, methode, chemin):
        auth_user = SimpleNamespace(id="u-1", email="u@example.test")
        with patch.object(security, "get_supabase_admin_client", return_value=_client(lecture_seule)), \
             patch.object(security, "supabase") as sb, \
             patch.object(security, "execute_with_retry", side_effect=lambda fn: fn()):
            sb.auth.get_user.return_value = SimpleNamespace(user=auth_user)
            return TestClient(_app()).request(
                methode, chemin, headers={"Authorization": "Bearer jwt"}
            )
    return _appeler


def test_un_compte_en_consultation_lit(appeler):
    r = appeler(True, "GET", "/api/payslips/x")
    assert r.status_code == 200
    assert r.json() == {"consultation": True}


def test_un_compte_en_consultation_ne_modifie_rien(appeler):
    r = appeler(True, "POST", "/api/payslips/x/validate")
    assert r.status_code == 403
    assert r.json()["detail"] == MESSAGE_CONSULTATION


def test_un_compte_en_consultation_voit_les_apercus_d_export(appeler):
    assert appeler(True, "POST", "/api/exports/preview").status_code == 200


def test_variables_du_mois_a_blanc_seulement(appeler):
    assert appeler(True, "POST", "/api/payroll-variables/generate?dry_run=true").status_code == 200
    assert appeler(True, "POST", "/api/payroll-variables/generate").status_code == 403


def test_un_compte_rh_ordinaire_n_est_pas_touche(appeler):
    assert appeler(False, "POST", "/api/payslips/x/validate").status_code == 200
    assert appeler(False, "GET", "/api/payslips/x").json() == {"consultation": False}


@pytest.mark.parametrize(
    "methode,chemin,parametres,permis",
    [
        ("GET", "/api/payslips/abc", {}, True),
        ("HEAD", "/api/payslips/abc", {}, True),
        ("POST", "/api/auth/change-password", {}, True),
        ("POST", "/api/auth/logout", {}, True),
        ("PUT", "/api/notifications/read-all", {}, True),
        ("PUT", "/api/notifications/123/read", {}, True),
        ("PATCH", "/api/users/set-primary-company", {}, True),
        ("POST", "/api/exports/generate", {}, True),
        ("POST", "/api/exports/generate/", {}, True),
        ("POST", "/api/simulation/abc/compare", {}, True),
        ("POST", "/api/simulation/reverse-calculation", {}, True),
        ("POST", "/api/payroll-variables/generate", {"dry_run": "true"}, True),
        ("POST", "/api/payroll-variables/generate", {"dry_run": "false"}, False),
        ("POST", "/api/simulation/create-payslip", {}, False),
        ("POST", "/api/exports/dispatch", {}, False),
        ("POST", "/api/exports/dsn-hors-martine", {}, False),
        ("POST", "/api/payslips/abc/regenerate", {}, False),
        ("PUT", "/api/payroll-variables/period", {}, False),
        ("DELETE", "/api/exports/scheduled/1", {}, False),
        ("PATCH", "/api/users/update-access/u/c", {}, False),
        ("POST", "/api/users/grant-access", {}, False),
        ("POST", "/api/notifications/123/read", {}, False),
    ],
)
def test_envois_permis(methode, chemin, parametres, permis):
    assert envoi_permis_en_consultation(methode, chemin, parametres) is permis


def _user(*lectures, admin=False):
    return User(
        id="u",
        is_platform_admin=admin,
        accessible_companies=[
            CompanyAccess(company_id=f"c{i}", company_name="x", role="rh",
                          is_primary=i == 0, lecture_seule=ls)
            for i, ls in enumerate(lectures)
        ],
        active_company_id="c0",
    )


def test_un_seul_acces_en_consultation_suffit():
    """Un company_id passé en paramètre pourrait sinon viser l'autre société."""
    assert _user(False, True).consultation is True
    assert _user(False, False).consultation is False
    assert _user(True, admin=True).consultation is False


def test_un_export_en_consultation_ne_laisse_aucune_trace():
    with patch.object(exports_commands.repository, "insert_export_record", return_value="id-1") as ins:
        with exports_commands.exports_sans_trace():
            assert exports_commands.record_export_history({}) == ""
        ins.assert_not_called()
        assert exports_commands.record_export_history({}) == "id-1"
        ins.assert_called_once()


def test_export_en_consultation_dsn_d_essai_sans_trace():
    from app.modules.exports.api import router as exports_router
    from app.modules.exports.schemas.requests import ExportGenerateRequest

    vu = {}

    def faux(company_id, user_id, req):
        vu["essai"] = (req.filters or {}).get("essai")
        vu["sans_trace"] = exports_commands._sans_trace.get()
        return {"ok": True}

    req = ExportGenerateRequest(export_type="dsn_mensuelle", period="2026-10")
    with patch.object(exports_router.export_service, "generate_export", side_effect=faux), \
         patch.object(exports_router, "_require_exports_company_access"):
        exports_router.generate_export(req, _user(True), "c0")
    assert vu == {"essai": True, "sans_trace": True}

    req = ExportGenerateRequest(export_type="dsn_mensuelle", period="2026-10")
    with patch.object(exports_router.export_service, "generate_export", side_effect=faux), \
         patch.object(exports_router, "_require_exports_company_access"):
        exports_router.generate_export(req, _user(False), "c0")
    assert vu == {"essai": None, "sans_trace": False}


def test_un_export_ne_vise_que_la_societe_active():
    from fastapi import HTTPException

    from app.modules.exports.api import router as exports_router
    from app.modules.exports.schemas.requests import ExportGenerateRequest

    req = ExportGenerateRequest(export_type="journal_paie", period="2026-10", company_id="autre")
    with patch.object(exports_router.export_service, "generate_export") as gen, \
         patch.object(exports_router, "_require_exports_company_access"):
        with pytest.raises(HTTPException) as exc:
            exports_router.generate_export(req, _user(False), "c0")
    assert exc.value.status_code == 403
    gen.assert_not_called()
