"""
Tests unitaires du domaine CSE : entités, value objects et règles.

Aucune dépendance DB ni HTTP. Logique pure du domain/.
"""

from datetime import date

import pytest

from app.modules.cse.domain.entities import ElectedMemberId, MeetingId
from app.modules.cse.domain import rules as domain_rules


# --- Entités (value objects) ---


class TestElectedMemberId:
    """Value object ElectedMemberId."""

    def test_creates_with_value(self):
        """ElectedMemberId stocke la valeur fournie."""
        eid = ElectedMemberId(value="mem-123")
        assert eid.value == "mem-123"

    def test_is_frozen(self):
        """ElectedMemberId est immuable."""
        eid = ElectedMemberId(value="mem-1")
        with pytest.raises(Exception):
            eid.value = "other"


class TestMeetingId:
    """Value object MeetingId."""

    def test_creates_with_value(self):
        """MeetingId stocke la valeur fournie."""
        mid = MeetingId(value="mtg-456")
        assert mid.value == "mtg-456"

    def test_is_frozen(self):
        """MeetingId est immuable."""
        mid = MeetingId(value="mtg-1")
        with pytest.raises(Exception):
            mid.value = "other"


# --- Règles : validate_mandate_dates ---


class TestValidateMandateDates:
    """Règle validate_mandate_dates : dates de mandat cohérentes."""

    def test_valid_dates_do_not_raise(self):
        """start_date <= end_date : pas d'exception."""
        domain_rules.validate_mandate_dates(
            date(2024, 1, 1),
            date(2026, 12, 31),
        )
        domain_rules.validate_mandate_dates(
            date(2024, 6, 15),
            date(2024, 6, 15),
        )

    def test_end_before_start_raises_value_error(self):
        """end_date < start_date → ValueError."""
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_mandate_dates(
                date(2026, 12, 31),
                date(2024, 1, 1),
            )
        assert "date de fin" in str(exc_info.value).lower()
        assert "date de début" in str(exc_info.value).lower()


# --- Règles : election_alert_level ---


class TestElectionAlertLevel:
    """Niveau d'alerte électorale selon les jours restants (J-180, J-90, J-30)."""

    def test_more_than_180_days_returns_none(self):
        """Plus de 180 jours → pas d'alerte."""
        assert domain_rules.election_alert_level(181) is None
        assert domain_rules.election_alert_level(365) is None

    def test_181_to_180_days_returns_info(self):
        """J-180 à J-91 → info."""
        assert domain_rules.election_alert_level(180) == "info"
        assert domain_rules.election_alert_level(91) == "info"

    def test_90_to_31_days_returns_warning(self):
        """J-90 à J-31 → warning."""
        assert domain_rules.election_alert_level(90) == "warning"
        assert domain_rules.election_alert_level(31) == "warning"

    def test_30_to_1_days_returns_critical(self):
        """J-30 à J-1 → critical."""
        assert domain_rules.election_alert_level(30) == "critical"
        assert domain_rules.election_alert_level(1) == "critical"

    def test_zero_or_negative_returns_critical(self):
        """J-0 ou mandat terminé → critical."""
        assert domain_rules.election_alert_level(0) == "critical"
        assert domain_rules.election_alert_level(-1) == "critical"


# --- Règles : election_alert_message ---


class TestElectionAlertMessage:
    """Message d'alerte électorale."""

    def test_zero_or_negative_days_returns_terminated_message(self):
        """J <= 0 → message mandat terminé."""
        msg = domain_rules.election_alert_message(0)
        assert "aujourd'hui" in msg.lower() or "terminé" in msg.lower()
        msg_neg = domain_rules.election_alert_message(-5)
        assert "aujourd'hui" in msg_neg.lower() or "terminé" in msg_neg.lower()

    def test_positive_days_returns_remaining_message(self):
        """J > 0 → message avec nombre de jours restants."""
        msg = domain_rules.election_alert_message(45)
        assert "45" in msg
        assert "jours" in msg.lower()
        assert "termine" in msg.lower() or "terminer" in msg.lower()
