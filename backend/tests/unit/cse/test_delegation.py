"""
Tests unitaires — calcul heures de délégation CSE (domain).
"""

from datetime import date

from app.modules.cse.domain.delegation import (
    MonthlyBalanceInput,
    compute_monthly_balance,
    compute_rolling_balances,
    credit_base,
    validate_transfer,
)
from app.modules.cse.domain.delegation_bareme import (
    heures_mensuelles_legales,
    lookup_bareme_row,
)


class TestBaremeR2314:
    def test_effectif_11_24(self):
        assert heures_mensuelles_legales(15) == 10.0
        row = lookup_bareme_row(15)
        assert row is not None
        assert row.nb_titulaires == 1

    def test_effectif_50_74(self):
        assert heures_mensuelles_legales(60) == 18.0

    def test_effectif_10000_plus(self):
        assert heures_mensuelles_legales(10000) == 34.0

    def test_effectif_sous_11(self):
        assert heures_mensuelles_legales(5) == 0.0
        assert lookup_bareme_row(5) is None


class TestCreditBase:
    def test_titulaire_bareme(self):
        assert credit_base("titulaire", 100, None) == 21.0

    def test_secretaire_comme_titulaire(self):
        assert credit_base("secretaire", 100, None) == 21.0

    def test_suppleant_zero(self):
        assert credit_base("suppleant", 100, None) == 0.0

    def test_override_prioritaire(self):
        assert credit_base("titulaire", 100, 30.0) == 30.0


class TestMonthlyBalance:
    def test_restant_simple(self):
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=2026,
                month=6,
                role="titulaire",
                reference_headcount=100,
                consumed_hours=5.0,
            )
        )
        assert detail.credit_base == 21.0
        assert detail.monthly_cap == 31.5
        assert detail.remaining_hours == 16.0
        assert detail.overrun_hours == 0.0

    def test_plafond_1_5x(self):
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=2026,
                month=6,
                role="titulaire",
                reference_headcount=100,
                report_enabled=True,
                prior_monthly_unused={(2026, 5): 50.0},
                consumed_hours=0.0,
            )
        )
        assert detail.available_hours == 31.5

    def test_depassement(self):
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=2026,
                month=6,
                role="titulaire",
                reference_headcount=100,
                consumed_hours=25.0,
            )
        )
        assert detail.overrun_hours == 4.0
        assert detail.is_over_limit is True

    def test_report_12_mois(self):
        prior = {(2025, m): 2.0 for m in range(7, 13)}
        prior.update({(2026, m): 1.0 for m in range(1, 6)})
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=2026,
                month=6,
                role="titulaire",
                reference_headcount=100,
                report_enabled=True,
                prior_monthly_unused=prior,
            )
        )
        assert detail.reported_available == 17.0  # 6×2 (2025-07→12) + 5×1 (2026-01→05)


class TestRollingBalances:
    def test_enchaine_les_reports(self):
        balances = compute_rolling_balances(
            role="titulaire",
            reference_headcount=100,
            monthly_hours_override=None,
            report_enabled=True,
            mutualisation_enabled=True,
            monthly_consumed={(2026, 1): 10.0, (2026, 2): 5.0},
            monthly_transfers_in={},
            monthly_transfers_out={},
            months=[(2026, 1), (2026, 2)],
        )
        jan = balances[(2026, 1)]
        feb = balances[(2026, 2)]
        assert jan.remaining_hours == 11.0
        assert feb.reported_available == 11.0


class TestValidateTransfer:
    def test_cedant_doit_etre_titulaire(self):
        ok, msgs = validate_transfer(
            from_role="suppleant",
            from_credit_base=0,
            to_credit_base=21,
            hours=5,
            to_month_consumed=0,
            to_month_transfers_in=0,
            to_month_reported=0,
            employer_notified_at=None,
            usage_date=date(2026, 6, 1),
        )
        assert ok is False
        assert "titulaire" in msgs[0].lower()

    def test_avertissement_info_employeur(self):
        ok, warnings = validate_transfer(
            from_role="titulaire",
            from_credit_base=21,
            to_credit_base=21,
            hours=5,
            to_month_consumed=0,
            to_month_transfers_in=0,
            to_month_reported=0,
            employer_notified_at=None,
            usage_date=date(2026, 6, 15),
        )
        assert ok is True
        assert any("employeur" in w.lower() for w in warnings)
