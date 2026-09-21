"""Un aperçu resservi depuis le cache est re-rapproché avec le roster du jour.

Constat du 21/09/2026 : la première extraction de S26/S27 avait un roster sans
Demory (sorti le 24/07) ; la seconde, roster complet, a resservi l'aperçu en
cache — rapprochement figé compris — et Demory restait « texte OCR non salarié ».
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    RosterEmployee,
)

pytestmark = pytest.mark.unit

ROSTER = [
    RosterEmployee(id="e-hugo", first_name="Hugo", last_name="FUCKAR"),
    RosterEmployee(id="e-demory", first_name="Aurélien", last_name="DEMORY"),
]


def _apercu_fige() -> AiCalendarProposalResponse:
    return AiCalendarProposalResponse(
        year=2026,
        month=7,
        source="relevé IA hybride",
        detected_format="handwritten_weekly",
        employees=[
            AiEmployeeProposal(
                raw_name="HUGO",
                employee_id="e-hugo",
                matched_name="Hugo FUCKAR",
                match_method="name_exact",
                match_confidence="medium",
                review_status="warning",
                warnings=["Prénom seul « HUGO » rapproché de Hugo FUCKAR."],
                days=[AiDayEntry(jour=29, heures=8.5, type="travail", nature="reel", year=2026, month=6)],
                days_expected_count=5,
                days_imported_count=1,
                coverage_ratio=0.2,
            ),
            AiEmployeeProposal(
                raw_name="AURELIEN",
                employee_id=None,
                match_method="none",
                match_confidence="none",
                review_status="error",
                warnings=["Ligne ignorée (texte OCR non salarié) : « AURELIEN »."],
                days=[AiDayEntry(jour=29, heures=8.5, type="travail", nature="reel", year=2026, month=6)],
                days_expected_count=5,
                days_imported_count=1,
                coverage_ratio=0.2,
            ),
        ],
        review_summary={"ready": 0, "warning": 1, "error": 1, "empty": 0, "incomplete": 0, "gap": 0, "total": 2},
    )


def test_le_rerapprochement_retrouve_un_salarie_ajoute_au_roster():
    from app.modules.schedules.application.employee_match import rematch_proposal_employees

    apercu = rematch_proposal_employees(_apercu_fige(), ROSTER)

    aurelien = next(e for e in apercu.employees if e.raw_name == "AURELIEN")
    assert aurelien.employee_id == "e-demory"
    assert aurelien.review_status == "warning"
    assert aurelien.days[0].heures == 8.5 and aurelien.days[0].month == 6
    assert not any("Ligne ignorée" in w for w in aurelien.warnings)
    assert apercu.review_summary["error"] == 0 and apercu.review_summary["warning"] == 2


def test_le_rerapprochement_ne_perd_pas_les_jours_ni_les_comptes():
    from app.modules.schedules.application.employee_match import rematch_proposal_employees

    apercu = rematch_proposal_employees(_apercu_fige(), ROSTER)

    hugo = next(e for e in apercu.employees if e.raw_name == "HUGO")
    assert (hugo.employee_id, hugo.days_expected_count, hugo.days_imported_count, hugo.coverage_ratio) == (
        "e-hugo", 5, 1, 0.2
    )


@patch("app.modules.schedules.application.timesheet_import.parse_service.create_batch_from_proposal")
@patch("app.modules.schedules.application.timesheet_import.parse_service.enrich_roster_time_tracking_ids", side_effect=lambda r, c: r)
@patch("app.modules.schedules.application.timesheet_import.parse_service.find_cached_preview")
def test_le_chemin_en_cache_rerapproche_avec_le_roster_du_jour(mock_cache, _enrich, mock_batch):
    from app.modules.schedules.application.timesheet_import.parse_service import parse_with_llm_fallback

    mock_cache.return_value = _apercu_fige()
    mock_batch.return_value = {"id": "b-cache"}

    proposal, batch_id = parse_with_llm_fallback(
        company_id="c1", user_id=None, content=b"pdf", filename="semaine-27.pdf",
        year=2026, month=7, roster=ROSTER, week_anchor_date=date(2026, 6, 29),
    )

    assert batch_id == "b-cache"
    assert next(e for e in proposal.employees if e.raw_name == "AURELIEN").employee_id == "e-demory"
    assert mock_cache.call_args.kwargs["week_anchor_date"] == date(2026, 6, 29)
    assert mock_batch.call_args.kwargs["proposal"] is proposal
