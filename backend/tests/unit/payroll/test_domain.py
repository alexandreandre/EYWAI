"""
Tests unitaires du domaine payroll (entités, value objects, règles).

Le module payroll a des placeholders dans domain/ (entities, value_objects, rules, enums).
La logique métier pure (sans DB, sans HTTP) est dans application (is_forfait_jour) et engine
(période de paie forfait, coefficient net/brut). Ces tests couvrent tout le comportement
"domaine" exposé par le module.
"""

from datetime import date

import pytest

from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.payroll.engine.period_forfait import (
    _get_end_date_for_month,
    definir_periode_de_paie,
)
from app.modules.payroll.engine.calcul_inverse import estimer_coefficient_net_brut


pytestmark = pytest.mark.unit


class TestDomainImports:
    """Vérification que le package domain s'importe sans erreur."""

    def test_domain_package_imports(self):
        """Le package domain et ses sous-modules sont importables."""
        from app.modules.payroll import domain

        assert domain is not None

    def test_domain_entities_placeholder(self):
        """domain.entities est un placeholder (pas d'entités métier pour l'instant)."""
        from app.modules.payroll.domain import entities

        assert entities is not None

    def test_domain_value_objects_placeholder(self):
        """domain.value_objects est un placeholder."""
        from app.modules.payroll.domain import value_objects

        assert value_objects is not None

    def test_domain_rules_placeholder(self):
        """domain.rules est un placeholder."""
        from app.modules.payroll.domain import rules

        assert rules is not None

    def test_domain_enums_placeholder(self):
        """domain.enums est un placeholder."""
        from app.modules.payroll.domain import enums

        assert enums is not None


class TestIsForfaitJour:
    """Règle métier : détection forfait jour selon le statut employé."""

    def test_forfait_jour_detected_lowercase(self):
        """Statut contenant 'forfait jour' en minuscules → True."""
        assert is_forfait_jour("Cadre forfait jour") is True
        assert is_forfait_jour("forfait jour") is True

    def test_forfait_jour_detected_mixed_case(self):
        """Statut contenant 'Forfait Jour' → True (comparaison insensible à la casse)."""
        assert is_forfait_jour("Forfait Jour") is True

    def test_non_forfait_returns_false(self):
        """Statut sans 'forfait jour' → False."""
        assert is_forfait_jour("Cadre") is False
        assert is_forfait_jour("Non-Cadre") is False
        assert is_forfait_jour("Agent de maîtrise") is False

    def test_none_statut_returns_false(self):
        """Statut None → False."""
        assert is_forfait_jour(None) is False

    def test_empty_string_returns_false(self):
        """Chaîne vide → False."""
        assert is_forfait_jour("") is False


class TestPeriodForfaitGetEndDate:
    """Règles de calcul de la date de fin de période (forfait jour)."""

    def test_get_end_date_first_monday_january_2025(self):
        """Premier lundi de janvier 2025 = 6."""
        result = _get_end_date_for_month(2025, 1, 0, 1)
        assert result == date(2025, 1, 6)

    def test_get_end_date_last_friday_january_2025(self):
        """Dernier vendredi de janvier 2025 (jour 4, occurrence -1)."""
        result = _get_end_date_for_month(2025, 1, 4, -1)
        assert result == date(2025, 1, 31)

    def test_get_end_date_second_wednesday_march_2025(self):
        """Deuxième mercredi de mars 2025 (jour 2, occurrence 2)."""
        result = _get_end_date_for_month(2025, 3, 2, 2)
        assert result == date(2025, 3, 12)

    def test_get_end_date_invalid_occurrence_raises(self):
        """Occurrence invalide (ex. 10 pour un mois avec 4 lundis) → ValueError."""
        with pytest.raises(ValueError, match="invalide"):
            _get_end_date_for_month(2025, 1, 0, 10)


class TestDefinirPeriodeDePaie:
    """Période de paie forfait : dates début/fin à partir du contexte."""

    def test_definir_periode_janvier_2025(self):
        """Période de paie pour janvier 2025 avec paramètres par défaut (vendredi avant-dernier)."""

        # Contexte minimal : jour_de_fin=4 (vendredi), occurrence=-2 (avant-dernier)
        class ContexteMinimal:
            entreprise = {
                "parametres_paie": {
                    "periode_de_paie": {"jour_de_fin": 4, "occurrence": -2},
                }
            }

        ctx = ContexteMinimal()
        date_debut, date_fin = definir_periode_de_paie(ctx, 2025, 1)
        assert date_debut is not None
        assert date_fin is not None
        assert date_debut < date_fin
        assert date_debut.month in (12, 1) and date_fin.month in (1, 2)

    def test_definir_periode_utilise_regles_contexte(self):
        """La période dépend des paramètres entreprise (jour_de_fin, occurrence)."""

        class ContexteLundiDernier:
            entreprise = {
                "parametres_paie": {
                    "periode_de_paie": {"jour_de_fin": 0, "occurrence": -1},
                }
            }

        ctx = ContexteLundiDernier()
        date_debut, date_fin = definir_periode_de_paie(ctx, 2025, 3)
        assert date_debut is not None
        assert date_fin is not None
        # La période s'arrête le dimanche de la semaine du jour de référence
        assert date_fin.weekday() == 6  # Dimanche


class TestEstimerCoefficientNetBrut:
    """Coefficient de conversion net/brut (calcul inverse)."""

    def test_cadre_coefficient(self):
        """Statut Cadre → coefficient ~1.30."""
        coef = estimer_coefficient_net_brut("Cadre", 0.0)
        assert coef == 1.30

    def test_non_cadre_coefficient(self):
        """Statut Non-cadre → coefficient ~1.28."""
        coef = estimer_coefficient_net_brut("Non-cadre", 0.0)
        assert coef == 1.28

    def test_unknown_statut_defaults_to_non_cadre(self):
        """Statut inconnu → défaut 1.28."""
        coef = estimer_coefficient_net_brut("Autre", 0.0)
        assert coef == 1.28

    def test_taux_pas_increases_coefficient(self):
        """Taux PAS > 0 augmente le coefficient."""
        coef_sans = estimer_coefficient_net_brut("Non-cadre", 0.0)
        coef_avec = estimer_coefficient_net_brut("Non-cadre", 10.0)
        assert coef_avec > coef_sans
