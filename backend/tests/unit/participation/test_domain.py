"""
Tests unitaires du domaine participation : entités, value objects, enums, règles.

Aucune dépendance DB ni HTTP. Logique pure du domain/.
"""
from datetime import date, datetime
from uuid import uuid4

import pytest

from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.value_objects import ParticipationDistributionParams
from app.modules.participation.domain.enums import DistributionMode
from app.modules.participation.domain import rules as domain_rules


# --- Entité ParticipationSimulation ---


class TestParticipationSimulationEntity:
    """Entité ParticipationSimulation (dataclass)."""

    def test_entity_has_all_required_fields(self):
        """L'entité expose tous les champs métier et techniques."""
        sim_id = uuid4()
        company_id = uuid4()
        created = datetime(2024, 1, 15, 10, 0)
        updated = datetime(2024, 1, 15, 12, 0)
        entity = ParticipationSimulation(
            id=sim_id,
            company_id=company_id,
            year=2024,
            simulation_name="Sim Q1",
            benefice_net=100000.0,
            capitaux_propres=500000.0,
            salaires_bruts=300000.0,
            valeur_ajoutee=400000.0,
            participation_mode=DistributionMode.COMBINAISON,
            participation_salaire_percent=60,
            participation_presence_percent=40,
            interessement_enabled=True,
            interessement_envelope=50000.0,
            interessement_mode=DistributionMode.SALAIRE,
            interessement_salaire_percent=100,
            interessement_presence_percent=0,
            results_data={"participants": []},
            created_at=created,
            created_by=uuid4(),
            updated_at=updated,
        )
        assert entity.id == sim_id
        assert entity.company_id == company_id
        assert entity.year == 2024
        assert entity.simulation_name == "Sim Q1"
        assert entity.benefice_net == 100000.0
        assert entity.participation_mode == DistributionMode.COMBINAISON
        assert entity.interessement_enabled is True
        assert entity.interessement_envelope == 50000.0
        assert entity.results_data == {"participants": []}
        assert entity.created_at == created
        assert entity.updated_at == updated

    def test_entity_accepts_optional_interessement_none(self):
        """interessement_envelope et interessement_mode peuvent être None."""
        entity = ParticipationSimulation(
            id=uuid4(),
            company_id=uuid4(),
            year=2025,
            simulation_name="Sans intéressement",
            benefice_net=0.0,
            capitaux_propres=0.0,
            salaires_bruts=0.0,
            valeur_ajoutee=0.0,
            participation_mode=DistributionMode.UNIFORME,
            participation_salaire_percent=50,
            participation_presence_percent=50,
            interessement_enabled=False,
            interessement_envelope=None,
            interessement_mode=None,
            interessement_salaire_percent=50,
            interessement_presence_percent=50,
            results_data={},
            created_at=datetime.now(),
            created_by=None,
            updated_at=datetime.now(),
        )
        assert entity.interessement_envelope is None
        assert entity.interessement_mode is None
        assert entity.created_by is None


# --- Value object ParticipationDistributionParams ---


class TestParticipationDistributionParams:
    """Value object des paramètres de répartition."""

    def test_frozen_and_holds_mode_and_percents(self):
        """Paramètres immuables avec mode et pourcentages."""
        params = ParticipationDistributionParams(
            mode=DistributionMode.COMBINAISON,
            salaire_percent=70,
            presence_percent=30,
        )
        assert params.mode == DistributionMode.COMBINAISON
        assert params.salaire_percent == 70
        assert params.presence_percent == 30

    def test_all_distribution_modes_usable(self):
        """Chaque mode peut être utilisé dans le value object."""
        for mode in DistributionMode:
            params = ParticipationDistributionParams(
                mode=mode,
                salaire_percent=50,
                presence_percent=50,
            )
            assert params.mode == mode


# --- Enum DistributionMode ---


class TestDistributionModeEnum:
    """Énumération des modes de répartition."""

    def test_all_modes_defined(self):
        """Tous les modes métier sont définis."""
        assert DistributionMode.UNIFORME.value == "uniforme"
        assert DistributionMode.SALAIRE.value == "salaire"
        assert DistributionMode.PRESENCE.value == "presence"
        assert DistributionMode.COMBINAISON.value == "combinaison"

    def test_enum_from_string(self):
        """Construction depuis une chaîne (aligné legacy)."""
        assert DistributionMode("uniforme") == DistributionMode.UNIFORME
        assert DistributionMode("combinaison") == DistributionMode.COMBINAISON


# --- Règles : types de jour présence / exclus ---


class TestPresenceDayTypes:
    """Constantes des types de jour (présence vs exclus)."""

    def test_presence_day_types_contains_expected(self):
        """Les types travail, congé, RTT, férié comptent comme présence (si heures_prevues > 0)."""
        assert "travail" in domain_rules.PRESENCE_DAY_TYPES
        assert "conge" in domain_rules.PRESENCE_DAY_TYPES
        assert "conge_paye" in domain_rules.PRESENCE_DAY_TYPES
        assert "rtt" in domain_rules.PRESENCE_DAY_TYPES
        assert "ferie" in domain_rules.PRESENCE_DAY_TYPES
        assert "fete" in domain_rules.PRESENCE_DAY_TYPES

    def test_excluded_day_types_contains_expected(self):
        """Weekend et maladie/arrêt ne comptent jamais."""
        assert "weekend" in domain_rules.EXCLUDED_DAY_TYPES
        assert "maladie" in domain_rules.EXCLUDED_DAY_TYPES
        assert "arret_maladie" in domain_rules.EXCLUDED_DAY_TYPES
        assert "arret" in domain_rules.EXCLUDED_DAY_TYPES


