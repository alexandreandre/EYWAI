"""
Tests unitaires des commandes du module absences (application/commands.py).

Repositories et providers (infrastructure) mockés. Pas de DB ni HTTP.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application import commands


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
                "app.modules.absences.application.commands.get_employee_hire_date",
                return_value="2020-01-01",
            ):
                with patch(
                    "app.modules.absences.application.commands.list_absence_requests_validated_for_cp",
                    return_value=[],
                ):
                    with patch(
                        "app.modules.absences.application.commands.calendar_update_provider"
                    ) as cal:
                        result = commands.update_absence_request_status(
                            "req-cp", "validated", current_user_id="user-1"
                        )

        assert result["status"] == "validated"
        call_update = repo.update.call_args[0][1]
        assert "status" in call_update
        assert "jours_payes" in call_update
        cal.update_calendar_from_days.assert_called_once()

    def test_raises_lookup_error_if_update_returns_none(self):
        """Si repository.update retourne None → LookupError."""
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {"id": "req-1", "type": "rtt"}
            repo.update.return_value = None
            with pytest.raises(LookupError, match="introuvable après"):
                commands.update_absence_request_status("req-1", "cancelled")


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
            "req-1", generated_by="user-1"
        )
