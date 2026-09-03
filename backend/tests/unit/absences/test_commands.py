"""
Tests unitaires des commandes du module absences (application/commands.py).

Repositories et providers (infrastructure) mockés. Pas de DB ni HTTP.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application import commands
from app.modules.maintenance_settings.schemas.responses import MaintenanceSettings


class TestCreateAbsenceRequest:
    """Commande create_absence_request."""

    def test_raises_value_error_when_no_selected_days(self):
        """Sans jour sélectionné → ValueError."""
        request_data = MagicMock()
        request_data.selected_days = []
        request_data.type = "conge_paye"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = None

        with pytest.raises(ValueError, match="au moins un jour"):
            commands.create_absence_request(request_data)

    def test_raises_value_error_when_selected_days_none(self):
        """selected_days None ou absent → traité comme liste vide → ValueError."""
        request_data = MagicMock()
        request_data.selected_days = None
        request_data.type = "conge_paye"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = None

        with pytest.raises(ValueError, match="au moins un jour"):
            commands.create_absence_request(request_data)

    def test_raises_value_error_for_evenement_familial_without_subtype(self):
        """Type evenement_familial sans event_subtype → ValueError."""
        request_data = MagicMock()
        request_data.selected_days = [date(2025, 6, 10)]
        request_data.type = "evenement_familial"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = None

        with pytest.raises(ValueError, match="événement familial"):
            commands.create_absence_request(request_data)

    def test_raises_lookup_error_when_employee_not_found(self):
        """Employé sans company_id → LookupError."""
        request_data = MagicMock()
        request_data.selected_days = [date(2025, 6, 10)]
        request_data.type = "conge_paye"
        request_data.employee_id = "emp-unknown"
        request_data.event_subtype = None
        request_data.comment = None
        request_data.attachment_url = None
        request_data.filename = None

        with patch(
            "app.modules.absences.application.commands.get_employee_company_id",
            return_value=None,
        ):
            with pytest.raises(LookupError, match="Employé non trouvé"):
                commands.create_absence_request(request_data)

    def test_creates_absence_and_returns_repository_result(self):
        """Données valides → appel repository.create avec les bons champs, retourne le résultat."""
        request_data = MagicMock()
        request_data.selected_days = [date(2025, 6, 10), date(2025, 6, 11)]
        request_data.type = "rtt"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = None
        request_data.comment = "RTT"
        request_data.attachment_url = None
        request_data.filename = None

        created_row = {
            "id": "req-new",
            "employee_id": "emp-1",
            "company_id": "comp-1",
            "type": "rtt",
            "status": "pending",
            "selected_days": ["2025-06-10", "2025-06-11"],
            "comment": "RTT",
        }

        with patch(
            "app.modules.absences.application.commands.get_employee_company_id",
            return_value="comp-1",
        ):
            with patch(
                "app.modules.absences.application.commands.absence_repository"
            ) as repo:
                repo.create.return_value = created_row
                result = commands.create_absence_request(request_data)

        assert result == created_row
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data["employee_id"] == "emp-1"
        assert call_data["company_id"] == "comp-1"
        assert call_data["type"] == "rtt"
        assert call_data["status"] == "pending"
        assert call_data["comment"] == "RTT"
        assert "2025-06-10" in call_data["selected_days"]
        assert "2025-06-11" in call_data["selected_days"]

    def test_evenement_familial_with_solde_calls_provider_and_repository(self):
        """Événement familial avec solde restant → appel evenement_familial_provider puis repository."""
        request_data = MagicMock()
        request_data.selected_days = [date(2025, 7, 1)]
        request_data.type = "evenement_familial"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = "mariage_salarie"
        request_data.comment = None
        request_data.attachment_url = None
        request_data.filename = None

        with patch(
            "app.modules.absences.application.commands.get_employee_hire_date",
            return_value="2020-01-15",
        ):
            with patch(
                "app.modules.absences.application.commands.evenement_familial_provider"
            ) as prov:
                prov.get_solde_evenement.return_value = {
                    "solde_restant": 2,
                    "cycles_completed": 0,
                }
                with patch(
                    "app.modules.absences.application.commands.get_employee_company_id",
                    return_value="comp-1",
                ):
                    with patch(
                        "app.modules.absences.application.commands.absence_repository"
                    ) as repo:
                        repo.create.return_value = {"id": "req-ef"}
                        result = commands.create_absence_request(request_data)

        assert result["id"] == "req-ef"
        prov.get_solde_evenement.assert_called_once()
        call_args = prov.get_solde_evenement.call_args
        assert call_args[0][0] == "emp-1"
        assert call_args[0][1] == "mariage_salarie"
        repo.create.assert_called_once()
        assert repo.create.call_args[0][0].get("event_subtype") == "mariage_salarie"

    def test_evenement_familial_zero_solde_raises_value_error(self):
        """Événement familial avec solde restant 0 → ValueError."""
        request_data = MagicMock()
        request_data.selected_days = [date(2025, 7, 1)]
        request_data.type = "evenement_familial"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = "mariage_salarie"

        with patch(
            "app.modules.absences.application.commands.get_employee_hire_date",
            return_value="2020-01-15",
        ):
            with patch(
                "app.modules.absences.application.commands.evenement_familial_provider"
            ) as prov:
                prov.get_solde_evenement.return_value = {
                    "solde_restant": 0,
                    "cycles_completed": 1,
                }
                with pytest.raises(ValueError, match="Aucun jour restant"):
                    commands.create_absence_request(request_data)

    def test_evenement_familial_demande_superieure_au_solde_raises_value_error(self):
        """Événement familial : jours demandés > solde restant → ValueError."""
        request_data = MagicMock()
        request_data.selected_days = [
            date(2025, 7, 1),
            date(2025, 7, 2),
            date(2025, 7, 3),
        ]
        request_data.type = "evenement_familial"
        request_data.employee_id = "emp-1"
        request_data.event_subtype = "mariage_salarie"

        with patch(
            "app.modules.absences.application.commands.get_employee_hire_date",
            return_value="2020-01-15",
        ):
            with patch(
                "app.modules.absences.application.commands.evenement_familial_provider"
            ) as prov:
                prov.get_solde_evenement.return_value = {
                    "solde_restant": 2,
                    "cycles_completed": 0,
                }
                with pytest.raises(ValueError, match="droit à 2 jour"):
                    commands.create_absence_request(request_data)


class TestUpdateAbsenceRequestStatus:
    """Commande update_absence_request_status."""

    def test_raises_lookup_error_when_request_not_found(self):
        """Demande inexistante → LookupError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(LookupError, match="non trouvée"):
                commands.update_absence_request_status("req-unknown", "validated")

    def test_updates_status_and_returns_updated_data(self):
        """Demande trouvée → update avec le statut, retourne les données mises à jour."""
        req_before = {
            "id": "req-1",
            "employee_id": "emp-1",
            "type": "rtt",
            "status": "pending",
            "selected_days": ["2025-06-10"],
        }
        updated = {
            "id": "req-1",
            "employee_id": "emp-1",
            "type": "rtt",
            "status": "rejected",
            "selected_days": ["2025-06-10"],
        }

        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = req_before
            repo.update.return_value = updated
            result = commands.update_absence_request_status("req-1", "rejected")

        assert result == updated
        repo.update.assert_called_once_with("req-1", {"status": "rejected"})

    def test_validated_conge_paye_sets_jours_payes_and_updates_calendar(self):
        """Validation d'un congé payé → calcul jours_payes, mise à jour calendrier."""
        req_before = {
            "id": "req-cp",
            "employee_id": "emp-1",
            "type": "conge_paye",
            "status": "pending",
            "selected_days": ["2025-06-10", "2025-06-11", "2025-06-12"],
        }
        updated = {
            **req_before,
            "status": "validated",
            "jours_payes": 2,
            "selected_days": ["2025-06-10", "2025-06-11", "2025-06-12"],
        }

        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = req_before
            repo.update.return_value = updated
            with patch(
                "app.modules.absences.application.commands.get_cp_solde_restant",
                return_value=25.0,
            ):
                with patch(
                    "app.modules.absences.application.commands.calendar_update_provider"
                ) as cal:
                    with patch(
                        "app.modules.absences.application.commands.get_maintenance_settings",
                        return_value=MaintenanceSettings(company_id="company-1"),
                    ):
                        result = commands.update_absence_request_status(
                            "req-cp", "validated", current_user_id="user-1"
                        )

        assert result["status"] == "validated"
        call_update = repo.update.call_args[0][1]
        assert "status" in call_update
        assert "jours_payes" in call_update
        cal.update_calendar_from_days.assert_called_once()

    def _valider_cp(self, nb_jours_demandes: int, solde_restant: float) -> dict:
        """Valide un CP de nb_jours avec un solde affiché donné, rend l'update."""
        req_before = {
            "id": "req-cp",
            "employee_id": "emp-1",
            "type": "conge_paye",
            "status": "pending",
            "selected_days": [
                f"2026-08-{10 + i:02d}" for i in range(nb_jours_demandes)
            ],
        }
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = req_before
            repo.update.return_value = {**req_before, "status": "validated"}
            with patch(
                "app.modules.absences.application.commands.get_cp_solde_restant",
                return_value=solde_restant,
            ):
                with patch(
                    "app.modules.absences.application.commands.calendar_update_provider"
                ):
                    with patch(
                        "app.modules.absences.application.commands.get_maintenance_settings",
                        return_value=MaintenanceSettings(company_id="company-1"),
                    ):
                        commands.update_absence_request_status(
                            "req-cp", "validated", current_user_id="user-1"
                        )
            return repo.update.call_args[0][1]

    def test_jours_payes_est_toujours_un_entier(self):
        """Retour Gaëlle 03/09 : un solde float (10.0) partait tel quel dans la
        colonne integer jours_payes → 22P02 « invalid input syntax ». Le cas
        « demande > solde » doit produire un int."""
        call_update = self._valider_cp(nb_jours_demandes=15, solde_restant=10.0)
        assert call_update["jours_payes"] == 10
        assert isinstance(call_update["jours_payes"], int)

    def test_jours_payes_utilise_le_solde_affiche(self):
        """Le solde retenu est celui AFFICHÉ à la RH (report N-1 compris) :
        24,96 j pour 15 demandés → 15 payés, aucun jour « sans solde »."""
        call_update = self._valider_cp(nb_jours_demandes=15, solde_restant=24.96)
        assert call_update["jours_payes"] == 15
        assert isinstance(call_update["jours_payes"], int)

    def test_jours_payes_plancher_du_solde_fractionnaire(self):
        """Un solde fractionnaire insuffisant est PLANCHÉ : 10,5 j pour 15
        demandés → 10 payés (pas de fraction de jour payée)."""
        call_update = self._valider_cp(nb_jours_demandes=15, solde_restant=10.5)
        assert call_update["jours_payes"] == 10

    def test_raises_lookup_error_if_update_returns_none(self):
        """Si repository.update retourne None → LookupError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {"id": "req-1", "type": "rtt"}
            repo.update.return_value = None
            with pytest.raises(LookupError, match="introuvable après"):
                commands.update_absence_request_status("req-1", "cancelled")


class TestModulationRecoveryOnValidation:
    """Débit compte modulation à la validation d'une récup."""

    def test_raises_when_balance_insufficient(self):
        data = {
            "company_id": "company-1",
            "employee_id": "emp-1",
            "selected_days": ["2026-03-10", "2026-03-11", "2026-03-12"],
        }
        with patch(
            "app.modules.modulation.infrastructure.repository.get_modulation_settings"
        ) as mock_settings:
            mock_settings.return_value = type(
                "S",
                (),
                {
                    "hour_account_enabled": True,
                    "recovery_absence_enabled": True,
                    "recovery_debit_timing": "on_validation",
                },
            )()
            with patch(
                "app.modules.absences.application.commands.supabase"
            ) as mock_sb:
                mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = type(
                    "R", (), {"data": [{"duree_hebdomadaire": 35}]}
                )()
                with patch(
                    "app.modules.modulation.application.hour_account_queries.get_employee_account_balance"
                ) as mock_bal:
                    mock_bal.return_value = type(
                        "B", (), {"account_balance_hours": 2.0}
                    )()
                    with pytest.raises(ValueError, match="Solde modulation insuffisant"):
                        commands._apply_modulation_recovery_on_validation(
                            data, "req-mod-1"
                        )

    def test_creates_debit_when_balance_sufficient(self):
        data = {
            "company_id": "company-1",
            "employee_id": "emp-1",
            "selected_days": ["2026-03-10"],
        }
        with patch(
            "app.modules.modulation.infrastructure.repository.get_modulation_settings"
        ) as mock_settings:
            mock_settings.return_value = type(
                "S",
                (),
                {
                    "hour_account_enabled": True,
                    "recovery_absence_enabled": True,
                    "recovery_debit_timing": "on_validation",
                },
            )()
            with patch(
                "app.modules.absences.application.commands.supabase"
            ) as mock_sb:
                mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = type(
                    "R", (), {"data": [{"duree_hebdomadaire": 35}]}
                )()
                with patch(
                    "app.modules.modulation.application.hour_account_queries.get_employee_account_balance"
                ) as mock_bal:
                    mock_bal.return_value = type(
                        "B", (), {"account_balance_hours": 20.0}
                    )()
                    with patch(
                        "app.modules.modulation.application.hour_account_commands.create_debit_recovery_movement"
                    ) as mock_debit:
                        commands._apply_modulation_recovery_on_validation(
                            data, "req-mod-1"
                        )
                        mock_debit.assert_called_once()
                        assert mock_debit.call_args[0][4] == 7.0  # 1 jour × 35/5


