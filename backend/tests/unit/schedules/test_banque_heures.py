"""Tests parseur Banque heures (Cartol)."""

from datetime import date

from app.modules.schedules.application.parsers.banque_heures import (
    is_banque_heures_format,
    try_parse_banque_heures,
)

CARTOL_SAMPLE = """
BANQUE HEURES V1 25/05/2026
000009 DE ABREU Jose Solde HS avant période : 14,00 J 24/11/2024
Date E 1 S 1 E 2 S 2 E 3 S 3 E 4 S 4
Justifiées
27/04/2026 07:00 10:00 10:10 12:00 __:__ __:__ __:__ __:__ 5,00 00:00 00:00 00:00 03:83 05:00 05:00 7,83 -2,83
28/04/2026 07:00 10:00 10:20 12:00 13:00 17:00 __:__ __:__ 8,83 00:00 00:00 00:00 00:00 08:83 08:83 7,83 1,00
04/05/2026 07:00 10:00 10:20 12:00 13:00 17:00 __:__ __:__ 8,83 00:00 00:00 00:00 00:00 08:83 08:83 7,83 1,00
18/2026 35,16 0,00 0,00 3,67 0,00 35,16 35,16 34,99 0,17 14,17
"""


class TestBanqueHeuresFormat:
    def test_detects_format(self):
        assert is_banque_heures_format(CARTOL_SAMPLE)

    def test_rejects_cegid_vertical(self):
        assert not is_banque_heures_format('Pointages "retenu"\nDu 25/05/2026 au 31/05/2026')


class TestBanqueHeuresParse:
    def test_parses_may_days(self):
        result = try_parse_banque_heures(
            CARTOL_SAMPLE, target_year=2026, target_month=5
        )
        assert result.format_detected
        assert result.confidence >= 0.75
        assert len(result.employees) == 1
        emp = result.employees[0]
        assert emp.matricule == "000009"
        assert emp.raw_name == "DE ABREU Jose"
        assert len(emp.days) == 1
        assert emp.days[0].jour == 4
        assert emp.days[0].heures == 8.83

    def test_period_bounds(self):
        result = try_parse_banque_heures(
            CARTOL_SAMPLE, target_year=2026, target_month=4
        )
        assert result.period_start == date(2026, 4, 27)
        assert len(result.employees) == 1
        assert len(result.employees[0].days) == 2
