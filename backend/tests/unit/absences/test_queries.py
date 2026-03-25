"""
Tests unitaires des queries du module absences (application/queries.py).

Repository et providers mockés. Pas de DB ni HTTP.
"""
from datetime import date
from unittest.mock import patch

import pytest

from app.modules.absences.application import queries


class TestGetUploadUrlSigned:
    """Query get_upload_url_signed."""

    def test_returns_path_and_signed_url(self):
        """Retourne dict avec path et signedURL."""
        with patch(
            "app.modules.absences.application.queries.storage_provider"
        ) as storage:
            storage.create_signed_upload_url.return_value = "https://signed.url/upload"
            result = queries.get_upload_url_signed("user-1", "doc.pdf")

        assert "path" in result
        assert "signedURL" in result
        assert result["signedURL"] == "https://signed.url/upload"
        assert result["path"].startswith("user-1/")
        assert "doc.pdf" not in result["path"]  # path est un nom unique
        storage.create_signed_upload_url.assert_called_once()

    def test_filename_without_extension(self):
        """Fichier sans extension → path sans point."""
        with patch(
            "app.modules.absences.application.queries.storage_provider"
        ) as storage:
            storage.create_signed_upload_url.return_value = "https://url"
            result = queries.get_upload_url_signed("user-1", "fichier")

        assert result["path"].startswith("user-1/")


class TestGetAbsenceRequests:
    """Query get_absence_requests."""

    def test_empty_list_when_no_requests(self):
        """Aucune demande → liste vide."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_status.return_value = []
            result = queries.get_absence_requests()
        assert result == []

    def test_enriches_requests_with_balances_and_returns_list(self):
        """Demandes présentes → enrichissement soldes, retour liste."""
        requests = [
            {
                "id": "req-1",
                "employee_id": "emp-1",
                "employee": {"id": "emp-1", "first_name": "Jean", "last_name": "Dupont"},
                "type": "conge_paye",
                "selected_days": ["2025-06-10"],
                "status": "pending",
            }
        ]
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_status.return_value = requests
            repo.list_validated_for_employees.return_value = []
            with patch(
                "app.modules.absences.application.queries.get_employees_hire_dates_batch",
                return_value={"emp-1": date(2020, 1, 15)},
            ):
                with patch(
                    "app.modules.absences.application.queries.get_repos_credits_by_employee_year",
                    return_value={"emp-1": 0.0},
                ):
                    result = queries.get_absence_requests()

        assert len(result) == 1
        assert "employee" in result[0]
        assert "balances" in result[0]["employee"]
        assert len(result[0]["employee"]["balances"]) > 0

    def test_calls_list_by_status_with_filter(self):
        """Filtre status passé au repository."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_status.return_value = []
            queries.get_absence_requests(status="pending")
            repo.list_by_status.assert_called_once_with("pending")


class TestGetAbsencesForEmployee:
    """Query get_absences_for_employee."""

    def test_empty_list_when_no_absences(self):
        """Aucune absence pour l'employé → liste vide."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_employee_id.return_value = []
            result = queries.get_absences_for_employee("emp-1")
        assert result == []

    def test_returns_list_from_repository(self):
        """Retourne la liste des demandes pour l'employé."""
        data = [
            {
                "id": "req-1",
                "employee_id": "emp-1",
                "type": "rtt",
                "selected_days": ["2025-06-10"],
                "status": "validated",
            }
        ]
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_employee_id.return_value = data
            result = queries.get_absences_for_employee("emp-1")
        assert len(result) == 1
        assert result[0]["id"] == "req-1"
        repo.list_by_employee_id.assert_called_once_with("emp-1")


