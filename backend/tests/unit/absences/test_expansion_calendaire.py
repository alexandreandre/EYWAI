"""Expansion calendaire des arrêts : helper partagé, schéma API, commande.

Spec : docs/superpowers/specs/2026-09-01-arrets-jours-calendaires-design.md
"""

from datetime import date

from app.shared.domain.absence_calendar import daterange_days


def test_daterange_days_couvre_week_ends_et_bornes():
    # vendredi 14/08/2026 → lundi 17/08/2026 : le week-end est inclus
    jours = daterange_days(date(2026, 8, 14), date(2026, 8, 17))
    assert jours == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_daterange_days_fin_avant_debut_renvoie_le_debut():
    assert daterange_days(date(2026, 8, 17), date(2026, 8, 14)) == [date(2026, 8, 17)]


def test_import_dsn_reexporte_le_helper_partage():
    from app.modules.dsn_import.domain import dsn_absence_exit_mapping

    assert dsn_absence_exit_mapping.daterange_days is daterange_days
