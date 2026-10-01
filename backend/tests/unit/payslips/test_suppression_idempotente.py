"""Supprimer un bulletin déjà supprimé répond 204, « déjà supprimé » — jamais 500.

Le 29/09 à 19 h 11, une suppression a répondu 500 (« 0 ligne ») : le bulletin
avait déjà été supprimé depuis un autre écran. La lecture du bulletin passait
par `.single()`, qui lève sur une ligne absente, et la route en faisait une 500.

Une 204 n'a pas de corps : « déjà supprimé » passe par l'en-tête
`X-Deja-Supprime`. Un bulletin d'une autre société répond exactement comme un
bulletin absent, pour que la réponse ne révèle pas qu'il existe. La garde
d'accès (société active, rôle) passe avant toute lecture et n'a pas changé.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.payslips.application import commands
from app.modules.payslips.application.dto import PayslipBadRequestError, PayslipValidatedError
from app.modules.payslips.infrastructure import queries
from app.modules.payslips.infrastructure import repository as depot
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

MA_SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE_SOCIETE = "99999999-9999-9999-9999-999999999999"
BULLETIN = "33333333-3333-3333-3333-333333333333"
SALARIE = "44444444-4444-4444-4444-444444444444"
EN_TETE = "X-Deja-Supprime"
ORIGINE_ECRAN = "http://localhost:5173"

_SERVICE = "app.modules.access_control.application.service.AccessControlService"


def _gestionnaire(role: str = "rh", *, societe_active: str | None = MA_SOCIETE) -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="paie@entreprise.test",
        first_name="Gestionnaire",
        last_name="Paie",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=MA_SOCIETE, company_name="Ma société", role=role, is_primary=True),
        ],
        active_company_id=societe_active,
    )


def _meta(societe: str = MA_SOCIETE) -> dict:
    return {"company_id": societe, "employee_id": SALARIE, "year": 2026, "month": 9}


def _supprimer(
    meta: dict | None,
    *,
    utilisateur: User | None = None,
    supprime: bool = True,
    erreur: Exception | None = None,
    hors_perimetre: bool = False,
):
    """DELETE avec la vraie garde d'accès : seules ses lectures en base sont doublées."""
    app.dependency_overrides[get_current_user] = lambda: utilisateur or _gestionnaire()
    try:
        with (
            patch("app.modules.payslips.api.router.get_payslip_meta_for_access", return_value=meta),
            patch(
                "app.modules.payslips.api.router.delete_payslip",
                return_value=supprime,
                side_effect=erreur,
            ) as suppr,
            patch(f"{_SERVICE}.check_user_has_permission", return_value=False),
            patch(
                f"{_SERVICE}.assert_employee_in_company",
                side_effect=HTTPException(404, "Ressource introuvable") if hors_perimetre else None,
            ) as perimetre,
        ):
            reponse = TestClient(app).delete(f"/api/payslips/{BULLETIN}", headers={"Origin": ORIGINE_ECRAN})
        return reponse, suppr, perimetre
    finally:
        app.dependency_overrides.pop(get_current_user, None)


class TestRouteIdempotente:
    def test_bulletin_deja_supprime_repond_204_et_le_dit(self):
        reponse, suppr, _ = _supprimer(None)

        assert reponse.status_code == 204
        assert reponse.headers.get(EN_TETE) == "true"
        assert reponse.content == b""
        suppr.assert_not_called()

    def test_bulletin_supprime_entre_la_lecture_et_la_suppression(self):
        reponse, suppr, _ = _supprimer(_meta(), supprime=False)

        assert reponse.status_code == 204
        assert reponse.headers.get(EN_TETE) == "true"
        suppr.assert_called_once_with(BULLETIN)

    def test_une_vraie_suppression_ne_dit_pas_deja_supprime(self):
        reponse, suppr, _ = _supprimer(_meta(), supprime=True)

        assert reponse.status_code == 204
        assert EN_TETE not in reponse.headers
        suppr.assert_called_once_with(BULLETIN)

    def test_l_ecran_peut_lire_l_en_tete(self):
        """Écran et API sont sur deux origines : sans `expose_headers`, le
        navigateur masque l'en-tête et l'écran ne saurait jamais « déjà supprimé »."""
        reponse, _, _ = _supprimer(None)

        exposes = reponse.headers.get("access-control-expose-headers", "")
        assert EN_TETE.lower() in exposes.lower()


class TestAutreSocieteIndiscernable:
    def test_meme_reponse_qu_un_bulletin_absent_et_rien_n_est_supprime(self):
        autre, suppr_autre, perimetre_autre = _supprimer(_meta(AUTRE_SOCIETE))
        absent, _, _ = _supprimer(None)

        assert (autre.status_code, autre.headers.get(EN_TETE), autre.content) == (
            absent.status_code,
            absent.headers.get(EN_TETE),
            absent.content,
        )
        suppr_autre.assert_not_called()
        # Le salarié de l'autre société n'est même pas cherché.
        perimetre_autre.assert_not_called()


