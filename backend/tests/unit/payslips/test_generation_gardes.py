"""
Tests des gardes de génération (lot 3 — génération sûre).

Task 1 : calendrier manquant/incomplet → refus 422, sauf force explicite tracé.
Tout passe par le point d'entrée réel `generate_payslip` (jamais un helper privé) ;
Supabase est toujours moqué (aucune connexion réseau).
"""

from __future__ import annotations

import calendar as _calendar
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payslips.application.commands import generate_payslip
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipCalendarIncompleteError,
)

_COMPLETE_EMPLOYEE = {
    "id": "emp-1",
    "company_id": "co-1",
    "employment_status": "actif",
    "hire_date": "2020-01-15",
    "nir": "1850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Paris"},
    "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
    "salaire_de_base": {"montant": 2500},
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
}


def _schedule_complet(year: int, month: int) -> dict:
    """Ligne employee_schedules avec un mois entièrement saisi (7 h/jour prévu = réel)."""
    days = _calendar.monthrange(year, month)[1]
    return {
        "planned_calendar": {
            "calendrier_prevu": [
                {"jour": d, "type": "travail", "heures_prevues": 7.0}
                for d in range(1, days + 1)
            ]
        },
        "actual_hours": {
            "calendrier_reel": [
                {"jour": d, "heures_faites": 7.0} for d in range(1, days + 1)
            ]
        },
    }


def _schedule_avec_ecart(year: int, month: int) -> dict:
    """Mois complet mais avec un écart significatif planifié/réel (10 h faites vs 7 h)."""
    row = _schedule_complet(year, month)
    for d in row["actual_hours"]["calendrier_reel"]:
        d["heures_faites"] = 10.0
    return row


