"""Tests unitaires des règles should_require_* (suivi médical)."""

from datetime import date

from app.modules.medical_follow_up.domain.rules import (
    should_require_aptitude_sir,
    should_require_mi_carriere,
    should_require_vip_periodic,
)


class TestShouldRequireAptitudeSir:
    def test_required_without_sir_history(self):
        assert (
            should_require_aptitude_sir(date(2025, 5, 28), []) is True
        )

    def test_not_required_after_sir_visit(self):
        assert (
            should_require_aptitude_sir(
                date(1996, 10, 1),
                [date(2025, 6, 10)],
            )
            is False
        )

    def test_not_required_after_any_sir_visit(self):
        assert (
            should_require_aptitude_sir(
                date(2025, 5, 28),
                [date(2025, 3, 1)],
            )
            is False
        )

    def test_false_without_hire_date(self):
        assert should_require_aptitude_sir(None, [date(2025, 1, 1)]) is False


class TestShouldRequireMiCarriere:
    def test_not_required_before_45(self):
        today = date(2026, 6, 24)
        birth = date(1990, 1, 1)
        assert (
            should_require_mi_carriere(birth, [], [], [], today) is False
        )

    def test_required_at_45_without_visits(self):
        today = date(2026, 6, 24)
        birth = date(1973, 4, 20)
        assert (
            should_require_mi_carriere(birth, [], [], [], today) is True
        )

    def test_not_required_after_sir_post_45(self):
        today = date(2026, 6, 24)
        birth = date(1973, 4, 20)
        assert (
            should_require_mi_carriere(
                birth,
                [date(2025, 6, 10)],
                [],
                [],
                today,
            )
            is False
        )

    def test_not_required_after_vip_post_45(self):
        today = date(2026, 6, 24)
        birth = date(1978, 8, 1)
        assert (
            should_require_mi_carriere(
                birth,
                [],
                [date(2024, 9, 1)],
                [],
                today,
            )
            is False
        )

    def test_not_required_with_vip_periodic_history(self):
        today = date(2026, 6, 24)
        birth = date(1978, 10, 6)
        assert (
            should_require_mi_carriere(
                birth,
                [],
                [date(2023, 8, 24)],
                [],
                today,
            )
            is False
        )


class TestShouldRequireVipPeriodic:
    def test_not_required_on_sir_post(self):
        assert should_require_vip_periodic(True, []) is False

    def test_required_off_sir_post(self):
        assert should_require_vip_periodic(False, []) is True
