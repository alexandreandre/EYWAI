"""
Tests unitaires du domaine exports : value objects et règles métier.

Sans DB, sans HTTP. Couvre value_objects (frozensets) et rules (validation DSN, types supportés).
"""
import pytest

from app.modules.exports.domain.value_objects import (
    EXPORT_TYPES_PREVIEW,
    EXPORT_TYPES_GENERATE,
    EXPORT_TYPES_OD,
    EXPORT_TYPES_CABINET,
)
from app.modules.exports.domain import rules


pytestmark = pytest.mark.unit


class TestExportValueObjects:
    """Value objects : ensembles de types d'export."""

    def test_export_types_preview_contains_all_preview_types(self):
        """EXPORT_TYPES_PREVIEW contient journal_paie, virement_salaires, od_*, cabinet, dsn_mensuelle."""
        expected = {
            "journal_paie",
            "virement_salaires",
            "od_salaires",
            "od_charges_sociales",
            "od_pas",
            "od_globale",
            "export_cabinet_generique",
            "export_cabinet_quadra",
            "export_cabinet_sage",
            "dsn_mensuelle",
        }
        assert expected == set(EXPORT_TYPES_PREVIEW)
        assert isinstance(EXPORT_TYPES_PREVIEW, frozenset)

    def test_export_types_generate_equals_preview(self):
        """EXPORT_TYPES_GENERATE contient les mêmes types que PREVIEW pour ce module."""
        assert EXPORT_TYPES_GENERATE == EXPORT_TYPES_PREVIEW

    def test_export_types_od_subset(self):
        """EXPORT_TYPES_OD ne contient que les types OD (écritures comptables)."""
        assert EXPORT_TYPES_OD == frozenset({
            "od_salaires",
            "od_charges_sociales",
            "od_pas",
            "od_globale",
        })
        for t in EXPORT_TYPES_OD:
            assert t in EXPORT_TYPES_PREVIEW

    def test_export_types_cabinet_subset(self):
        """EXPORT_TYPES_CABINET ne contient que les types cabinet."""
        assert EXPORT_TYPES_CABINET == frozenset({
            "export_cabinet_generique",
            "export_cabinet_quadra",
            "export_cabinet_sage",
        })
        for t in EXPORT_TYPES_CABINET:
            assert t in EXPORT_TYPES_PREVIEW


class TestRulesPreview:
    """Règle is_supported_export_type_for_preview."""

    def test_preview_journal_paie_supported(self):
        assert rules.is_supported_export_type_for_preview("journal_paie") is True

    def test_preview_virement_salaires_supported(self):
        assert rules.is_supported_export_type_for_preview("virement_salaires") is True

    def test_preview_dsn_mensuelle_supported(self):
        assert rules.is_supported_export_type_for_preview("dsn_mensuelle") is True

    def test_preview_od_types_supported(self):
        for t in ["od_salaires", "od_charges_sociales", "od_pas", "od_globale"]:
            assert rules.is_supported_export_type_for_preview(t) is True

    def test_preview_cabinet_types_supported(self):
        for t in ["export_cabinet_generique", "export_cabinet_quadra", "export_cabinet_sage"]:
            assert rules.is_supported_export_type_for_preview(t) is True

    def test_preview_unknown_type_not_supported(self):
        assert rules.is_supported_export_type_for_preview("export_fictif") is False
        assert rules.is_supported_export_type_for_preview("") is False


class TestRulesGenerate:
    """Règle is_supported_export_type_for_generate."""

    def test_generate_journal_paie_supported(self):
        assert rules.is_supported_export_type_for_generate("journal_paie") is True

    def test_generate_dsn_mensuelle_supported(self):
        assert rules.is_supported_export_type_for_generate("dsn_mensuelle") is True

    def test_generate_unknown_type_not_supported(self):
        assert rules.is_supported_export_type_for_generate("autre_type") is False


class TestValidateDsnCanGenerate:
    """Règle validate_dsn_can_generate : anomalies bloquantes et avertissements."""

    def test_no_anomalies_no_warnings_ok(self):
        """Sans anomalies ni warnings, ne lève pas."""
        rules.validate_dsn_can_generate(
            preview_data={"anomalies": [], "warnings": []},
            accept_warnings=False,
        )

    def test_blocking_anomaly_raises(self):
        """Une anomalie bloquante lève ValueError."""
        with pytest.raises(ValueError) as exc_info:
            rules.validate_dsn_can_generate(
                preview_data={
                    "anomalies": [{"severity": "blocking", "message": "Erreur"}],
                    "warnings": [],
                },
                accept_warnings=True,
            )
        assert "bloquante" in str(exc_info.value).lower() or "impossible" in str(exc_info.value).lower()

    def test_multiple_blocking_raises(self):
        """Plusieurs anomalies bloquantes lèvent avec le bon message."""
        with pytest.raises(ValueError) as exc_info:
            rules.validate_dsn_can_generate(
                preview_data={
                    "anomalies": [
                        {"severity": "blocking"},
                        {"severity": "blocking"},
                    ],
                    "warnings": [],
                },
                accept_warnings=True,
            )
        assert "2 anomalie(s) bloquante(s)" in str(exc_info.value)

    def test_warnings_without_accept_raises(self):
        """Des warnings sans accept_warnings lèvent ValueError."""
        with pytest.raises(ValueError) as exc_info:
            rules.validate_dsn_can_generate(
                preview_data={
                    "anomalies": [],
                    "warnings": ["Avertissement 1"],
                },
                accept_warnings=False,
            )
        assert "avertissement" in str(exc_info.value).lower()

    def test_warnings_with_accept_ok(self):
        """Des warnings avec accept_warnings=True ne lèvent pas."""
        rules.validate_dsn_can_generate(
            preview_data={
                "anomalies": [],
                "warnings": ["Avertissement"],
            },
            accept_warnings=True,
        )

    def test_preview_data_without_anomalies_key_ok(self):
        """preview_data sans clé 'anomalies' traité comme liste vide."""
        rules.validate_dsn_can_generate(preview_data={}, accept_warnings=True)
        rules.validate_dsn_can_generate(preview_data={"warnings": []}, accept_warnings=False)

    def test_warning_severity_ignored_for_blocking(self):
        """Seules les anomalies avec severity=='blocking' bloquent."""
        rules.validate_dsn_can_generate(
            preview_data={
                "anomalies": [{"severity": "warning", "message": "Info"}],
                "warnings": [],
            },
            accept_warnings=False,
        )