class TestGardeCalendrierIncomplet:
    """Task 1 : la génération refuse un calendrier manquant ou incomplet."""

    def _patches(self, schedule_row):
        return (
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ),
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ),
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ),
            patch(
                "app.modules.payslips.application.commands._fetch_month_schedule",
                return_value=schedule_row,
            ),
            patch(
                "app.modules.payslips.application.commands._fetch_existing_payslip",
                return_value=None,
            ),
        )

    def test_mois_sans_calendrier_refuse_et_generateur_non_appele(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        p_repo, p_reader, p_provider, p_sched, p_valide = self._patches(None)
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            with pytest.raises(PayslipCalendarIncompleteError):
                generate_payslip(cmd)

        mock_provider.generate_heures.assert_not_called()
        mock_provider.generate_forfait.assert_not_called()

    def test_mois_partiellement_saisi_refuse(self):
        """Un seul jour de travail sans réel saisi suffit à bloquer."""
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        row = _schedule_complet(2026, 5)
        row["actual_hours"]["calendrier_reel"] = row["actual_hours"][
            "calendrier_reel"
        ][:-1]  # dernier jour non saisi
        p_repo, p_reader, p_provider, p_sched, p_valide = self._patches(row)
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            with pytest.raises(PayslipCalendarIncompleteError):
                generate_payslip(cmd)

        mock_provider.generate_heures.assert_not_called()

    def test_force_genere_avec_warning_et_trace(self, caplog):
        cmd = GeneratePayslipInput(
            employee_id="emp-1",
            year=2026,
            month=5,
            force_calendrier_incomplet=True,
            requested_by="user-rh-1",
        )
        mock_result = {"status": "success", "message": "OK", "download_url": "u"}
        p_repo, p_reader, p_provider, p_sched, p_valide = self._patches(None)
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = mock_result
            # Le logger applicatif a propagate=False (app/core/logging.py:165) :
            # caplog ne le voit jamais via root, on attache son handler au
            # vrai logger du module.
            import app.modules.payslips.application.commands as commands_mod

            logger_module = commands_mod.logger
            logger_module.addHandler(caplog.handler)
            ancien_niveau = logger_module.level
            logger_module.setLevel(logging.WARNING)
            try:
                result = generate_payslip(cmd)
            finally:
                logger_module.removeHandler(caplog.handler)
                logger_module.setLevel(ancien_niveau)

        mock_provider.generate_heures.assert_called_once()
        codes = [
            w.get("code") for w in (result.warnings or []) if isinstance(w, dict)
        ]
        assert "calendrier_incomplet_force" in codes
        assert any(
            "calendrier" in m.lower() and "user-rh-1" in m
            for m in (r.getMessage() for r in caplog.records)
        )

    def test_mois_complet_genere_sans_warning(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        mock_result = {"status": "success", "message": "OK", "download_url": "u"}
        p_repo, p_reader, p_provider, p_sched, p_valide = self._patches(
            _schedule_complet(2026, 5)
        )
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = mock_result
            result = generate_payslip(cmd)

        mock_provider.generate_heures.assert_called_once()
        assert not [
            w
            for w in (result.warnings or [])
            if isinstance(w, dict) and w.get("code") == "calendrier_incomplet_force"
        ]

    def test_mois_avec_ecart_ne_bloque_pas(self):
        """Seul `a_saisir` bloque : un écart planifié/réel n'empêche pas la génération."""
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        mock_result = {"status": "success", "message": "OK", "download_url": "u"}
        p_repo, p_reader, p_provider, p_sched, p_valide = self._patches(
            _schedule_avec_ecart(2026, 5)
        )
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = mock_result
            generate_payslip(cmd)

        mock_provider.generate_heures.assert_called_once()


class TestRouteGenerate422CalendrierIncomplet:
    """Mapping HTTP : PayslipCalendarIncompleteError → 422 {code, message}."""

    def _rh_user(self):
        from app.modules.users.schemas.responses import CompanyAccess, User

        access = CompanyAccess(
            company_id="co-1", company_name="Co", role="rh", is_primary=True
        )
        return User(
            id="user-rh-1",
            email="rh@test.co",
            first_name="R",
            last_name="H",
            is_platform_admin=False,
            is_group_admin=False,
            accessible_companies=[access],
            active_company_id="co-1",
        )

    def test_route_mappe_en_422_avec_code(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.generate_payslip",
            side_effect=PayslipCalendarIncompleteError(
                "Calendrier du mois incomplet — saisissez les heures avant de générer."
            ),
        ):
            app.dependency_overrides[get_current_user] = self._rh_user
            try:
                response = client.post(
                    "/api/actions/generate-payslip",
                    json={"employee_id": "emp-1", "year": 2026, "month": 5},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "calendrier_incomplet"
        assert "alendrier" in detail["message"]

    def test_route_transmet_force_et_auteur(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.generate_payslip"
        ) as mock_gen:
            mock_gen.return_value = MagicMock(
                status="success",
                message="OK",
                download_url="u",
                payslip_id="ps-1",
                warnings=[{"code": "calendrier_incomplet_force"}],
            )
            app.dependency_overrides[get_current_user] = self._rh_user
            try:
                response = client.post(
                    "/api/actions/generate-payslip",
                    json={
                        "employee_id": "emp-1",
                        "year": 2026,
                        "month": 5,
                        "force_calendrier_incomplet": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        cmd = mock_gen.call_args[0][0]
        assert cmd.force_calendrier_incomplet is True
        assert cmd.requested_by == "user-rh-1"
        assert response.json()["warnings"] == [
            {"code": "calendrier_incomplet_force"}
        ]


class TestGardeBulletinValide:
    """Task 2 : un bulletin validé n'est plus écrasable en silence."""

    def _patches(self, existing_payslip):
        return (
            patch("app.modules.payslips.application.commands._employee_repository"),
            patch("app.modules.payslips.application.commands.employee_statut_reader"),
            patch("app.modules.payslips.application.commands.payslip_generator_provider"),
            patch(
                "app.modules.payslips.application.commands._calendar_row_status",
                return_value="saisi",
            ),
            patch(
                "app.modules.payslips.application.commands._fetch_existing_payslip",
                return_value=existing_payslip,
            ),
        )

    def test_regenerer_un_bulletin_valide_sans_force_est_refuse(self):
        from app.modules.payslips.application.commands import generate_payslip
        from app.modules.payslips.application.dto import (
            GeneratePayslipInput,
            PayslipValidatedError,
        )

        existing = {"id": "p-1", "status": "valide", "payslip_data": {}, "url": "u"}
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        p_repo, p_reader, p_provider, p_cal, p_fetch = self._patches(existing)
        with p_repo as mock_repo, p_reader, p_provider as mock_provider, p_cal, p_fetch:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            with pytest.raises(PayslipValidatedError):
                generate_payslip(cmd)
        mock_provider.generate_heures.assert_not_called()
        mock_provider.generate_forfait.assert_not_called()

    def test_force_archive_avant_generation_puis_remet_en_brouillon(self):
        from app.modules.payslips.application import commands as mod
        from app.modules.payslips.application.dto import GeneratePayslipInput

        existing = {
            "id": "p-1",
            "status": "valide",
            "payslip_data": {"net_a_payer": 1000, "alerts_status": {"R01": "acquittee"}},
            "url": "ancien.pdf",
            "edit_history": [],
        }
        ordre = []
        cmd = GeneratePayslipInput(
            employee_id="emp-1", year=2026, month=5,
            regenerer_bulletin_valide=True,
            requested_by="user-rh-1", requested_by_name="RH Test",
        )
        p_repo, p_reader, p_provider, p_cal, p_fetch = self._patches(existing)
        with (
            p_repo as mock_repo,
            p_reader as mock_reader,
            p_provider as mock_provider,
            p_cal,
            p_fetch,
            patch.object(mod, "_archive_before_regeneration") as mock_archive,
            patch.object(mod, "_reset_payslip_flags_after_regeneration") as mock_reset,
        ):
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_archive.side_effect = lambda *a, **k: ordre.append("archive")
            mock_provider.generate_heures.side_effect = lambda **k: (
                ordre.append("generation") or {"status": "success", "message": "OK", "download_url": "u"}
            )
            mock_reset.side_effect = lambda *a, **k: ordre.append("reset")
            result = mod.generate_payslip(cmd)

        assert ordre == ["archive", "generation", "reset"]
        codes = [w.get("code") for w in (result.warnings or []) if isinstance(w, dict)]
        assert "bulletin_valide_regenere" in codes

    def test_un_brouillon_existant_ne_declenche_pas_la_garde(self):
        from app.modules.payslips.application.commands import generate_payslip
        from app.modules.payslips.application.dto import GeneratePayslipInput

        existing = {"id": "p-1", "status": "brouillon", "payslip_data": {}, "url": "u"}
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        p_repo, p_reader, p_provider, p_cal, p_fetch = self._patches(existing)
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_cal, p_fetch:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = {
                "status": "success", "message": "OK", "download_url": "u",
            }
            result = generate_payslip(cmd)
        assert result.status == "success"
