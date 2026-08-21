"""Tests feuilles hebdomadaires manuscrites DEBUT/FIN."""

from app.modules.schedules.application.employee_match import is_junk_employee_name
from app.modules.schedules.application.handwritten_weekly import (
    FORMAT_HINT,
    calculate_hours_from_range,
    normalize_handwritten_weekly_payload,
    weekday_to_month_day,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    build_page_consensus,
)
from app.modules.schedules.application.timesheet_page_merge import merge_page_results
from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
)


def _employee(name: str, week_number: int = 18) -> dict:
    return {
        "raw_name": name,
        "matricule": None,
        "week_number": week_number,
        "weekly_total_pdf": None,
        "days": [
            {
                "weekday": "lundi",
                "debut": "08:00",
                "fin": "17:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mardi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mercredi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "jeudi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
        ],
    }


def test_s18_weekday_maps_to_may_2026():
    assert (
        weekday_to_month_day(year=2026, month=5, week_number=18, weekday="lundi") == 4
    )
    assert (
        weekday_to_month_day(year=2026, month=5, week_number=18, weekday="vendredi")
        == 8
    )


def test_handwritten_range_hours_are_raw_without_settings():
    """Lot 4 : sans paramétrage société, AUCUNE pause n'est déduite — le
    -1 h en dur a produit des paies fausses silencieuses."""
    assert calculate_hours_from_range("8h", "17h") == 9.0
    assert calculate_hours_from_range("6h45", "16h") == 9.25
    assert calculate_hours_from_range("6h", "18h30") == 12.5


def test_handwritten_range_hours_follow_company_break_settings():
    """Société à horaires variables : 30 min au-delà de 6 h de présence."""
    settings = PunchAccountingSettings(
        enabled=True,
        default_break_deduct_minutes=30,
        break_threshold_minutes=360,
    )

    # 9 h d'amplitude : 30 min de pause, pas l'heure forfaitaire.
    assert calculate_hours_from_range("7h", "16h", settings=settings) == 8.5
    # Demi-journée sous le seuil : aucune pause.
    assert calculate_hours_from_range("8h", "13h", settings=settings) == 5.0
    # Seuil atteint pile : toujours aucune pause.
    assert calculate_hours_from_range("8h", "14h", settings=settings) == 6.0


def test_handwritten_range_hours_ignore_disabled_settings():
    """Réglage désactivé = comme sans réglage : heures brutes."""
    settings = PunchAccountingSettings(enabled=False, default_break_deduct_minutes=30)
    assert calculate_hours_from_range("8h", "17h", settings=settings) == 9.0


def test_normalize_recomputes_hours_when_company_break_configured():
    """Les heures lues par l'IA ne priment pas sur le paramétrage société."""
    settings = PunchAccountingSettings(
        enabled=True,
        default_break_deduct_minutes=30,
        break_threshold_minutes=360,
    )
    payload = {
        "employees": [
            {
                "raw_name": "HUGO",
                "week_number": 18,
                "days": [
                    {
                        "weekday": "lundi",
                        "debut": "07:00",
                        "fin": "16:00",
                        # L'IA a déduit une heure de pause de son côté.
                        "heures": 8.0,
                        "type": "travail",
                    }
                ],
            }
        ]
    }

    normalized = normalize_handwritten_weekly_payload(
        payload, year=2026, month=5, settings=settings
    )

    assert normalized["employees"][0]["days"][0]["heures"] == 8.5


def test_normalize_recomputes_even_without_company_settings():
    """Lot 4 : le serveur recalcule TOUJOURS depuis DEBUT/FIN — l'IA
    appliquait sa propre pause, l'import n'en dépend plus."""
    payload = {
        "employees": [
            {
                "raw_name": "HUGO",
                "week_number": 18,
                "days": [
                    {
                        "weekday": "lundi",
                        "debut": "07:00",
                        "fin": "16:00",
                        "heures": 8.0,
                        "type": "travail",
                    }
                ],
            }
        ]
    }

    normalized = normalize_handwritten_weekly_payload(payload, year=2026, month=5)

    assert normalized["employees"][0]["days"][0]["heures"] == 9.0


def test_hugo_not_junk_for_handwritten_format():
    assert is_junk_employee_name("HUGO")
    assert not is_junk_employee_name("HUGO", format_hint=FORMAT_HINT)


def test_consensus_and_merge_keep_six_handwritten_employees():
    payload = {
        "employees": [
            _employee("HUGO"),
            _employee("MICHEL"),
            _employee("ANTHONY"),
            _employee("LEO"),
            _employee("AURELIEN"),
            _employee("MARION"),
        ],
        "page_period_hint": "S18",
        "confidence": 0.86,
        "warnings": [],
    }

    page = build_page_consensus(
        page_index=1,
        vision_data=payload,
        text_data=None,
        year=2026,
        month=5,
    )
    merged = merge_page_results([page])

    assert [emp.raw_name for emp in merged.employees] == [
        "HUGO",
        "MICHEL",
        "ANTHONY",
        "LEO",
        "AURELIEN",
        "MARION",
    ]
    assert all(len(emp.days) == 4 for emp in merged.employees)
    assert all(emp.days[0]["jour"] == 4 for emp in merged.employees)


def test_consensus_applies_company_break_settings():
    page = build_page_consensus(
        page_index=1,
        vision_data={
            "employees": [_employee("HUGO")],
            "page_period_hint": "S18",
            "confidence": 0.86,
        },
        text_data=None,
        year=2026,
        month=5,
        punch_settings=PunchAccountingSettings(
            enabled=True,
            default_break_deduct_minutes=30,
            break_threshold_minutes=360,
        ),
    )

    # Lundi 08h-17h : 9 h d'amplitude, 30 min de pause société.
    assert page.employees[0].days[0]["heures"] == 8.5
