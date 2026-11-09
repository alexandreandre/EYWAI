"""
Les routes ouvertes entre sociétés trouvées par le parcours du 09/11/2026 (R-620).

Chaque test joue l'appel d'une RH de la société A qui vise la société B.
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
SALARIE_DE_B = "cccccccc-3333-3333-3333-333333333333"


def _rh_de_a(role: str = "rh") -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE_A,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE_A,
    )


class TestReposCompensateur:
    def test_refuse_une_autre_societe(self):
        from app.modules.repos_compensateur.api.router import _resolve_company_id

        with pytest.raises(HTTPException) as exc:
            _resolve_company_id(SOCIETE_B, _rh_de_a())
        assert exc.value.status_code == 403

    def test_refuse_un_salarie_sans_droit_rh(self):
        from app.modules.repos_compensateur.api.router import _resolve_company_id

        with pytest.raises(HTTPException) as exc:
            _resolve_company_id(None, _rh_de_a(role="collaborateur"))
        assert exc.value.status_code == 403

    def test_garde_la_societe_active_d_une_rh(self):
        from app.modules.repos_compensateur.api.router import _resolve_company_id

        assert _resolve_company_id(None, _rh_de_a()) == SOCIETE_A


class TestReglagesAbsences:
    def test_refuse_une_autre_societe(self):
        from app.modules.absences.api.router import _societe_lisible

        with pytest.raises(HTTPException) as exc:
            _societe_lisible(SOCIETE_B, _rh_de_a())
        assert exc.value.status_code == 403

    def test_retombe_sur_la_societe_active(self):
        from app.modules.absences.api.router import _societe_lisible

        assert _societe_lisible(None, _rh_de_a()) == SOCIETE_A

    def test_repasser_en_attente_une_demande_d_ailleurs_est_refuse(self):
        from app.modules.absences.api import router as absences
        from app.modules.absences.schemas.requests import AbsenceRequestStatusUpdate

        with (
            patch.object(
                absences.absence_router,
                "get_absence_by_id",
                return_value={"company_id": SOCIETE_B, "status": "validated"},
            ),
            patch.object(absences.commands, "update_absence_request_status") as ecrit,
        ):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(
                    absences.update_absence_request_status(
                        "demande-b",
                        MagicMock(),
                        AbsenceRequestStatusUpdate(status="pending"),
                        _rh_de_a(),
                    )
                )
        assert exc.value.status_code == 403
        ecrit.assert_not_called()


class TestTicketsSupport:
    def test_l_en_tete_d_une_autre_societe_ne_lit_pas_ses_tickets(self):
        from app.modules.support.api import router as support

        with patch.object(support, "queries") as queries:
            queries.get_tickets_for_user.return_value = []
            support.get_tickets(
                company_id=None,
                urgency=None,
                status=None,
                module=None,
                date_from=None,
                date_to=None,
                user_id=None,
                current_user=_rh_de_a(),
                x_active_company=SOCIETE_B,
            )
        queries.get_tickets_for_company.assert_not_called()
        queries.get_tickets_for_user.assert_called_once()

    def test_la_societe_de_la_rh_reste_lisible(self):
        from app.modules.support.api import router as support

        with patch.object(support, "queries") as queries:
            queries.get_tickets_for_company.return_value = []
            support.get_tickets(
                company_id=None,
                urgency=None,
                status=None,
                module=None,
                date_from=None,
                date_to=None,
                user_id=None,
                current_user=_rh_de_a(),
                x_active_company=SOCIETE_A,
            )
        queries.get_tickets_for_company.assert_called_once()

    def test_pas_de_ticket_au_nom_d_une_autre_societe(self):
        from app.modules.support.api import router as support

        with patch.object(support, "commands") as commands:
            with pytest.raises(HTTPException) as exc:
                support.post_ticket(MagicMock(), _rh_de_a(), SOCIETE_B)
        assert exc.value.status_code == 403
        commands.create_ticket.assert_not_called()


class TestImportBadgeuse:
    def test_le_corps_ne_vise_pas_une_autre_societe(self):
        from app.modules.schedules.api import router as schedules

        requete = SimpleNamespace(
            company_id=SOCIETE_B,
            employee_ids=[SALARIE_DE_B],
            year=2026,
            month=10,
            recalculate_payroll=False,
        )
        with patch.object(schedules, "import_actual_hours_from_badgeuse_bulk") as importe:
            with pytest.raises(HTTPException) as exc:
                schedules.import_badgeuse_actual_hours_bulk(requete, _rh_de_a())
        assert exc.value.status_code == 403
        importe.assert_not_called()


class TestPointages:
    @staticmethod
    def _table():
        table = MagicMock()
        for methode in ("update", "delete", "eq"):
            getattr(table, methode).return_value = table
        return table

    def test_supprimer_est_borne_a_la_societe(self):
        from app.modules.badgeuse.infrastructure import repository as depot

        table = self._table()
        table.execute.return_value = SimpleNamespace(data=[])
        with patch.object(depot, "supabase") as supabase:
            supabase.table.return_value = table
            with pytest.raises(LookupError):
                depot.TimeEntryRepository().delete_entry("evt", company_id=SOCIETE_A)
        table.eq.assert_any_call("company_id", SOCIETE_A)

    def test_la_route_repond_404_hors_societe(self):
        from app.modules.badgeuse.api import router as badgeuse

        with (
            patch.object(badgeuse, "_require_badgeuse_rh_access"),
            patch.object(
                badgeuse.badgeuse_service,
                "delete_event_for_employee_day",
                side_effect=LookupError("absent"),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                badgeuse.delete_event("evt", SOCIETE_A, _rh_de_a())
        assert exc.value.status_code == 404

    def test_modifier_passe_la_societe_au_depot(self):
        from app.modules.badgeuse.application import punch_service

        with (
            patch.object(punch_service, "deps") as deps,
            patch.object(punch_service, "get_day_detail_for_employee"),
        ):
            punch_service.update_event_for_employee_day(
                event_id="evt",
                timestamp=None,
                event_type=None,
                current_user=_rh_de_a(),
                company_id=SOCIETE_A,
            )
        assert deps.time_entry_repository.update_entry.call_args.kwargs["company_id"] == SOCIETE_A


class TestCet:
    def test_le_resume_refuse_un_salarie_d_ailleurs(self):
        from app.modules.cet.api import router as cet

        with (
            patch.object(cet, "_require_rh"),
            patch.object(
                cet.access_control_service,
                "assert_employee_in_company",
                side_effect=HTTPException(status_code=404, detail="Ressource introuvable"),
            ),
            patch.object(cet, "cet_service") as service,
        ):
            with pytest.raises(HTTPException) as exc:
                cet.get_employee_cet_summary(SALARIE_DE_B, None, None, None, _rh_de_a())
        assert exc.value.status_code == 404
        service.build_employee_summary.assert_not_called()


class TestCse:
    def test_reunion_d_une_autre_societe_introuvable(self):
        from app.modules.cse.infrastructure.cse_service_impl import (
            _refuser_reunion_hors_societe,
        )

        with pytest.raises(HTTPException) as exc:
            _refuser_reunion_hors_societe(SOCIETE_B, SOCIETE_A)
        assert exc.value.status_code == 404

    def test_reunion_de_la_societe_active_acceptee(self):
        from app.modules.cse.infrastructure.cse_service_impl import (
            _refuser_reunion_hors_societe,
        )

        _refuser_reunion_hors_societe(SOCIETE_A, SOCIETE_A)


class TestModelesDeRole:
    def test_la_liste_refuse_une_autre_societe(self):
        acces = importlib.import_module("app.modules.access_control.api.router")

        with patch.object(acces, "queries") as queries:
            with pytest.raises(HTTPException) as exc:
                acces.get_role_templates(SOCIETE_B, None, True, _rh_de_a())
        assert exc.value.status_code == 403
        queries.get_role_templates.assert_not_called()

    def test_le_detail_d_un_modele_d_ailleurs_est_introuvable(self):
        from app.modules.access_control.application import queries

        with patch.object(queries, "role_template_repository") as depot:
            depot.get_role_template_by_id.return_value = {"company_id": SOCIETE_B}
            with pytest.raises(HTTPException) as exc:
                queries.get_role_template_by_id(_rh_de_a(), "modele-b")
        assert exc.value.status_code == 404
