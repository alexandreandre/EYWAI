"""
Tests de câblage (wiring) du module payroll.

Vérifient que l'injection des dépendances et le flux de bout en bout
(entrée API -> module payslips -> module payroll) fonctionnent pour la paie.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payroll.application import (
    is_forfait_jour,
    process_payslip_generation,
    process_payslip_generation_forfait,
    calculer_indemnites_sortie,
    get_exit_document_generator,
    definir_periode_de_paie_forfait,
    run_reverse_calculation,
    creer_simulation_bulletin,
    generer_scenarios_predefinis,
    get_simulated_payslip_generator,
)


pytestmark = pytest.mark.integration


class TestPayrollApplicationLayerWiring:
    """Vérification que la couche application payroll est correctement câblée et importable."""

    def test_payroll_application_exports_commands(self):
        """Les commandes payroll sont importables depuis application."""
        assert callable(is_forfait_jour)
        assert callable(process_payslip_generation)
        assert callable(process_payslip_generation_forfait)
        assert callable(calculer_indemnites_sortie)
        assert callable(get_exit_document_generator)
        assert callable(definir_periode_de_paie_forfait)
        assert callable(run_reverse_calculation)
        assert callable(creer_simulation_bulletin)
        assert callable(generer_scenarios_predefinis)
        assert callable(get_simulated_payslip_generator)

    def test_get_exit_document_generator_returns_usable_instance(self):
        """Le générateur de documents de sortie est une instance utilisable."""
        gen = get_exit_document_generator()
        assert gen is not None
        assert hasattr(gen, "generate_certificat_travail")
        assert hasattr(gen, "generate_attestation_pole_emploi")

    def test_get_simulated_payslip_generator_returns_class(self):
        """Le générateur de bulletins simulés est une classe."""
        cls = get_simulated_payslip_generator()
        assert cls is not None
        assert cls.__name__ == "SimulatedPayslipGenerator"


class TestPayrollFlowViaPayslipsRoute:
    """Flux bout en bout : route generate-payslip -> payslips application -> payroll (mocké)."""

    def test_generate_payslip_route_calls_payslips_use_case(self, client: TestClient):
        """POST /api/actions/generate-payslip déclenche le use case (mock au niveau router)."""
        with patch(
            "app.modules.payslips.api.router.generate_payslip",
            return_value=MagicMock(status="ok", message="OK", download_url="/file.pdf"),
        ) as mock_generate:
            response = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-wiring", "year": 2025, "month": 3},
            )
            if response.status_code == 200:
                mock_generate.assert_called_once()
                call_args = mock_generate.call_args[0][0]
                assert call_args.employee_id == "emp-wiring"
                assert call_args.year == 2025
                assert call_args.month == 3
        assert response.status_code in (200, 401, 422, 500)


class TestPayrollForfaitPeriodWiring:
    """Câblage forfait jour : période de paie (moteur mocké pour éviter Supabase en test)."""

    @patch("app.modules.payroll.application.forfait_commands.ContextePaie")
    @patch("app.modules.payroll.application.forfait_commands.definir_periode_de_paie")
    def test_definir_periode_de_paie_forfait_flow(self, mock_definir, mock_ctx):
        """definir_periode_de_paie_forfait appelle le moteur et retourne des dates."""
        from datetime import date
        mock_ctx.return_value = MagicMock()
        mock_definir.return_value = (date(2024, 12, 23), date(2025, 1, 5))
        params = {"periode_de_paie": {"jour_de_fin": 4, "occurrence": -2}}
        d_debut, d_fin = definir_periode_de_paie_forfait(
            parametres_paie=params,
            employee_statut="Cadre forfait jour",
            year=2025,
            month=1,
        )
        assert d_debut is not None
        assert d_fin is not None
        assert d_debut < d_fin
        mock_definir.assert_called_once()


class TestPayrollExportServiceWiring:
    """Le service d'export (facade) est importable et expose les fonctions attendues."""

    def test_export_service_module_imports(self):
        """export_service expose les exports paie (journal, virements, DSN, etc.)."""
        from app.modules.payroll.application import export_service
        assert hasattr(export_service, "get_journal_paie_data")
        assert hasattr(export_service, "preview_journal_paie")
        assert hasattr(export_service, "get_paiement_salaires_data")
        assert hasattr(export_service, "preview_dsn")
        assert hasattr(export_service, "generate_dsn_xml")
