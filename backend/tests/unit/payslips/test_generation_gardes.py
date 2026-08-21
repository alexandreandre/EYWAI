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


class TestNotificationALaValidation:
    """Task 3 : le salarié est notifié à la VALIDATION, une seule fois."""

    def test_la_generation_ne_notifie_plus(self):
        from app.modules.payslips.application import commands as mod
        from app.modules.payslips.application.dto import GeneratePayslipInput

        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        with (
            patch.object(mod, "_employee_repository") as mock_repo,
            patch.object(mod, "employee_statut_reader") as mock_reader,
            patch.object(mod, "payslip_generator_provider") as mock_provider,
            patch.object(mod, "_calendar_row_status", return_value="saisi"),
            patch.object(mod, "_fetch_existing_payslip", return_value=None),
            patch.object(mod, "_notify_payslip_available") as mock_notify,
        ):
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = {
                "status": "success", "message": "OK", "download_url": "u",
            }
            mod.generate_payslip(cmd)
        mock_notify.assert_not_called()

    def _valider(self, payslip_data, notifications):
        """Passe un bulletin dans le VRAI validate_payslip_for_user, I/O moquée."""
        from unittest.mock import MagicMock

        from app.modules.payslips.application import comparison_service as svc

        detail = {
            "id": "p-1",
            "employee_id": "emp-1",
            "company_id": "comp-1",
            "year": 2026,
            "month": 5,
            "status": "brouillon",
            "payslip_data": payslip_data,
        }
        resultat_comparaison = MagicMock()
        resultat_comparaison.alerts = []
        with (
            patch.object(svc, "payslip_meta_reader") as mock_meta,
            patch.object(svc, "_ensure_edit_meta"),
            patch.object(svc, "get_payslip_details", return_value=detail),
            patch.object(svc, "fetch_previous_validated_payslip", return_value=None),
            patch.object(svc, "fetch_employee_statut", return_value="Non-Cadre"),
            patch.object(svc, "fetch_recent_nets_asc_for_r10", return_value=[]),
            patch.object(svc, "compute_comparison", return_value=resultat_comparaison),
            patch.object(svc, "mark_payslip_validated") as mock_mark,
            patch.object(svc, "_notify_payslip_available") as mock_notify,
            patch.object(svc, "_persist_salarie_notifie_le") as mock_persist,
        ):
            mock_meta.get_payslip_meta.return_value = {"id": "p-1"}
            mock_notify.side_effect = lambda *a, **k: notifications.append(a)
            ctx = MagicMock()
            ctx.user_id = "rh-1"
            svc.validate_payslip_for_user("p-1", ctx)
        return mock_mark, mock_persist

    def test_la_validation_notifie_une_fois(self):
        notifications = []
        mock_mark, mock_persist = self._valider({"net_a_payer": 100}, notifications)
        assert len(notifications) == 1
        mock_mark.assert_called_once()
        mock_persist.assert_called_once()

    def test_pas_de_renotification_si_deja_notifie(self):
        notifications = []
        _, mock_persist = self._valider(
            {"net_a_payer": 100, "salarie_notifie_le": "2026-08-01T10:00:00"},
            notifications,
        )
        assert notifications == []
        mock_persist.assert_not_called()


def test_espace_salarie_ne_liste_que_les_bulletins_valides():
    """Task 4 : un salarié ne voit jamais un brouillon (contrat vague 3)."""
    from unittest.mock import MagicMock

    from app.modules.payslips.infrastructure import queries as q

    fake = MagicMock()
    table = MagicMock()
    fake.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=[])

    with patch.object(q, "supabase", fake):
        q.get_my_payslips("emp-1")

    filtres = {appel.args for appel in table.eq.call_args_list}
    assert ("status", "valide") in filtres


