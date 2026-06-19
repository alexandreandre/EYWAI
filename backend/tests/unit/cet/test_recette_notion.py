"""Tests recette soldes CET (capture Elsa / Notion)."""

from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cet_balance_days,
    compute_running_balance_days,
    HOURS_PER_REST_DAY_DEFAULT,
)

# Données anonymisées inspirées du tableau Notion (Faucher, Kocis, etc.)
NOTION_SAMPLE = [
    ("2025-03-01", "deposit_cp", 10.0, "validated"),
    ("2026-06-04", "deposit_cp", 15.0, "validated"),
]


def _rows(sample: list[tuple]) -> list[CetMovementRow]:
    return [
        CetMovementRow(
            movement_type=t[1],
            hours=0,
            days=t[2],
            status=t[3],
            year=int(t[0][:4]),
        )
        for t in sample
    ]


def test_notion_faucher_like_balance():
    rows = _rows(NOTION_SAMPLE)
    balances = compute_running_balance_days(
        rows, hours_per_rest_day=HOURS_PER_REST_DAY_DEFAULT
    )
    assert balances[-1] == 25.0
    assert compute_cet_balance_days(rows) == 25.0


def test_notion_kocis_partial():
    rows = _rows([("2025-03-01", "deposit_cp", 5.0, "validated")])
    assert compute_cet_balance_days(rows) == 5.0