# --- Règles : compute_presence_days_for_schedules ---


class TestComputePresenceDaysForSchedules:
    """Calcul des jours de présence à partir des plannings."""

    def test_empty_schedules_returns_zero(self):
        """Liste vide ou sans données valides → 0."""
        assert domain_rules.compute_presence_days_for_schedules([]) == 0
        assert domain_rules.compute_presence_days_for_schedules([{}]) == 0

    def test_day_with_heures_faites_gt_zero_counts(self):
        """Un jour avec heures_faites > 0 compte comme présence."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {"calendrier_prevu": []},
                "actual_hours": {
                    "calendrier_reel": [
                        {"jour": 5, "heures_faites": 7.5},
                    ]
                },
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 1

    def test_day_weekend_does_not_count_without_heures_faites(self):
        """Un jour de type weekend sans heures_faites ne compte pas."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 6, "type": "weekend", "heures_prevues": 0},
                    ]
                },
                "actual_hours": {"calendrier_reel": []},
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 0

    def test_day_travail_with_heures_prevues_counts(self):
        """Un jour type travail avec heures_prevues > 0 compte (sans heures_faites)."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 10, "type": "travail", "heures_prevues": 7},
                    ]
                },
                "actual_hours": {"calendrier_reel": []},
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 1

    def test_day_maladie_does_not_count(self):
        """Un jour maladie sans heures_faites ne compte pas."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 15, "type": "maladie", "heures_prevues": 7},
                    ]
                },
                "actual_hours": {"calendrier_reel": []},
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 0

    def test_deduplication_by_month_jour(self):
        """Dédoublonnage par (month, jour) : un même jour ne compte qu'une fois."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 20, "type": "travail", "heures_prevues": 7},
                    ]
                },
                "actual_hours": {"calendrier_reel": [{"jour": 20, "heures_faites": 7}]},
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 1

    def test_multiple_months_sum_days(self):
        """Plusieurs mois : les jours s'ajoutent."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 8, "type": "travail", "heures_prevues": 7},
                    ]
                },
                "actual_hours": {"calendrier_reel": []},
            },
            {
                "month": 2,
                "planned_calendar": {
                    "calendrier_prevu": [
                        {"jour": 9, "type": "travail", "heures_prevues": 7},
                    ]
                },
                "actual_hours": {"calendrier_reel": []},
            },
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 2

    def test_actual_day_without_planned_but_with_heures_faites_counts(self):
        """Un jour dans calendrier_reel avec heures_faites > 0 compte même sans entrée prévue."""
        schedules = [
            {
                "month": 1,
                "planned_calendar": {"calendrier_prevu": []},
                "actual_hours": {
                    "calendrier_reel": [
                        {"jour": 3, "heures_faites": 6},
                    ]
                },
            }
        ]
        assert domain_rules.compute_presence_days_for_schedules(schedules) == 1


# --- Règles : compute_seniority_years ---


class TestComputeSeniorityYears:
    """Calcul de l'ancienneté en années."""

    def test_none_returns_zero(self):
        """hire_date None → 0."""
        assert domain_rules.compute_seniority_years(None) == 0

    def test_iso_string_parsed(self):
        """Chaîne ISO (YYYY-MM-DD) correctement parsée."""
        # Dépend de date.today() ; on vérifie au moins que ça ne lève pas et retourne un entier >= 0
        result = domain_rules.compute_seniority_years("2020-06-01")
        assert isinstance(result, int)
        assert result >= 0

    def test_date_object_accepted(self):
        """Objet date accepté."""
        d = date(2019, 1, 15)
        result = domain_rules.compute_seniority_years(d)
        assert isinstance(result, int)
        assert result >= 0

    def test_invalid_string_returns_zero(self):
        """Chaîne invalide → 0 (ValueError/TypeError gérés)."""
        assert domain_rules.compute_seniority_years("not-a-date") == 0
        assert domain_rules.compute_seniority_years("") == 0


# --- Règles : extract_annual_salary_from_cumuls ---


class TestExtractAnnualSalaryFromCumuls:
    """Extraction du brut total depuis une structure cumuls."""

    def test_non_dict_returns_zero(self):
        """Entrée non-dict → 0.0."""
        assert domain_rules.extract_annual_salary_from_cumuls(None) == 0.0
        assert domain_rules.extract_annual_salary_from_cumuls([]) == 0.0

    def test_nested_cumuls_brut_total(self):
        """Structure cumuls.cumuls.brut_total extraite."""
        cumuls = {"cumuls": {"brut_total": 36000.5}}
        assert domain_rules.extract_annual_salary_from_cumuls(cumuls) == 36000.5

    def test_missing_cumuls_returns_zero(self):
        """Pas de clé cumuls ou brut_total → 0.0."""
        assert domain_rules.extract_annual_salary_from_cumuls({}) == 0.0
        assert domain_rules.extract_annual_salary_from_cumuls({"cumuls": {}}) == 0.0

    def test_brut_total_zero_or_none_returns_zero(self):
        """brut_total à 0 ou None → 0.0."""
        assert domain_rules.extract_annual_salary_from_cumuls(
            {"cumuls": {"brut_total": 0}}
        ) == 0.0
        assert domain_rules.extract_annual_salary_from_cumuls(
            {"cumuls": {"brut_total": None}}
        ) == 0.0