def test_un_echec_de_notification_ne_fait_pas_echouer_la_validation():
    """Le marquage « validé » prime : une panne de notification se logge."""
    from unittest.mock import MagicMock, patch as p_

    from app.modules.payslips.application import comparison_service as svc

    detail = {
        "id": "p-1", "employee_id": "emp-1", "company_id": "comp-1",
        "year": 2026, "month": 5, "payslip_data": {"net_a_payer": 100},
    }
    resultat = MagicMock()
    resultat.alerts = []
    with (
        p_.object(svc, "payslip_meta_reader"),
        p_.object(svc, "_ensure_edit_meta"),
        p_.object(svc, "get_payslip_details", return_value=detail),
        p_.object(svc, "fetch_previous_validated_payslip", return_value=None),
        p_.object(svc, "fetch_employee_statut", return_value="Non-Cadre"),
        p_.object(svc, "fetch_recent_nets_asc_for_r10", return_value=[]),
        p_.object(svc, "compute_comparison", return_value=resultat),
        p_.object(svc, "mark_payslip_validated") as mock_mark,
        p_.object(svc, "_notify_payslip_available", side_effect=RuntimeError("smtp down")),
        p_.object(svc, "_persist_salarie_notifie_le") as mock_persist,
    ):
        ctx = MagicMock()
        ctx.user_id = "rh-1"
        svc.validate_payslip_for_user("p-1", ctx)  # ne doit PAS lever
    mock_mark.assert_called_once()
    mock_persist.assert_not_called()


def test_ijss_sur_bulletin_valide_archive_et_remet_en_brouillon():
    """La porte latérale IJSS suit le même protocole que la régénération
    forcée : archive avant, brouillon après — plus d'écrasement silencieux."""
    from unittest.mock import MagicMock

    from app.modules.ijss_tracking.application import apply_to_payslip as mod

    ordre = []
    existing = {
        "id": "p-1",
        "status": "valide",
        "payslip_data": {"net_a_payer": 900},
        "url": "ancien.pdf",
        "edit_history": [],
    }

    def fake_generation(*a, **k):
        ordre.append("generation")
        return {"status": "success", "payslip_id": "p-1"}

    fake_emp = MagicMock()
    fake_emp.data = {"statut": "Non-Cadre", "is_forfait_jour": False}
    fake_admin = MagicMock()
    fake_admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_emp

    with (
        patch.object(mod, "repo") as fake_repo,
        patch.object(mod, "get_supabase_admin_client", return_value=fake_admin),
        patch.object(mod, "_fetch_existing_payslip", return_value=existing),
        patch.object(mod, "_archive_before_regeneration") as m_archive,
        patch.object(mod, "_reset_payslip_flags_after_regeneration") as m_reset,
        patch(
            "app.modules.ijss_tracking.application.service._recompute_period",
            return_value={},
        ),
        patch(
            "app.modules.payroll.documents.payslip_generator.process_payslip_generation",
            side_effect=fake_generation,
        ),
    ):
        fake_repo.get_expected_line.return_value = {
            "id": "line-1",
            "period_id": "per-1",
            "employee_id": "emp-1",
            "ijss_brut_validated": 350.0,
            "ijss_theorique": 340.0,
            "validation_source": "manual",
        }
        fake_repo.get_period.return_value = {
            "id": "per-1",
            "company_id": "comp-1",
            "period_year": 2026,
            "period_month": 5,
            "status": "open",
        }
        fake_repo.list_expected_lines.return_value = []
        m_archive.side_effect = lambda *a, **k: ordre.append("archive")
        m_reset.side_effect = lambda *a, **k: ordre.append("reset")
        mod.apply_validated_ijss_to_payslip("comp-1", "line-1", "rh-1")

    assert ordre[:2] == ["archive", "generation"]
    assert "reset" in ordre