class TestGenerateSalaryCertificate:
    """Commande generate_salary_certificate."""

    def test_raises_lookup_error_when_absence_not_found(self):
        """Arrêt inexistant → LookupError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(LookupError, match="Arrêt non trouvé"):
                commands.generate_salary_certificate("req-unknown")

    def test_raises_value_error_when_not_validated(self):
        """Arrêt non validé → ValueError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {
                "id": "req-1",
                "status": "pending",
                "type": "arret_maladie",
            }
            with pytest.raises(ValueError, match="doit être validé"):
                commands.generate_salary_certificate("req-1")

    def test_raises_value_error_when_type_not_eligible(self):
        """Type ne nécessitant pas d'attestation → ValueError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {
                "id": "req-1",
                "status": "validated",
                "type": "conge_paye",
            }
            with pytest.raises(ValueError, match="ne nécessite pas"):
                commands.generate_salary_certificate("req-1")

    def test_raises_runtime_error_when_provider_returns_none(self):
        """Provider retourne None → RuntimeError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {
                "id": "req-1",
                "status": "validated",
                "type": "arret_maladie",
            }
            with patch(
                "app.modules.absences.application.commands.salary_certificate_provider"
            ) as prov:
                prov.generate_for_absence.return_value = None
                with pytest.raises(RuntimeError, match="génération de l'attestation"):
                    commands.generate_salary_certificate("req-1")

    def test_returns_certificate_id_on_success(self):
        """Arrêt validé et type éligible → retourne certificate_id."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {
                "id": "req-1",
                "status": "validated",
                "type": "arret_maladie",
            }
            with patch(
                "app.modules.absences.application.commands.salary_certificate_provider"
            ) as prov:
                prov.generate_for_absence.return_value = "cert-uuid-123"
                result = commands.generate_salary_certificate(
                    "req-1", generated_by="user-1"
                )
        assert result == "cert-uuid-123"
        prov.generate_for_absence.assert_called_once_with(
            "req-1", generated_by="user-1", replace_existing=True
        )


class TestModulationRecoveryPreCheck:
    """Le refus d'une récup modulation ne doit PAS laisser l'absence validée."""

    def test_solde_insuffisant_refuse_avant_l_ecriture_du_statut(self):
        req_before = {
            "id": "req-recup",
            "employee_id": "emp-1",
            "company_id": "comp-1",
            "type": "recuperation_modulation",
            "status": "pending",
            "selected_days": ["2026-08-10"],
        }
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = req_before
            with patch(
                "app.modules.absences.application.commands._verifier_modulation_recovery",
                side_effect=ValueError("Solde modulation insuffisant"),
            ):
                with pytest.raises(ValueError, match="Solde modulation"):
                    commands.update_absence_request_status(
                        "req-recup", "validated", current_user_id="user-1"
                    )
        repo.update.assert_not_called()