class TestUpdateAbsenceRequestSignedUrlSingle:
    """Query update_absence_request_signed_url_single."""

    def test_returns_none_when_request_not_found(self):
        """Demande inexistante → None."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = None
            result = queries.update_absence_request_signed_url_single("req-unknown")
        assert result is None

    def test_returns_data_without_signed_url_when_no_attachment(self):
        """Demande sans attachment_url → retourne les données telles quelles."""
        data = {"id": "req-1", "attachment_url": None}
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = data
            result = queries.update_absence_request_signed_url_single("req-1")
        assert result == data


class TestGetMyAbsenceBalances:
    """Query get_my_absence_balances."""

    def test_raises_lookup_error_when_no_hire_date(self):
        """Pas de date d'embauche pour l'employé → LookupError."""
        with patch(
            "app.modules.absences.application.queries.get_employee_hire_date",
            return_value=None,
        ):
            with pytest.raises(LookupError, match="Date d'embauche"):
                queries.get_my_absence_balances("emp-1")

    def test_returns_balances_list_with_cp_rtt_repos_etc(self):
        """Avec hire_date et pas d'absences validées → soldes avec acquired, taken, remaining."""
        with patch(
            "app.modules.absences.application.queries.get_employee_hire_date",
            return_value="2020-01-15",
        ):
            with patch(
                "app.modules.absences.application.queries.absence_repository"
            ) as repo:
                repo.list_validated_for_employees.return_value = []
                with patch(
                    "app.modules.absences.application.queries.get_repos_credits_by_employee_year",
                    return_value={"emp-1": 2.0},
                ):
                    result = queries.get_my_absence_balances("emp-1")

        assert isinstance(result, list)
        types_found = [b["type"] for b in result]
        assert "Congés Payés" in types_found
        assert "RTT" in types_found
        assert "Repos compensateur" in types_found
        assert "Événement familial" in types_found
        assert "Congé sans solde" in types_found
        for b in result:
            assert "acquired" in b
            assert "taken" in b
            assert "remaining" in b


class TestGetMyMonthlyCalendar:
    """Query get_my_monthly_calendar."""

    def test_delegates_to_get_planned_calendar(self):
        """Délègue à get_planned_calendar(employee_id, year, month)."""
        with patch(
            "app.modules.absences.application.queries.get_planned_calendar"
        ) as get_cal:
            get_cal.return_value = [{"jour": 1, "type": "travail", "heures_prevues": 7}]
            result = queries.get_my_monthly_calendar("emp-1", 2025, 6)
            get_cal.assert_called_once_with("emp-1", 2025, 6)
        assert len(result) == 1
        assert result[0]["jour"] == 1


class TestGetMyAbsencesHistory:
    """Query get_my_absences_history."""

    def test_returns_empty_list_when_no_data(self):
        """Aucune demande → liste vide."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_employee_id.return_value = []
            result = queries.get_my_absences_history("emp-1")
        assert result == []

    def test_returns_list_from_repository(self):
        """Retourne l'historique pour l'employé."""
        data = [{"id": "req-1", "employee_id": "emp-1", "status": "validated"}]
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_employee_id.return_value = data
            result = queries.get_my_absences_history("emp-1")
        assert result == data
        repo.list_by_employee_id.assert_called_once_with("emp-1")


class TestGetMyAbsencesPageData:
    """Query get_my_absences_page_data."""

    def test_raises_lookup_error_when_no_hire_date(self):
        """Pas de date d'embauche → LookupError."""
        with patch(
            "app.modules.absences.application.queries.get_employee_hire_date",
            return_value=None,
        ):
            with pytest.raises(LookupError, match="Date d'embauche"):
                queries.get_my_absences_page_data("emp-1", 2025, 6)

    def test_returns_balances_calendar_days_history(self):
        """Retourne dict avec balances, calendar_days, history."""
        with patch(
            "app.modules.absences.application.queries.get_employee_hire_date",
            return_value="2020-01-15",
        ):
            with patch(
                "app.modules.absences.application.queries.absence_repository"
            ) as repo:
                repo.list_validated_for_employees.return_value = []
                repo.list_by_employee_id.return_value = []
                with patch(
                    "app.modules.absences.application.queries.get_repos_credits_by_employee_year",
                    return_value={"emp-1": 0.0},
                ):
                    with patch(
                        "app.modules.absences.application.queries.get_planned_calendar",
                        return_value=[],
                    ):
                        result = queries.get_my_absences_page_data(
                            "emp-1", 2025, 6
                        )

        assert "balances" in result
        assert "calendar_days" in result
        assert "history" in result
        assert isinstance(result["balances"], list)
        assert result["calendar_days"] == []
        assert result["history"] == []