def test_scenario_de_vie_generation_validation_regeneration():
    """Task 6 — la chaîne complète, avec un vrai état partagé simulé :
    génération → validation (notifie 1 fois) → re-validation (ne renotifie
    pas) → régénération forcée (archive + brouillon) → re-validation
    (renotifie : le contenu a changé)."""
    from unittest.mock import MagicMock

    from app.modules.payslips.application import commands as cmd_mod
    from app.modules.payslips.application import comparison_service as svc
    from app.modules.payslips.application.dto import GeneratePayslipInput

    # ---- État partagé : la « base » du scénario -------------------------
    store = {
        "id": "p-1",
        "status": None,          # pas encore généré
        "payslip_data": None,
        "url": None,
        "edit_history": [],
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "year": 2026,
        "month": 5,
    }
    notifications = []

    def fake_generation(**k):
        store["status"] = "brouillon"
        store["payslip_data"] = {"net_a_payer": 1000}
        store["url"] = "v1.pdf"
        return {"status": "success", "message": "OK", "download_url": "u"}

    def fake_mark_validated(payslip_id, user_id):
        store["status"] = "valide"

    def fake_persist_notifie(payslip_id, pd):
        store["payslip_data"] = {**pd, "salarie_notifie_le": "2026-08-21T10:00"}

    def fake_archive(existing, c):
        store["edit_history"] = list(store["edit_history"]) + [
            {"action": "regeneration", "previous_payslip_data": existing["payslip_data"]}
        ]

    def fake_reset(payslip_id):
        store["status"] = "brouillon"

    def generer(force_valide=False):
        with (
            patch.object(cmd_mod, "_employee_repository") as m_repo,
            patch.object(cmd_mod, "employee_statut_reader") as m_reader,
            patch.object(cmd_mod, "payslip_generator_provider") as m_prov,
            patch.object(cmd_mod, "_calendar_row_status", return_value="saisi"),
            patch.object(
                cmd_mod, "_fetch_existing_payslip",
                side_effect=lambda *a: dict(store) if store["status"] else None,
            ),
            patch.object(cmd_mod, "_archive_before_regeneration", side_effect=fake_archive),
            patch.object(
                cmd_mod, "_reset_payslip_flags_after_regeneration", side_effect=fake_reset
            ),
        ):
            m_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            m_reader.get_employee_statut.return_value = "Non-Cadre"
            m_prov.generate_heures.side_effect = lambda **k: fake_generation(**k)
            return cmd_mod.generate_payslip(
                GeneratePayslipInput(
                    employee_id="emp-1", year=2026, month=5,
                    regenerer_bulletin_valide=force_valide,
                    requested_by="rh-1",
                )
            )

    def valider():
        resultat = MagicMock()
        resultat.alerts = []
        detail = dict(store)
        with (
            patch.object(svc, "payslip_meta_reader"),
            patch.object(svc, "_ensure_edit_meta"),
            patch.object(svc, "get_payslip_details", return_value=detail),
            patch.object(svc, "fetch_previous_validated_payslip", return_value=None),
            patch.object(svc, "fetch_employee_statut", return_value="Non-Cadre"),
            patch.object(svc, "fetch_recent_nets_asc_for_r10", return_value=[]),
            patch.object(svc, "compute_comparison", return_value=resultat),
            patch.object(svc, "mark_payslip_validated", side_effect=fake_mark_validated),
            patch.object(
                svc, "_notify_payslip_available",
                side_effect=lambda *a: notifications.append(a),
            ),
            patch.object(
                svc, "_persist_salarie_notifie_le", side_effect=fake_persist_notifie
            ),
        ):
            ctx = MagicMock()
            ctx.user_id = "rh-1"
            svc.validate_payslip_for_user("p-1", ctx)

    # 1. Génération initiale : brouillon, personne n'est notifié
    generer()
    assert store["status"] == "brouillon"
    assert notifications == []

    # 2. Validation : notifié UNE fois
    valider()
    assert store["status"] == "valide"
    assert len(notifications) == 1

    # 3. Re-validation (double clic) : pas de renotification
    valider()
    assert len(notifications) == 1

    # 4. Régénérer sans force : refusé
    from app.modules.payslips.application.dto import PayslipValidatedError

    with pytest.raises(PayslipValidatedError):
        generer()

    # 5. Régénération forcée : archivé, retour en brouillon
    generer(force_valide=True)
    assert store["status"] == "brouillon"
    assert len(store["edit_history"]) == 1

    # 6. Re-validation : renotifie (le contenu a changé)
    valider()
    assert store["status"] == "valide"
    assert len(notifications) == 2
