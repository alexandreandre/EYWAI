"""
Tests unitaires de la saisie assistée du calendrier (application/ai_fill.py).

Le LLM (extract_structured_json) et la configuration IA sont mockés :
aucun appel réseau, aucune DB.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application import ai_fill
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import RosterEmployee
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult


ROSTER = [
    RosterEmployee(id="e1", first_name="Paul", last_name="Martin"),
    RosterEmployee(id="e2", first_name="Sophie", last_name="Durand"),
    RosterEmployee(id="e3", first_name="Marie", last_name="Martin"),
]


def _result(data):
    return StructuredExtractionResult(data=data, tokens_used=10)


# --- Résolution des employés ---


class TestResolveEmployee:
    def test_exact_full_name_high_confidence(self):
        proposal = ai_fill._resolve_employee("Paul Martin", ROSTER)
        assert proposal.employee_id == "e1"
        assert proposal.match_confidence == "high"

    def test_reversed_order_matches(self):
        proposal = ai_fill._resolve_employee("Durand Sophie", ROSTER)
        assert proposal.employee_id == "e2"
        assert proposal.match_confidence == "high"

    def test_accent_and_case_insensitive(self):
        proposal = ai_fill._resolve_employee("SOPHIE DURAND", ROSTER)
        assert proposal.employee_id == "e2"

    def test_ambiguous_last_name_not_resolved(self):
        # "Martin" seul correspond à Paul Martin ET Marie Martin
        proposal = ai_fill._resolve_employee("Martin", ROSTER)
        assert proposal.employee_id is None
        assert proposal.match_confidence == "none"
        assert proposal.warnings

    def test_unknown_name_not_resolved(self):
        proposal = ai_fill._resolve_employee("Jean Inconnu", ROSTER)
        assert proposal.employee_id is None
        assert proposal.warnings


# --- Nettoyage des jours ---


class TestCoerceDays:
    def test_filters_out_of_range_and_duplicates(self):
        raw = [
            {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"},
            {"jour": 1, "heures": 7, "type": "travail", "nature": "reel"},  # doublon
            {"jour": 40, "heures": 8, "type": "travail", "nature": "reel"},  # hors mois
            {"jour": 2, "heures": -3, "type": "travail", "nature": "reel"},  # négatif
        ]
        days = ai_fill._coerce_days(raw, num_days=30, default_nature="reel")
        assert [d.jour for d in days] == [1, 2]
        assert days[0].heures == 8
        assert days[1].heures == 0.0

    def test_invalid_type_falls_back_to_travail(self):
        days = ai_fill._coerce_days(
            [{"jour": 3, "heures": 8, "type": "n_importe_quoi", "nature": "reel"}],
            num_days=30,
            default_nature="reel",
        )
        assert days[0].type == "travail"

    def test_known_absence_type_preserved(self):
        days = ai_fill._coerce_days(
            [{"jour": 3, "heures": 0, "type": "conge", "nature": "reel"}],
            num_days=30,
            default_nature="reel",
        )
        assert days[0].type == "conge"

    def test_invalid_nature_falls_back_to_default(self):
        days = ai_fill._coerce_days(
            [{"jour": 3, "heures": 8, "type": "travail", "nature": "n_importe"}],
            num_days=30,
            default_nature="prevu",
        )
        assert days[0].nature == "prevu"

    def test_missing_nature_uses_default(self):
        days = ai_fill._coerce_days(
            [{"jour": 3, "heures": 8, "type": "travail"}],
            num_days=30,
            default_nature="prevu",
        )
        assert days[0].nature == "prevu"

    def test_same_day_two_natures_kept(self):
        raw = [
            {"jour": 5, "heures": 8, "type": "travail", "nature": "prevu"},
            {"jour": 5, "heures": 6, "type": "travail", "nature": "reel"},
        ]
        days = ai_fill._coerce_days(raw, num_days=30, default_nature="reel")
        assert len(days) == 2
        natures = {d.nature for d in days}
        assert natures == {"prevu", "reel"}


# --- parse_instruction ---


class TestParseInstruction:
    def test_builds_proposal_with_resolution(self):
        extracted = {
            "employees": [
                {
                    "name": "Paul Martin",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"}
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.parse_instruction(
                year=2026, month=6, instruction="Paul a fait 8h le 1er", roster=ROSTER
            )

        assert proposal.source == "texte"
        assert len(proposal.employees) == 1
        emp = proposal.employees[0]
        assert emp.employee_id == "e1"
        assert emp.days[0].jour == 1
        assert emp.days[0].nature == "reel"

    def test_raises_when_llm_not_configured(self):
        with patch.object(ai_fill, "is_llm_configured", return_value=False):
            with pytest.raises(ScheduleAppError) as exc:
                ai_fill.parse_instruction(
                    year=2026, month=6, instruction="x", roster=ROSTER
                )
        assert exc.value.status_code == 503

    def test_raises_on_empty_instruction(self):
        with patch.object(ai_fill, "is_llm_configured", return_value=True):
            with pytest.raises(ScheduleAppError) as exc:
                ai_fill.parse_instruction(
                    year=2026, month=6, instruction="   ", roster=ROSTER
                )
        assert exc.value.status_code == 400

    def test_raises_when_llm_returns_none(self):
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=None
        ):
            with pytest.raises(ScheduleAppError) as exc:
                ai_fill.parse_instruction(
                    year=2026, month=6, instruction="Paul 8h", roster=ROSTER
                )
        assert exc.value.status_code == 502


# --- extract_timesheet ---


class TestExtractTimesheet:
    def test_builds_proposal_from_document(self):
        extracted = {
            "employees": [
                {
                    "name": "Sophie Durand",
                    "days": [
                        {"jour": 2, "heures": 7, "type": "travail", "nature": "reel"}
                    ],
                }
            ],
            "warnings": ["scan partiel"],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_document_text", return_value=("texte ocr", "PDF natif")
        ), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=6,
                file_content=b"%PDF-1.4 fake",
                filename="releve.pdf",
                roster=ROSTER,
            )

        assert "relevé" in proposal.source
        assert proposal.employees[0].employee_id == "e2"
        assert proposal.employees[0].days[0].heures == 7
        assert proposal.employees[0].days[0].nature == "reel"

    def test_raises_on_extraction_error(self):
        from app.shared.infrastructure.documents import DocumentExtractionError

        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill,
            "extract_document_text",
            side_effect=DocumentExtractionError("illisible"),
        ):
            with pytest.raises(ScheduleAppError) as exc:
                ai_fill.extract_timesheet(
                    year=2026,
                    month=6,
                    file_content=b"x",
                    filename="bad.png",
                    roster=ROSTER,
                )
        assert exc.value.status_code == 400
