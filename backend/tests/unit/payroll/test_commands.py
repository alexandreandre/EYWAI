"""
Tests unitaires des commandes du module payroll (application/).

Couverture : payslip_commands, forfait_commands, simulation_commands,
indemnites_commands, exit_document_commands. Repositories et sous-modules mockés.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application.payslip_commands import (
    is_forfait_jour,
    process_payslip_generation,
    process_payslip_generation_forfait,
    save_edited_payslip,
    restore_payslip_version,
)
from app.modules.payroll.application.forfait_commands import (
    definir_periode_de_paie_forfait,
    analyser_jours_forfait_du_mois,
)
from app.modules.payroll.application.simulation_commands import (
    run_reverse_calculation,
    creer_simulation_bulletin,
    comparer_simulation_reel,
    generer_scenarios_predefinis,
    get_simulated_payslip_generator,
)
from app.modules.payroll.application.indemnites_commands import calculer_indemnites_sortie
from app.modules.payroll.application.exit_document_commands import get_exit_document_generator


pytestmark = pytest.mark.unit


# --- Payslip commands ---


class TestPayslipCommandsIsForfaitJour:
    """is_forfait_jour (déjà couvert en domain, rappel)."""

    def test_forfait_jour_true(self):
        assert is_forfait_jour("Cadre forfait jour") is True

    def test_forfait_jour_false(self):
        assert is_forfait_jour("Cadre") is False


class TestPayslipCommandsProcessGeneration:
    """process_payslip_generation et process_payslip_generation_forfait avec mocks (délégation vers documents)."""

    @patch("app.modules.payroll.documents.payslip_generator.process_payslip_generation")
    def test_process_payslip_generation_delegates_to_documents(self, mock_impl):
        mock_impl.return_value = {"status": "ok", "message": "OK", "download_url": "/f.pdf"}
        result = process_payslip_generation("emp-1", 2025, 3)
        mock_impl.assert_called_once_with(employee_id="emp-1", year=2025, month=3)
        assert result["status"] == "ok"
        assert result["download_url"] == "/f.pdf"

    @patch("app.modules.payroll.documents.payslip_generator_forfait.process_payslip_generation_forfait")
    def test_process_payslip_generation_forfait_delegates(self, mock_impl):
        mock_impl.return_value = {"status": "ok", "message": "Forfait", "download_url": None}
        result = process_payslip_generation_forfait("emp-2", 2025, 4)
        mock_impl.assert_called_once_with(employee_id="emp-2", year=2025, month=4)
        assert result["status"] == "ok"


class TestPayslipCommandsSaveAndRestore:
    """save_edited_payslip et restore_payslip_version avec mocks (délégation vers documents.payslip_editor)."""

    @patch("app.modules.payroll.documents.payslip_editor.save_edited_payslip")
    def test_save_edited_payslip_delegates(self, mock_impl):
        mock_impl.return_value = {"payslip_id": "p1", "version": 2}
        result = save_edited_payslip(
            payslip_id="p1",
            new_payslip_data={"brut": 3000},
            changes_summary="Modif",
            current_user_id="u1",
            current_user_name="User",
            pdf_notes="Note",
            internal_note="Int",
        )
        mock_impl.assert_called_once()
        assert result["payslip_id"] == "p1"

    @patch("app.modules.payroll.documents.payslip_editor.restore_payslip_version")
    def test_restore_payslip_version_delegates(self, mock_impl):
        mock_impl.return_value = {"payslip_id": "p1", "restored_version": 1}
        result = restore_payslip_version(
            payslip_id="p1",
            version=1,
            current_user_id="u1",
            current_user_name="User",
        )
        mock_impl.assert_called_once_with(
            payslip_id="p1",
            version=1,
            current_user_id="u1",
            current_user_name="User",
        )
        assert result["restored_version"] == 1


# --- Forfait commands ---


class TestForfaitCommandsDefinirPeriode:
    """definir_periode_de_paie_forfait (ContextePaie appelle Supabase en prod ; on mocke ici)."""

    @patch("app.modules.payroll.application.forfait_commands.ContextePaie")
    @patch("app.modules.payroll.application.forfait_commands.definir_periode_de_paie")
    def test_definir_periode_forfait_returns_two_dates(self, mock_definir, mock_ctx):
        """Retourne (date_debut, date_fin) en déléguant au moteur (mocks pour éviter Supabase)."""
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


class TestForfaitCommandsAnalyserJours:
    """analyser_jours_forfait_du_mois : délègue au engine."""

    @patch(
        "app.modules.payroll.application.forfait_commands._analyser_jours_forfait_impl",
        return_value=[{"jour": 1, "type": "travail", "heures_prevues": 1}],
    )
    def test_analyser_jours_forfait_du_mois_delegates(self, mock_impl):
        planned = [{"annee": 2025, "mois": 1, "jour": 1, "type": "travail", "heures_prevues": 1}]
        actual = [{"annee": 2025, "mois": 1, "jour": 1, "heures_faites": 1}]
        result = analyser_jours_forfait_du_mois(
            planned_data_all_months=planned,
            actual_data_all_months=actual,
            annee=2025,
            mois=1,
            employee_name="Dupont",
        )
        mock_impl.assert_called_once()
        assert len(result) == 1
        assert result[0]["type"] == "travail"


# --- Simulation commands ---


class TestSimulationCommandsReverseCalculation:
    """run_reverse_calculation : calcul inverse net → brut."""

    def test_run_reverse_calculation_invalid_net_raises(self):
        """CalculInverseError est convertie en ValueError par la commande."""
        from app.modules.payroll.engine.calcul_inverse import CalculInverseError
        with patch(
            "app.modules.payroll.engine.calcul_inverse.calculer_brut_depuis_net",
            side_effect=CalculInverseError("Le net cible doit être strictement positif"),
        ):
            with pytest.raises(ValueError, match="net cible"):
                run_reverse_calculation(
                    employee_data={"statut": "Non-cadre"},
                    company_data={},
                    baremes={},
                    calendrier={},
                    saisies={},
                    net_target=0.0,
                    net_type="net_a_payer",
                    options={},
                )

    @patch("app.modules.payroll.engine.calcul_inverse.calculer_brut_depuis_net")
    def test_run_reverse_calculation_returns_dict(self, mock_calc):
        mock_calc.return_value = {
            "brut_calcule": 2500.0,
            "net_obtenu": 1950.0,
            "ecart": 0.0,
            "iterations": 5,
            "convergence": True,
            "bulletin_complet": {},
            "cout_employeur": 3200.0,
        }
        result = run_reverse_calculation(
            employee_data={"statut": "Non-cadre", "taux_prelevement_source": 0},
            company_data={},
            baremes={},
            calendrier={},
            saisies={},
            net_target=1950.0,
            net_type="net_a_payer",
            options={},
        )
        assert result["brut_calcule"] == 2500.0
        assert result["convergence"] is True


class TestSimulationCommandsCreerSimulation:
    """creer_simulation_bulletin : délègue à engine.simulation."""

    @patch("app.modules.payroll.engine.simulation.creer_simulation_bulletin")
    def test_creer_simulation_bulletin_delegates(self, mock_impl):
        mock_impl.return_value = {"bulletin_simule": {"net_a_payer": 2000}}
        result = creer_simulation_bulletin(
            employee_data={"id": "e1"},
            company_data={},
            baremes={},
            month=3,
            year=2025,
            scenario_data={"salaire_brut": 3000},
            prefill_from_real=False,
        )
        mock_impl.assert_called_once()
        assert result["bulletin_simule"]["net_a_payer"] == 2000


class TestSimulationCommandsComparer:
    """comparer_simulation_reel."""

    @patch("app.modules.payroll.engine.simulation.comparer_simulation_reel")
    def test_comparer_simulation_reel_delegates(self, mock_impl):
        mock_impl.return_value = {"ecarts": [], "resume": "OK"}
        result = comparer_simulation_reel(
            bulletin_simule={"net_a_payer": 2000},
            bulletin_reel={"net_a_payer": 2000},
        )
        mock_impl.assert_called_once()
        assert result["resume"] == "OK"


class TestSimulationCommandsScenarios:
    """generer_scenarios_predefinis et get_simulated_payslip_generator."""

    @patch("app.modules.payroll.engine.simulation.generer_scenarios_predefinis")
    def test_generer_scenarios_predefinis_delegates(self, mock_impl):
        mock_impl.return_value = [{"nom": "Scénario 1", "params": {}}]
        result = generer_scenarios_predefinis(employee_data={"id": "e1"})
        mock_impl.assert_called_once_with(employee_data={"id": "e1"})
        assert len(result) == 1
        assert result[0]["nom"] == "Scénario 1"

    def test_get_simulated_payslip_generator_returns_class(self):
        gen_class = get_simulated_payslip_generator()
        assert gen_class is not None
        assert gen_class.__name__ == "SimulatedPayslipGenerator"
        assert hasattr(gen_class, "prepare_simulation_data_for_template")


# --- Indemnités commands ---


class TestIndemnitesCommands:
    """calculer_indemnites_sortie avec supabase mocké."""

    @patch("app.modules.payroll.engine.calculer_indemnites_sortie")
    def test_calculer_indemnites_sortie_delegates(self, mock_impl):
        mock_impl.return_value = {"indemnite_legale": 1000.0, "indemnite_conventionnelle": 500.0}
        result = calculer_indemnites_sortie(
            employee_data={"salaire": 2500, "anciennete_annees": 2},
            exit_data={"type_sortie": "licenciement"},
            supabase_client=MagicMock(),
        )
        assert result["indemnite_legale"] == 1000.0


# --- Exit document commands ---


class TestExitDocumentCommands:
    """get_exit_document_generator."""

    def test_get_exit_document_generator_returns_instance(self):
        gen = get_exit_document_generator()
        assert gen is not None
        assert hasattr(gen, "generate_certificat_travail")
        assert hasattr(gen, "generate_attestation_pole_emploi")
