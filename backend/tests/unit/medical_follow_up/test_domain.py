"""
Tests unitaires du domaine medical_follow_up : entités, règles, enums.

Aucune dépendance DB ni HTTP. Logique pure du domain/.
"""
from datetime import date

import pytest

from app.modules.medical_follow_up.domain.entities import MedicalObligation
from app.modules.medical_follow_up.domain.enums import (
    ObligationStatus,
    TriggerType,
    VisitType,
)
from app.modules.medical_follow_up.domain.rules import compute_kpis_from_rows


# --- Entité MedicalObligation ---


class TestMedicalObligationEntity:
    """Entité MedicalObligation : champs requis et optionnels."""

    def test_entity_has_required_fields(self):
        """L'entité possède tous les champs requis."""
        ob = MedicalObligation(
            id="obl-1",
            company_id="co-1",
            employee_id="emp-1",
            visit_type="vip",
            trigger_type="periodicite_vip",
            due_date="2025-06-01",
            priority=1,
            status="a_faire",
            rule_source="legal",
        )
        assert ob.id == "obl-1"
        assert ob.company_id == "co-1"
        assert ob.employee_id == "emp-1"
        assert ob.visit_type == "vip"
        assert ob.trigger_type == "periodicite_vip"
        assert ob.due_date == "2025-06-01"
        assert ob.priority == 1
        assert ob.status == "a_faire"
        assert ob.rule_source == "legal"
        assert ob.justification is None
        assert ob.planned_date is None
        assert ob.completed_date is None

    def test_entity_accepts_optional_fields(self):
        """L'entité accepte justification, planned_date, completed_date, etc."""
        ob = MedicalObligation(
            id="obl-2",
            company_id="co-1",
            employee_id="emp-2",
            visit_type="demande",
            trigger_type="demande",
            due_date="2025-07-15",
            priority=3,
            status="planifiee",
            rule_source="legal",
            justification="Visite programmée",
            planned_date="2025-07-10",
            completed_date=None,
            collective_agreement_idcc="1234",
            request_motif="Demande salarié",
            request_date="2025-06-01",
        )
        assert ob.justification == "Visite programmée"
        assert ob.planned_date == "2025-07-10"
        assert ob.collective_agreement_idcc == "1234"
        assert ob.request_motif == "Demande salarié"
        assert ob.request_date == "2025-06-01"


# --- Règles compute_kpis_from_rows ---


class TestComputeKpisFromRows:
    """Règle compute_kpis_from_rows : calcul des indicateurs à partir des lignes."""

    def test_empty_rows_returns_zeros(self):
        """Liste vide → tous les KPIs à 0."""
        today = date(2025, 3, 17)
        result = compute_kpis_from_rows([], today)
        assert result["overdue_count"] == 0
        assert result["due_within_30_count"] == 0
        assert result["active_total"] == 0
        assert result["completed_this_month"] == 0

    def test_overdue_count_excludes_realisee(self):
        """En retard : due_date < today et status != realisee."""
        today = date(2025, 3, 17)
        today_iso = today.isoformat()
        rows = [
            {"due_date": "2025-03-01", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-03-10", "status": "planifiee", "completed_date": None},
            {"due_date": "2025-03-05", "status": "realisee", "completed_date": "2025-03-06"},
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["overdue_count"] == 2  # a_faire et planifiee, pas realisee

    def test_due_within_30_count(self):
        """À échéance sous 30 jours : today <= due_date <= today+30, status != realisee."""
        today = date(2025, 3, 17)
        rows = [
            {"due_date": "2025-03-17", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-04-15", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-04-20", "status": "a_faire", "completed_date": None},  # > 30 j
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["due_within_30_count"] == 2

    def test_active_total_excludes_realisee_and_annulee(self):
        """Total actif : toutes les lignes dont status != realisee (annulée exclue par convention)."""
        today = date(2025, 3, 17)
        rows = [
            {"due_date": "2025-04-01", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-04-02", "status": "planifiee", "completed_date": None},
            {"due_date": "2025-03-01", "status": "realisee", "completed_date": "2025-03-10"},
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["active_total"] == 2

    def test_completed_this_month(self):
        """Réalisées ce mois : status == realisee et completed_date >= début du mois."""
        today = date(2025, 3, 17)
        month_start = "2025-03-01"
        rows = [
            {"due_date": "2025-02-01", "status": "realisee", "completed_date": "2025-03-05"},
            {"due_date": "2025-02-15", "status": "realisee", "completed_date": "2025-02-20"},
            {"due_date": "2025-03-01", "status": "realisee", "completed_date": "2025-03-01"},
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["completed_this_month"] == 2  # 2025-03-05 et 2025-03-01

    def test_row_without_due_date_not_counted_for_overdue_or_due_within(self):
        """Lignes sans due_date ne comptent pas pour overdue ni due_within_30."""
        today = date(2025, 3, 17)
        rows = [
            {"status": "a_faire", "completed_date": None},
            {"due_date": None, "status": "a_faire", "completed_date": None},
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["overdue_count"] == 0
        assert result["due_within_30_count"] == 0
        assert result["active_total"] == 2

    def test_full_kpis_scenario(self):
        """Scénario complet : mélange retard, à venir, réalisées ce mois."""
        today = date(2025, 3, 17)
        rows = [
            {"due_date": "2025-03-01", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-04-01", "status": "a_faire", "completed_date": None},
            {"due_date": "2025-03-10", "status": "realisee", "completed_date": "2025-03-12"},
        ]
        result = compute_kpis_from_rows(rows, today)
        assert result["overdue_count"] == 1
        assert result["due_within_30_count"] == 1
        assert result["active_total"] == 2
        assert result["completed_this_month"] == 1


# --- Enums ---


class TestVisitType:
    """Enum VisitType."""

    def test_values_are_strings(self):
        """Les valeurs sont des chaînes (StrEnum)."""
        assert VisitType.VIP == "vip"
        assert VisitType.SIR == "sir"
        assert VisitType.REPRISE == "reprise"
        assert VisitType.DEMANDE == "demande"
        assert VisitType.MI_CARRIERE_45 == "mi_carriere_45"

    def test_aptitude_sir_and_vip_mineur_nuit(self):
        """Types spécifiques SIR / VIP mineur nuit."""
        assert VisitType.APTITUDE_SIR_AVANT_AFFECTATION == "aptitude_sir_avant_affectation"
        assert VisitType.VIP_AVANT_AFFECTATION_MINEUR_NUIT == "vip_avant_affectation_mineur_nuit"


class TestObligationStatus:
    """Enum ObligationStatus."""

    def test_status_values(self):
        """Statuts a_faire, planifiee, realisee, annulee."""
        assert ObligationStatus.A_FAIRE == "a_faire"
        assert ObligationStatus.PLANIFIEE == "planifiee"
        assert ObligationStatus.REALISEE == "realisee"
        assert ObligationStatus.ANNULEE == "annulee"


class TestTriggerType:
    """Enum TriggerType."""

    def test_trigger_values(self):
        """Déclencheurs poste_sir, periodicite_vip, demande, etc."""
        assert TriggerType.POSTE_SIR == "poste_sir"
        assert TriggerType.PERIODICITE_VIP == "periodicite_vip"
        assert TriggerType.PERIODICITE_SIR == "periodicite_sir"
        assert TriggerType.DEMANDE == "demande"
        assert TriggerType.EMBANCHE == "embauche"
        assert TriggerType.ARRET_LONG == "arret_long"
        assert TriggerType.AGE_45 == "age_45"
        assert TriggerType.NUIT_MINEUR == "nuit_mineur"