class TestGardesInchangees:
    @pytest.mark.parametrize("meta", [None, _meta(), _meta(AUTRE_SOCIETE)], ids=["absent", "ma-societe", "autre-societe"])
    def test_sans_droit_de_suppression_403_quel_que_soit_le_bulletin(self, meta):
        """Avant toute lecture : un collaborateur n'apprend rien, pas même « déjà supprimé »."""
        reponse, suppr, _ = _supprimer(meta, utilisateur=_gestionnaire("collaborateur"))

        assert reponse.status_code == 403
        assert EN_TETE not in reponse.headers
        suppr.assert_not_called()

    def test_sans_societe_active_400(self):
        reponse, suppr, _ = _supprimer(None, utilisateur=_gestionnaire(societe_active=None))

        assert reponse.status_code == 400
        suppr.assert_not_called()

    def test_salarie_hors_perimetre_dans_ma_societe_reste_404(self):
        """Le bulletin existe : répondre « déjà supprimé » serait faux."""
        reponse, suppr, _ = _supprimer(_meta(), hors_perimetre=True)

        assert reponse.status_code == 404
        assert EN_TETE not in reponse.headers
        suppr.assert_not_called()

    def test_bulletin_valide_toujours_refuse(self):
        reponse, _, _ = _supprimer(_meta(), erreur=PayslipValidatedError("Ce bulletin est validé."))

        assert reponse.status_code == 409
        assert EN_TETE not in reponse.headers

    def test_bulletin_importe_toujours_refuse(self):
        reponse, _, _ = _supprimer(_meta(), erreur=PayslipBadRequestError("Bulletin repris de l'ancien logiciel."))

        assert reponse.status_code == 400
        assert EN_TETE not in reponse.headers


class TestCommande:
    def test_bulletin_absent_rend_faux_sans_rien_supprimer(self):
        with (
            patch.object(commands, "_fetch_payslip_status", return_value=None),
            patch("app.modules.payslips.infrastructure.repository.payslip_repository") as repo,
        ):
            assert commands.delete_payslip("ps-parti") is False
        repo.delete.assert_not_called()

    def test_rend_ce_que_dit_le_depot(self):
        with (
            patch.object(commands, "_fetch_payslip_status", return_value={"id": "ps-1", "status": "brouillon"}),
            patch("app.modules.payslips.infrastructure.repository.payslip_repository") as repo,
        ):
            repo.delete.return_value = False
            assert commands.delete_payslip("ps-1") is False
            repo.delete.return_value = True
            assert commands.delete_payslip("ps-1") is True


def _supabase_sans_ligne() -> MagicMock:
    """Client dont toute lecture `maybe_single` ne trouve rien ; `single` lèverait."""
    client = MagicMock()
    requete = client.table.return_value.select.return_value.eq.return_value
    requete.maybe_single.return_value.execute.return_value = None
    requete.single.return_value.execute.side_effect = AssertionError(
        "`.single()` lève sur une ligne absente (PGRST116)"
    )
    return client


class TestLecturesSansSingle:
    def test_meta_d_un_bulletin_absent_vaut_none(self, monkeypatch):
        monkeypatch.setattr(queries, "supabase", _supabase_sans_ligne())

        assert queries.get_payslip_meta(BULLETIN) is None

    def test_meta_d_un_bulletin_present(self, monkeypatch):
        client = _supabase_sans_ligne()
        requete = client.table.return_value.select.return_value.eq.return_value
        requete.maybe_single.return_value.execute.return_value = SimpleNamespace(data=_meta())
        monkeypatch.setattr(queries, "supabase", client)

        assert queries.get_payslip_meta(BULLETIN) == _meta()

    def test_le_depot_ne_supprime_rien_d_absent(self, monkeypatch):
        client = _supabase_sans_ligne()
        monkeypatch.setattr(depot, "supabase", client)

        assert depot.PayslipRepository().delete(BULLETIN) is False
        client.table.return_value.delete.assert_not_called()
        client.storage.from_.assert_not_called()

    def test_le_depot_supprime_ligne_et_pdf(self, monkeypatch):
        client = _supabase_sans_ligne()
        requete = client.table.return_value.select.return_value.eq.return_value
        requete.maybe_single.return_value.execute.return_value = SimpleNamespace(
            data={"pdf_storage_path": "co/emp/bulletins/b.pdf", "employee_id": None}
        )
        monkeypatch.setattr(depot, "supabase", client)

        assert depot.PayslipRepository().delete(BULLETIN) is True
        client.table.return_value.delete.return_value.eq.assert_called_once_with("id", BULLETIN)
        client.storage.from_.return_value.remove.assert_called_once_with(["co/emp/bulletins/b.pdf"])
