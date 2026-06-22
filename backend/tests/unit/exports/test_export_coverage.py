"""
Matrice de couverture : chaque type d'export exposé dans l'UI doit être
supporté pour preview et generate, avec un handler queries + service.
"""

import pytest

from app.modules.exports.application import queries, service
from app.modules.exports.domain import rules
from app.modules.exports.domain.value_objects import (
    EXPORT_TYPES_GENERATE,
    EXPORT_TYPES_PREVIEW,
)
from app.modules.exports.schemas import ExportPreviewRequest

pytestmark = pytest.mark.unit

# Types actifs dans l'interface (hors « À venir »)
UI_EXPORT_TYPES = [
    "journal_paie",
    "od_salaires",
    "od_charges_sociales",
    "od_pas",
    "od_globale",
    "fec",
    "export_cabinet_generique",
    "export_cabinet_quadra",
    "export_cabinet_sage",
    "acomptes",
    "saisies",
    "prets_employeur",
    "paiement_organismes",
    "attestations_annexes",
    "dsn_mensuelle",
    "virement_salaires",
    "recapitulatif_montants",
    "charges_sociales",
    "conges_absences",
    "notes_frais",
]


class TestExportTypeCoverage:
    @pytest.mark.parametrize("export_type", UI_EXPORT_TYPES)
    def test_ui_export_supported_for_preview(self, export_type: str):
        assert rules.is_supported_export_type_for_preview(export_type) is True
        assert export_type in EXPORT_TYPES_PREVIEW

    @pytest.mark.parametrize("export_type", UI_EXPORT_TYPES)
    def test_ui_export_supported_for_generate(self, export_type: str):
        assert rules.is_supported_export_type_for_generate(export_type) is True
        assert export_type in EXPORT_TYPES_GENERATE

    @pytest.mark.parametrize("export_type", UI_EXPORT_TYPES)
    def test_preview_query_has_handler(self, export_type: str, monkeypatch):
        """Chaque type UI doit passer par queries.preview_export sans 'non implémenté'."""
        mock_preview = {
            "employees_count": 1,
            "totals": {"employees_count": 1, "total_amount": 100.0},
            "anomalies": [],
            "warnings": [],
            "can_generate": True,
        }

        provider_mocks = {
            "journal_paie": "preview_journal_paie",
            "virement_salaires": "preview_paiement_salaires",
            "recapitulatif_montants": "preview_recapitulatif_montants",
            "charges_sociales": "preview_charges_sociales",
            "conges_absences": "preview_conges_absences",
            "notes_frais": "preview_notes_frais",
            "acomptes": "preview_acomptes",
            "saisies": "preview_saisies",
            "fec": "preview_fec",
            "prets_employeur": "preview_prets_employeur",
            "paiement_organismes": "preview_paiement_organismes",
            "attestations_annexes": "preview_attestations",
            "dsn_mensuelle": "preview_dsn",
            "od_salaires": "preview_od",
            "od_charges_sociales": "preview_od",
            "od_pas": "preview_od",
            "od_globale": "preview_od",
            "export_cabinet_generique": "preview_cabinet_export",
            "export_cabinet_quadra": "preview_cabinet_export",
            "export_cabinet_sage": "preview_cabinet_export",
        }

        if export_type.startswith("od_"):
            mock_preview["total_debit"] = 100.0
            mock_preview["can_generate"] = True

        if export_type == "dsn_mensuelle":
            mock_preview = {
                "nombre_salaries": 1,
                "masse_salariale_brute": 1000.0,
                "total_net_imposable": 800.0,
                "period": "2025-06",
                "anomalies": [],
                "warnings": [],
                "can_generate": True,
            }

        provider_name = provider_mocks[export_type]
        monkeypatch.setattr(
            queries.providers, provider_name, lambda *a, **k: mock_preview
        )

        req = ExportPreviewRequest(export_type=export_type, period="2025-06")
        result = queries.preview_export("company-1", req)
        assert result.export_type == export_type

    @pytest.mark.parametrize("export_type", UI_EXPORT_TYPES)
    def test_generate_service_has_handler(self, export_type: str):
        """Le service doit router chaque type UI vers un handler dédié."""
        handler_names = {
            "journal_paie": "_generate_journal_paie",
            "virement_salaires": "_generate_virement_salaires",
            "recapitulatif_montants": "_generate_recapitulatif_montants",
            "charges_sociales": "_generate_charges_sociales",
            "conges_absences": "_generate_conges_absences",
            "notes_frais": "_generate_notes_frais",
            "acomptes": "_generate_acomptes",
            "saisies": "_generate_saisies",
            "fec": "_generate_fec",
            "prets_employeur": "_generate_prets_employeur",
            "paiement_organismes": "_generate_paiement_organismes",
            "attestations_annexes": "_generate_attestations",
            "dsn_mensuelle": "_generate_dsn",
            "od_salaires": "_generate_od",
            "od_charges_sociales": "_generate_od",
            "od_pas": "_generate_od",
            "od_globale": "_generate_od",
            "export_cabinet_generique": "_generate_cabinet",
            "export_cabinet_quadra": "_generate_cabinet",
            "export_cabinet_sage": "_generate_cabinet",
        }
        assert hasattr(service, handler_names[export_type])
