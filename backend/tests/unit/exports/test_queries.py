"""
Tests unitaires des queries applicatives exports.

Chaque query est testée avec providers, infrastructure queries et storage mockés.
"""
from unittest.mock import patch

import pytest

from app.modules.exports.application import queries
from app.modules.exports.schemas import ExportPreviewRequest


pytestmark = pytest.mark.unit


class TestPreviewExport:
    """Query preview_export : prévisualisation sans génération de fichier."""

    def test_unsupported_type_raises_value_error(self):
        """Type non supporté pour preview lève ValueError."""
        req = ExportPreviewRequest(export_type="journal_paie", period="2025-01")
        with patch.object(
            queries.domain_rules,
            "is_supported_export_type_for_preview",
            return_value=False,
        ):
            with pytest.raises(ValueError) as exc_info:
                queries.preview_export("company-1", req)
            assert "non implémenté" in str(exc_info.value)

    def test_journal_paie_preview_returns_response(self):
        """Preview journal_paie délègue au provider et retourne ExportPreviewResponse."""
        req = ExportPreviewRequest(export_type="journal_paie", period="2025-01")
        mock_preview = {
            "employees_count": 3,
            "totals": {"employees_count": 3, "total_brut": 10000.0},
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch.object(queries.domain_rules, "is_supported_export_type_for_preview", return_value=True):
            with patch.object(queries.providers, "preview_journal_paie", return_value=mock_preview):
                result = queries.preview_export("company-1", req)
        assert result.export_type == "journal_paie"
        assert result.period == "2025-01"
        assert result.employees_count == 3
        assert result.totals.employees_count == 3
        assert result.can_generate is True

    def test_virement_salaires_preview_calls_provider_with_params(self):
        """Preview virement_salaires appelle le provider avec excluded_employee_ids, execution_date, payment_label."""
        req = ExportPreviewRequest(
            export_type="virement_salaires",
            period="2025-02",
            excluded_employee_ids=["emp-2"],
            execution_date="2025-02-28",
            payment_label="Salaire fév",
        )
        mock_preview = {
            "employees_count": 5,
            "totals": {"employees_count": 5},
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch.object(queries.domain_rules, "is_supported_export_type_for_preview", return_value=True):
            with patch.object(queries.providers, "preview_paiement_salaires", return_value=mock_preview) as mock_prov:
                queries.preview_export("company-1", req)
                mock_prov.assert_called_once_with(
                    "company-1",
                    "2025-02",
                    None,
                    ["emp-2"],
                    "2025-02-28",
                    "Salaire fév",
                )

    def test_od_type_preview_returns_totals_from_total_debit(self):
        """Preview OD (od_salaires, etc.) mappe total_debit dans totals.total_amount."""
        req = ExportPreviewRequest(export_type="od_salaires", period="2025-01")
        mock_preview = {
            "total_debit": 15000.0,
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch.object(queries.domain_rules, "is_supported_export_type_for_preview", return_value=True):
            with patch.object(queries.providers, "preview_od", return_value=mock_preview):
                result = queries.preview_export("company-1", req)
        assert result.totals.total_amount == 15000.0
        assert result.employees_count == 0

    def test_dsn_mensuelle_preview_uses_filters(self):
        """Preview dsn_mensuelle utilise filters (dsn_type, establishment_id)."""
        req = ExportPreviewRequest(
            export_type="dsn_mensuelle",
            period="2025-01",
            filters={"dsn_type": "dsn_mensuelle_normale", "establishment_id": "etab-1"},
        )
        mock_preview = {
            "period": "2025-01",
            "nombre_salaries": 8,
            "masse_salariale_brute": 32000.0,
            "total_net_imposable": 28000.0,
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch.object(queries.domain_rules, "is_supported_export_type_for_preview", return_value=True):
            with patch.object(queries.providers, "preview_dsn", return_value=mock_preview) as mock_dsn:
                result = queries.preview_export("company-1", req)
                mock_dsn.assert_called_once_with(
                    "company-1",
                    "2025-01",
                    "dsn_mensuelle_normale",
                    None,
                    "etab-1",
                )
        assert result.employees_count == 8
        assert result.totals.total_brut == 32000.0

    def test_cabinet_preview_calls_provider(self):
        """Preview export_cabinet_* appelle preview_cabinet_export."""
        req = ExportPreviewRequest(export_type="export_cabinet_generique", period="2025-01")
        mock_preview = {
            "employees_count": 4,
            "totals": {"employees_count": 4},
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }
        with patch.object(queries.domain_rules, "is_supported_export_type_for_preview", return_value=True):
            with patch.object(queries.providers, "preview_cabinet_export", return_value=mock_preview) as mock_cab:
                result = queries.preview_export("company-1", req)
                mock_cab.assert_called_once_with("company-1", "2025-01", "export_cabinet_generique", None)
        assert result.export_type == "export_cabinet_generique"


class TestGetExportHistory:
    """Query get_export_history : liste des exports par entreprise."""

    def test_returns_empty_list_when_no_exports(self):
        """Sans exports en base, retourne liste vide et total 0."""
        with patch.object(queries.infra_queries, "list_exports_by_company", return_value=[]):
            result = queries.get_export_history("company-1")
        assert result.exports == []
        assert result.total == 0

    def test_returns_entries_with_generated_by_name(self):
        """Les entrées incluent generated_by_name via profiles_map et mappers."""
        exports_data = [
            {
                "id": "exp-1",
                "export_type": "journal_paie",
                "period": "2025-01",
                "status": "generated",
                "generated_at": "2025-01-15T10:00:00",
                "generated_by": "user-1",
                "report": {"totals": {"employees_count": 5}},
                "file_paths": ["path/1.xlsx"],
            },
        ]
        profiles_map = {"user-1": {"first_name": "Jean", "last_name": "Dupont"}}
        with patch.object(queries.infra_queries, "list_exports_by_company", return_value=exports_data):
            with patch.object(queries.infra_queries, "get_profiles_map", return_value=profiles_map):
                result = queries.get_export_history("company-1")
        assert result.total == 1
        assert len(result.exports) == 1
        assert result.exports[0].id == "exp-1"
        assert result.exports[0].generated_by_name == "Jean Dupont"
        assert result.exports[0].files_count == 1

    def test_filters_by_export_type_and_period(self):
        """list_exports_by_company est appelé avec export_type et period si fournis."""
        with patch.object(queries.infra_queries, "list_exports_by_company", return_value=[]) as mock_list:
            queries.get_export_history("company-1", export_type="dsn_mensuelle", period="2025-02")
            mock_list.assert_called_once_with("company-1", "dsn_mensuelle", "2025-02")


class TestGetExportForDownload:
    """Query get_export_for_download : URL signée du premier fichier."""

    def test_export_not_found_raises_value_error(self):
        """Si l'export n'existe pas, lève ValueError."""
        with patch.object(queries.infra_queries, "get_export_by_id", return_value=None):
            with pytest.raises(ValueError) as exc_info:
                queries.get_export_for_download("company-1", "unknown-id")
            assert "non trouvé" in str(exc_info.value).lower() or "Export" in str(exc_info.value)

    def test_export_without_files_raises_value_error(self):
        """Si l'export n'a pas de file_paths, lève ValueError."""
        with patch.object(
            queries.infra_queries,
            "get_export_by_id",
            return_value={"id": "exp-1", "file_paths": []},
        ):
            with pytest.raises(ValueError) as exc_info:
                queries.get_export_for_download("company-1", "exp-1")
            assert "fichier" in str(exc_info.value).lower() or "Aucun" in str(exc_info.value)

    def test_returns_signed_url_for_first_file(self):
        """Retourne l'URL signée du premier fichier."""
        with patch.object(
            queries.infra_queries,
            "get_export_by_id",
            return_value={"id": "exp-1", "file_paths": ["exports/co/file.xlsx"]},
        ):
            with patch.object(
                queries,
                "create_signed_url",
                return_value="https://signed.example.com/file.xlsx",
            ) as mock_signed:
                url = queries.get_export_for_download("company-1", "exp-1")
                mock_signed.assert_called_once_with("exports/co/file.xlsx", 3600)
                assert url == "https://signed.example.com/file.xlsx"
