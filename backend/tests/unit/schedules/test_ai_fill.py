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
from app.shared.infrastructure.documents.text_extraction import ExtractionMetadata

_EMPTY_META = ExtractionMetadata()


@pytest.fixture(autouse=True)
def _deterministic_extract_mode(monkeypatch):
    """Les tests ai_fill ciblent le chemin Cegid/LLM document (pas l'hybride async)."""
    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "deterministic")


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
    def test_uses_fast_path_without_llm(self):
        with patch.object(ai_fill, "extract_structured_json") as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="Paul Martin a fait 8h du 1 au 3",
                roster=ROSTER,
            )
        mock_llm.assert_not_called()
        assert proposal.source == "texte (analyse rapide)"
        assert proposal.employees[0].employee_id == "e1"

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
                year=2026,
                month=6,
                instruction="Paul a fait 8h le 1er et Sophie 7h le 2",
                roster=ROSTER,
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

    def test_broadcast_collective_mode_without_llm(self):
        roster = ROSTER + [
            RosterEmployee(id="e3", first_name="Fredo", last_name="André"),
        ]
        with patch.object(ai_fill, "extract_structured_json") as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="Met 0h faites à tout le monde sauf fredo andré",
                roster=roster,
            )
        mock_llm.assert_not_called()
        assert proposal.source == "texte (analyse rapide)"
        assert len(proposal.employees) == 2

    def test_raises_when_llm_returns_none(self):
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=None
        ):
            with pytest.raises(ScheduleAppError) as exc:
                ai_fill.parse_instruction(
                    year=2026, month=6, instruction="Paul 8h", roster=ROSTER
                )
        assert exc.value.status_code == 502

    def test_single_employee_forces_attribution_without_name(self):
        # L'IA renvoie un nom générique / vide, mais en mode mono-employé tout
        # est rattaché à l'unique salarié du roster.
        extracted = {
            "employees": [
                {
                    "name": "le salarié",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"},
                        {"jour": 2, "heures": 7, "type": "travail", "nature": "reel"},
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="a fait 8h le 1 et 7h le 2",
                roster=[ROSTER[0]],
                single_employee=True,
            )

        assert len(proposal.employees) == 1
        emp = proposal.employees[0]
        assert emp.employee_id == "e1"
        assert emp.match_confidence == "high"
        assert [d.jour for d in emp.days] == [1, 2]

    def test_broadcast_applies_to_all_roster_without_names(self):
        # Saisie collective : mêmes jours appliqués à tous (analyse rapide).
        with patch.object(ai_fill, "extract_structured_json") as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="tout le monde a fait 7h le 1 et le 2",
                roster=ROSTER,
                broadcast=True,
            )

        mock_llm.assert_not_called()
        assert proposal.source == "texte (analyse rapide)"
        assert {e.employee_id for e in proposal.employees} == {"e1", "e2", "e3"}
        for emp in proposal.employees:
            assert emp.match_confidence == "high"
            assert [d.jour for d in emp.days] == [1, 2]
            assert all(d.heures == 7 for d in emp.days)

    def test_broadcast_flag_clear_instruction_no_llm(self):
        # Mode collectif (flag) avec consigne claire sans nom : diffusé à tout le
        # roster de façon déterministe, sans LLM (évite les coupures de réponse).
        with patch.object(ai_fill, "extract_structured_json") as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="a fait 8h du 1 au 3",
                roster=ROSTER,
                broadcast=True,
            )
        mock_llm.assert_not_called()
        assert {e.employee_id for e in proposal.employees} == {"e1", "e2", "e3"}
        for emp in proposal.employees:
            assert [d.jour for d in emp.days] == [1, 2, 3]
            assert all(d.heures == 8 for d in emp.days)

    def test_broadcast_flag_vague_instruction_uses_llm_for_all(self):
        # Consigne sans heures exploitables par le fast-path : le LLM prend le
        # relais mais la diffusion reste sur TOUT le roster (jamais un seul nom).
        extracted = {
            "employees": [
                {
                    "name": "(tous)",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"}
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="comme d'habitude le 1er",
                roster=ROSTER,
                broadcast=True,
            )
        mock_llm.assert_called_once()
        assert proposal.source == "texte (saisie collective)"
        assert {e.employee_id for e in proposal.employees} == {"e1", "e2", "e3"}

    def test_single_employee_skips_fast_path(self):
        # Même une consigne « fast-path friendly » passe par le LLM en mode mono.
        extracted = {
            "employees": [
                {
                    "name": "x",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"}
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="a fait 8h du 1 au 3",
                roster=[ROSTER[1]],
                single_employee=True,
            )
        mock_llm.assert_called_once()
        assert proposal.employees[0].employee_id == "e2"

    def test_mirror_planned_skips_llm_for_exactly_as_planned(self):
        planned = [
            {"jour": 1, "type": "travail", "heures_prevues": 8.0},
            {"jour": 2, "type": "travail", "heures_prevues": 7.0},
        ]

        def load_planned(_employee_id, _year, _month):
            return planned

        with patch(
            "app.modules.schedules.application.nl_fast_path._default_load_planned_calendar",
            side_effect=load_planned,
        ), patch.object(ai_fill, "extract_structured_json") as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=5,
                instruction=(
                    "Michel Bugny a fait exactement toutes les heures "
                    "qui lui étaient prévues"
                ),
                roster=ROSTER + [
                    RosterEmployee(id="e-bugny", first_name="Michel", last_name="BUGNY"),
                ],
            )
        mock_llm.assert_not_called()
        assert proposal.source == "texte (reprise planning)"
        assert proposal.employees[0].employee_id == "e-bugny"
        assert len(proposal.employees[0].days) == 2


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
            ai_fill, "extract_document_text", return_value=("texte ocr", "PDF natif", _EMPTY_META)
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

    def test_single_employee_merges_all_rows(self):
        # Le relevé peut contenir plusieurs blocs / un nom différent : tout est
        # fusionné sur l'unique salarié ciblé.
        extracted = {
            "employees": [
                {
                    "name": "MARTIN P.",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"}
                    ],
                },
                {
                    "name": "P. MARTIN",
                    "days": [
                        {"jour": 2, "heures": 7, "type": "travail", "nature": "reel"}
                    ],
                },
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_document_text", return_value=("texte ocr", "PDF natif", _EMPTY_META)
        ), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=6,
                file_content=b"%PDF-1.4 fake",
                filename="releve.pdf",
                roster=[ROSTER[0]],
                single_employee=True,
            )

        assert len(proposal.employees) == 1
        emp = proposal.employees[0]
        assert emp.employee_id == "e1"
        assert [d.jour for d in emp.days] == [1, 2]

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

    def test_attaches_period_metadata_for_weekly_releve(self):
        from tests.fixtures.timesheets.ocr_samples import WEEKLY_HEADER

        extracted = {
            "employees": [
                {
                    "name": "Paul Martin",
                    "days": [
                        {"jour": 3, "heures": 8, "type": "travail", "nature": "reel"},
                        {"jour": 4, "heures": 7.5, "type": "travail", "nature": "reel"},
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_document_text", return_value=(WEEKLY_HEADER, "PDF natif", _EMPTY_META)
        ), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.extract_timesheet(
                year=2025,
                month=6,
                file_content=b"%PDF-1.4 fake",
                filename="semaine.pdf",
                roster=ROSTER,
            )

        assert proposal.detected_scope == "weekly"
        assert proposal.detected_period_start is not None
        assert proposal.detected_days_count == 2
        assert proposal.suggested_year == 2025
        assert proposal.suggested_month == 6

    def test_auto_corrects_month_when_releve_outside_ui_month(self):
        may_week = """
        Semaine du 25/05/2026 au 31/05/2026
        Martin Paul
        Lun 25/05 8h Mar 26/05 8h Mer 27/05 8h Jeu 28/05 8h Ven 29/05 8h
        """
        extracted = {
            "employees": [
                {
                    "name": "Paul Martin",
                    "days": [
                        {"jour": 25, "heures": 8, "type": "travail", "nature": "reel"},
                        {"jour": 26, "heures": 8, "type": "travail", "nature": "reel"},
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_document_text", return_value=(may_week, "PDF natif", _EMPTY_META)
        ), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ):
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=6,
                file_content=b"%PDF-1.4 fake",
                filename="semaine.pdf",
                roster=ROSTER,
            )

        assert proposal.month_auto_corrected is True
        assert proposal.year == 2026
        assert proposal.month == 5
        assert proposal.requested_year == 2026
        assert proposal.requested_month == 6
        assert proposal.month_correction_message is not None
        assert not any("hors du mois" in w for w in proposal.period_warnings)


class TestExtractTimesheetHybridMonthDetection:
    def test_hybrid_pre_scans_month_before_extraction(self, monkeypatch):
        from datetime import date

        from app.modules.schedules.application.parsers.cegid_weekly import (
            CegidDayEntry,
            CegidEmployeeBlock,
            CegidParseResult,
        )
        from app.modules.schedules.application.timesheet_hybrid_extract import (
            HybridExtractResult,
        )
        from tests.fixtures.timesheets.ocr_samples import WEEKLY_HEADER

        monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "hybrid")
        june_text = WEEKLY_HEADER
        parse_result = CegidParseResult(
            format_detected=True,
            confidence=0.9,
            period_start=date(2025, 6, 3),
            period_end=date(2025, 6, 9),
            employees=[
                CegidEmployeeBlock(
                    matricule="1",
                    raw_name="Paul Martin",
                    days=[
                        CegidDayEntry(jour=3, month=6, year=2025, heures=8.0),
                        CegidDayEntry(jour=4, month=6, year=2025, heures=7.5),
                    ],
                )
            ],
        )
        hybrid_result = HybridExtractResult(
            parse_result=parse_result,
            full_ocr_text=june_text,
            extraction_method="hybrid_vision_ocr",
            pages_total=1,
            pages_processed=1,
            truncated=False,
        )

        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch(
            "app.shared.infrastructure.documents.extract_document_text",
            return_value=(june_text, "PDF natif", _EMPTY_META),
        ), patch(
            "app.modules.schedules.application.timesheet_hybrid_extract.extract_timesheet_hybrid",
            return_value=hybrid_result,
        ) as mock_hybrid, patch(
            "app.modules.schedules.application.roster_enrichment.enrich_roster_time_tracking_ids",
            side_effect=lambda roster, _company_id: roster,
        ):
            proposal = ai_fill.extract_timesheet(
                year=2025,
                month=5,
                file_content=b"%PDF-1.4 fake",
                filename="semaine_juin.pdf",
                roster=ROSTER,
            )

        mock_hybrid.assert_called_once()
        assert mock_hybrid.call_args.kwargs["year"] == 2025
        assert mock_hybrid.call_args.kwargs["month"] == 6
        assert proposal.month_auto_corrected is True
        assert proposal.year == 2025
        assert proposal.month == 6
        assert proposal.requested_year == 2025
        assert proposal.requested_month == 5
        assert proposal.employees[0].days[0].jour == 3


class TestExtractTimesheetCegid:
    def test_cegid_parser_without_llm(self):
        from tests.fixtures.timesheets.ocr_samples import CEGID_WEEK_22

        roster = [
            RosterEmployee(id="e1", first_name="Sophie", last_name="Durand", time_tracking_id="270"),
            RosterEmployee(id="e2", first_name="Adam", last_name="Youssef", time_tracking_id="196"),
        ]
        with patch.object(ai_fill, "is_llm_configured", return_value=False), patch.object(
            ai_fill, "extract_document_text", return_value=(CEGID_WEEK_22, "PDF natif", _EMPTY_META)
        ), patch(
            "app.modules.schedules.application.roster_enrichment.enrich_roster_time_tracking_ids",
            side_effect=lambda r, c: r,
        ):
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=5,
                file_content=b"%PDF-1.4 fake",
                filename="semaine22.pdf",
                roster=roster,
            )

        assert proposal.detected_format == "cegid_weekly"
        assert len(proposal.employees) >= 2
        assert proposal.quality_checks is not None
        assert proposal.review_summary is not None

    def test_cegid_long_text_not_truncated_before_parse(self):
        from tests.fixtures.timesheets.ocr_samples import CEGID_LONG_TEXT, _CEGID_EMP_NAMES

        assert len(CEGID_LONG_TEXT) > ai_fill._MAX_LLM_TEXT_CHARS
        roster = [
            RosterEmployee(
                id=f"e{i}",
                first_name=_CEGID_EMP_NAMES[i % len(_CEGID_EMP_NAMES)],
                last_name="Employe",
                time_tracking_id=str(100 + i),
            )
            for i in range(90)
        ]
        meta = ExtractionMetadata(
            ocr_pages_total=18,
            ocr_pages_processed=18,
        )
        with patch.object(ai_fill, "is_llm_configured", return_value=False), patch.object(
            ai_fill, "extract_document_text", return_value=(CEGID_LONG_TEXT, "OCR PDF (Tesseract)", meta)
        ), patch(
            "app.modules.schedules.application.roster_enrichment.enrich_roster_time_tracking_ids",
            side_effect=lambda r, c: r,
        ):
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=5,
                file_content=b"%PDF-1.4 fake",
                filename="semaine22.pdf",
                roster=roster,
            )

        assert proposal.detected_format == "cegid_weekly"
        assert len(proposal.employees) >= 80
        assert not any("tronqué" in w.lower() for w in proposal.extraction_warnings)
        assert proposal.extraction_pages_processed == 18
        assert proposal.extraction_truncated is False

    def test_llm_fallback_truncates_long_text(self):
        long_generic = "RELEVÉ GENERIQUE\n" + ("Paul Martin 8h jour 1\n" * 2000)
        assert len(long_generic) > ai_fill._MAX_LLM_TEXT_CHARS
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
            ai_fill, "extract_document_text", return_value=(long_generic, "PDF natif", _EMPTY_META)
        ), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            proposal = ai_fill.extract_timesheet(
                year=2026,
                month=6,
                file_content=b"%PDF-1.4 fake",
                filename="releve.pdf",
                roster=ROSTER,
            )

        mock_llm.assert_called_once()
        prompt = mock_llm.call_args.kwargs.get("user_prompt") or mock_llm.call_args[1].get("user_prompt")
        assert len(prompt) < len(long_generic)
        assert any("tronqué" in w.lower() for w in proposal.extraction_warnings)


# --- parse_instruction : mode correction (current_proposal) ---


class TestParseInstructionRefinement:
    CURRENT = {
        "employees": [
            {
                "name": "Paul Martin",
                "days": [
                    {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"},
                    {"jour": 2, "heures": 8, "type": "travail", "nature": "reel"},
                ],
            }
        ]
    }

    def test_refinement_skips_fast_path_and_injects_current_proposal(self):
        """Une consigne qui matcherait le fast-path passe au LLM avec la
        proposition actuelle dans le prompt — jamais de régénération."""
        extracted = {
            "employees": [
                {
                    "name": "Paul Martin",
                    "days": [
                        {"jour": 1, "heures": 8, "type": "travail", "nature": "reel"},
                        {"jour": 2, "heures": 7, "type": "travail", "nature": "reel"},
                    ],
                }
            ],
            "warnings": [],
        }
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                # Formulation volontairement fast-path-compatible.
                instruction="Paul Martin a fait 7h le 2",
                roster=ROSTER,
                current_proposal=self.CURRENT,
            )
        mock_llm.assert_called_once()
        prompt = mock_llm.call_args.kwargs["user_prompt"]
        assert "Proposition actuelle" in prompt
        assert '"jour": 1' in prompt or '"jour":1' in prompt
        assert "correction" in prompt.lower()
        assert proposal.employees[0].employee_id == "e1"
        assert proposal.source == "texte"

    def test_refinement_ignores_broadcast_sniffing(self):
        """« tout le monde » dans une correction ne bascule pas en mode collectif."""
        extracted = {"employees": self.CURRENT["employees"], "warnings": []}
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="mets tout le monde à 7h le lundi",
                roster=ROSTER,
                current_proposal=self.CURRENT,
            )
        prompt = mock_llm.call_args.kwargs["user_prompt"]
        assert "(tous)" not in prompt

    def test_refinement_single_employee_keeps_target(self):
        extracted = {"employees": self.CURRENT["employees"], "warnings": []}
        with patch.object(ai_fill, "is_llm_configured", return_value=True), patch.object(
            ai_fill, "extract_structured_json", return_value=_result(extracted)
        ) as mock_llm:
            proposal = ai_fill.parse_instruction(
                year=2026,
                month=6,
                instruction="vendredi à 8h",
                roster=[ROSTER[0]],
                single_employee=True,
                current_proposal=self.CURRENT,
            )
        prompt = mock_llm.call_args.kwargs["user_prompt"]
        assert "Paul Martin" in prompt
        assert "Proposition actuelle" in prompt
        assert proposal.employees[0].employee_id == "e1"
