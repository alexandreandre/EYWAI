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
            ai_fill, "extract_document_text", return_value=("texte ocr", "PDF natif")
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
