"""Tests inférence subrogation liée au maintien."""

from __future__ import annotations

from app.modules.payroll.engine.maintien_salaire_service import resolve_subrogation_active


def _settings(mode: str = "when_maintien"):
    return {"subrogation_mode": mode}


class TestResolveSubrogationActive:
    def test_when_maintien_eligible(self):
        assert resolve_subrogation_active(
            _settings("when_maintien"), "maladie_simple", True, None
        ) is True

    def test_when_maintien_non_eligible(self):
        assert resolve_subrogation_active(
            _settings("when_maintien"), "maladie_simple", False, None
        ) is False

    def test_automatic_legacy_maps_to_maintien(self):
        assert resolve_subrogation_active(
            _settings("automatic"), "maladie_simple", False, None
        ) is False

    def test_at_mp_only_requires_at_and_maintien(self):
        assert resolve_subrogation_active(
            _settings("at_mp_only"), "accident_travail", True, None
        ) is True
        assert resolve_subrogation_active(
            _settings("at_mp_only"), "maladie_simple", True, None
        ) is False
        assert resolve_subrogation_active(
            _settings("at_mp_only"), "accident_travail", False, None
        ) is False

    def test_per_case_defaults_to_maintien_eligible(self):
        assert resolve_subrogation_active(
            _settings("per_case"), "maladie_simple", True, None
        ) is True

    def test_override_preempts_rules(self):
        assert resolve_subrogation_active(
            _settings("when_maintien"), "maladie_simple", False, True
        ) is True