class TestGetMyEvenementsFamiliaux:
    """Query get_my_evenements_familiaux."""

    def test_returns_empty_list_when_no_employee_resolved(self):
        """resolve_employee_id_for_user retourne None → liste vide."""
        with patch(
            "app.modules.absences.application.queries.resolve_employee_id_for_user",
            return_value=None,
        ):
            result = queries.get_my_evenements_familiaux("user-1")
        assert result == []

    def test_returns_events_from_provider_when_employee_resolved(self):
        """Employé résolu → délégation au provider, retour des événements."""
        events = [
            {
                "code": "mariage_salarie",
                "libelle": "Mariage du salarié",
                "duree_jours": 4,
                "type_jours": "ouvres",
                "quota": 1,
                "solde_restant": 1,
                "taken": 0,
                "cycles_completed": 0,
            }
        ]
        with patch(
            "app.modules.absences.application.queries.resolve_employee_id_for_user",
            return_value="emp-1",
        ):
            with patch(
                "app.modules.absences.application.queries.evenement_familial_provider"
            ) as prov:
                prov.get_events_disponibles.return_value = events
                result = queries.get_my_evenements_familiaux("user-1")
        assert result == events
        prov.get_events_disponibles.assert_called_once_with("emp-1")


class TestGetSalaryCertificateInfo:
    """Query get_salary_certificate_info."""

    def test_returns_none_when_absence_not_found(self):
        """Absence inexistante → None."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = None
            result = queries.get_salary_certificate_info("req-1")
        assert result is None

    def test_returns_none_when_no_certificate_record(self):
        """Absence trouvée mais pas d'enregistrement attestation → None."""
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {"id": "req-1"}
            with patch(
                "app.modules.absences.application.queries.get_salary_certificate_record",
                return_value=None,
            ):
                result = queries.get_salary_certificate_info("req-1")
        assert result is None

    def test_returns_cert_data_with_view_and_download_urls(self):
        """Enregistrement attestation présent → dict avec view_url et download_url."""
        cert_data = {
            "id": "cert-1",
            "storage_path": "emp-1/attestation.pdf",
            "filename": "attestation.pdf",
        }
        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.get_by_id.return_value = {"id": "req-1"}
            with patch(
                "app.modules.absences.application.queries.get_salary_certificate_record",
                return_value=cert_data,
            ):
                with patch(
                    "app.modules.absences.application.queries.storage_provider"
                ) as storage:
                    storage.create_signed_url.side_effect = [
                        "https://view.url",
                        "https://download.url",
                    ]
                    result = queries.get_salary_certificate_info("req-1")
        assert result is not None
        assert result.get("view_url") == "https://view.url"
        assert result.get("download_url") == "https://download.url"


class TestDownloadSalaryCertificate:
    """Query download_salary_certificate."""

    def test_returns_none_when_no_certificate_record(self):
        """Pas d'enregistrement attestation → None."""
        with patch(
            "app.modules.absences.application.queries.get_salary_certificate_record",
            return_value=None,
        ):
            result = queries.download_salary_certificate("req-1")
        assert result is None

    def test_returns_tuple_bytes_filename_when_success(self):
        """Enregistrement + téléchargement OK → (bytes, filename)."""
        with patch(
            "app.modules.absences.application.queries.get_salary_certificate_record",
            return_value={
                "storage_path": "path/to/file.pdf",
                "filename": "attestation.pdf",
            },
        ):
            with patch(
                "app.modules.absences.application.queries.storage_provider"
            ) as storage:
                storage.download.return_value = b"%PDF-1.4..."
                result = queries.download_salary_certificate("req-1")
        assert result is not None
        pdf_bytes, filename = result
        assert pdf_bytes == b"%PDF-1.4..."
        assert filename == "attestation.pdf"

    def test_returns_none_when_download_returns_error_dict(self):
        """storage.download retourne dict avec error → None."""
        with patch(
            "app.modules.absences.application.queries.get_salary_certificate_record",
            return_value={"storage_path": "path", "filename": "f.pdf"},
        ):
            with patch(
                "app.modules.absences.application.queries.storage_provider"
            ) as storage:
                storage.download.return_value = {"error": "not found"}
                result = queries.download_salary_certificate("req-1")
        assert result is None
