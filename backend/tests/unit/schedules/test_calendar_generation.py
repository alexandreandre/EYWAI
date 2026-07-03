"""Tests du moteur de génération des calendriers prévisionnels (domaine pur + service).

Les modèles proviennent directement des presets 2026 : ces tests valident donc
à la fois la logique de génération ET la cohérence des presets métier.
"""
from datetime import date

import pytest

from app.modules.schedules.application import calendar_generation
from app.modules.schedules.application.calendar_generation import GenerationSpec, generate
from app.modules.schedules.application.presets_2026 import get_registry
from app.modules.schedules.domain.calendar_generation_rules import (
    build_month_calendrier_prevu,
    day_config_map,
    resolve_cycle_week_index,
    week_weekly_hours,
)


def _template(company_key: str, name: str):
    preset = get_registry()[company_key]
    for t in preset.templates:
        if t.name == name:
            return t
    raise KeyError(name)


def _days(company_key: str, name: str):
    return _template(company_key, name).days


def _resolver(days):
    dm = day_config_map(days)
    return lambda monday: dm


def _entries(days, year=2026, month=2, **kw):
    return build_month_calendrier_prevu(year, month, _resolver(days), **kw)


def _fridays(entries, year=2026, month=2):
    return [e for e in entries if date(year, month, e["jour"]).isoweekday() == 5]


# ---------------- Colorplast ----------------


def test_colorplast_vendredi_5h_et_semaine_39h():
    days = _days("colorplast", "Colorplast — Standard (39h)")
    assert week_weekly_hours(days) == 39.0
    entries = _entries(days)
    assert all(e["heures_prevues"] == 5 for e in _fridays(entries))
    # Une semaine pleine L-V = 39h.
    assert week_weekly_hours(days) == 8.5 * 4 + 5


# ---------------- MBC ----------------


def test_mbc_standard_37_5():
    assert week_weekly_hours(_days("mbc", "MBC — Standard (37,5h)")) == 37.5


def test_mbc_exceptions_rina_20_sihem_17_5():
    assert week_weekly_hours(_days("mbc", "MBC — Rina LIKA (20h)")) == 20.0
    assert week_weekly_hours(_days("mbc", "MBC — Sihem RABBENI (17,5h)")) == 17.5


# ---------------- Lewis ----------------


def test_lewis_activite_partielle_35h():
    days = _days("lewis", "Lewis — Activité partielle (35h)")
    assert week_weekly_hours(days) == 35.0
    # Juin 2026 : chaque jour L-V = 7h.
    entries = _entries(days, year=2026, month=6)
    worked = [e for e in entries if e["type"] == "travail"]
    assert all(e["heures_prevues"] == 7 for e in worked)


def test_lewis_cycle_70h_sur_deux_semaines():
    a = week_weekly_hours(_days("lewis", "Lewis — Semaine A (37,25h)"))
    b = week_weekly_hours(_days("lewis", "Lewis — Semaine B (32,75h)"))
    assert a == 37.25
    assert b == 32.75
    assert round(a + b, 2) == 70.0


def test_lewis_cycle_alterne_semaine_a_puis_b():
    anchor = date(2026, 8, 31)  # un lundi
    assert resolve_cycle_week_index(2, anchor, anchor) == 0            # semaine A
    assert resolve_cycle_week_index(2, anchor, date(2026, 9, 7)) == 1  # semaine B
    assert resolve_cycle_week_index(2, anchor, date(2026, 9, 14)) == 0 # retour A


# ---------------- Comitech ----------------


def test_comitech_ete_vendredi_7_total_39():
    days = _days("comitech", "Comitech — Été (39h)")
    assert week_weekly_hours(days) == 39.0
    assert all(e["heures_prevues"] == 7 for e in _fridays(_entries(days)))


def test_comitech_hiver_vendredi_5_5_total_39():
    days = _days("comitech", "Comitech — Hiver (39h)")
    assert week_weekly_hours(days) == 39.0
    assert all(e["heures_prevues"] == 5.5 for e in _fridays(_entries(days)))


# ---------------- Cartol ----------------


def test_cartol_atelier_35h_vendredi_3h45_total_environ_35():
    days = _days("cartol", "Cartol — Atelier 35H")
    # Vendredi = 3h45 = 3.75h.
    assert all(e["heures_prevues"] == 3.75 for e in _fridays(_entries(days)))
    # Somme réelle recalculée ≈ 35,08h (nominal 35 signalé needs_confirmation).
    assert week_weekly_hours(days) == 35.08


def test_cartol_atelier_28h_lundi_repos_mardi_jeudi_7h50_vendredi_4h25():
    days = _days("cartol", "Cartol — Atelier 28H (MN Deplanne)")
    entries = _entries(days)
    for e in entries:
        iso = date(2026, 2, e["jour"]).isoweekday()
        if iso == 1:  # lundi non travaillé
            assert e["type"] != "travail"
            assert e["heures_prevues"] == 0
        elif iso in (2, 3, 4):  # mardi-jeudi 7h50
            assert e["heures_prevues"] == pytest.approx(7 + 50 / 60, abs=1e-3)
        elif iso == 5:  # vendredi 4h25
            assert e["heures_prevues"] == pytest.approx(4 + 25 / 60, abs=1e-3)


def test_cartol_bureau_tania_total_35():
    assert week_weekly_hours(_days("cartol", "Cartol — Bureau 35H (Tania Espirito Santo)")) == 35.0


def test_cartol_bureau_ete_total_36h40():
    days = _days("cartol", "Cartol — Bureau Été")
    assert week_weekly_hours(days) == pytest.approx(36 + 40 / 60, abs=0.01)


# ---------------- Jours fériés & modes ----------------


def test_jour_ferie_devient_ferie_0h():
    days = _days("colorplast", "Colorplast — Standard (39h)")
    # 1er mai 2026 (vendredi) férié.
    entries = build_month_calendrier_prevu(
        2026, 5, _resolver(days), holidays={1}
    )
    jour1 = next(e for e in entries if e["jour"] == 1)
    assert jour1["type"] == "ferie"
    assert jour1["heures_prevues"] == 0


def test_preserve_manual_conserve_les_jours_manuels():
    days = _days("colorplast", "Colorplast — Standard (39h)")
    existing = [{"jour": 2, "type": "conge", "heures_prevues": 0, "manuel": True}]
    entries = build_month_calendrier_prevu(
        2026, 2, _resolver(days), existing_entries=existing,
        overwrite_mode="preserve_manual",
    )
    jour2 = next(e for e in entries if e["jour"] == 2)
    assert jour2["type"] == "conge"
    assert jour2.get("manuel") is True


# ---------------- Service de génération (données écrites) ----------------


def test_generate_ecrit_calendrier_prevu(monkeypatch):
    days = _days("colorplast", "Colorplast — Standard (39h)")
    captured = {}

    def fake_get_templates_by_ids(company_id, ids):
        return {ids[0]: {"id": ids[0], "day_configs": days}}

    def fake_resolve_scope(company_id, scope_type, scope_ref):
        return [{"id": "emp-1", "statut": None, "first_name": "Jean", "last_name": "Dupont"}]

    def fake_get_schedules(employee_id, year_months):
        return []

    def fake_bulk_upsert(payloads):
        captured["payloads"] = payloads

    monkeypatch.setattr(calendar_generation.plans_repo, "get_templates_by_ids", fake_get_templates_by_ids)
    monkeypatch.setattr(calendar_generation.plans_repo, "resolve_scope_employees", fake_resolve_scope)
    monkeypatch.setattr(calendar_generation.schedule_repository, "get_schedules_for_months", fake_get_schedules)
    monkeypatch.setattr(calendar_generation.schedule_repository, "bulk_upsert_schedules", fake_bulk_upsert)
    monkeypatch.setattr(calendar_generation, "day_numbers_observed_holidays", lambda y, m, c: set())

    spec = GenerationSpec(
        company_id="comp-1",
        template_cycle=["tpl-1"],
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        cycle_anchor=date(2026, 2, 2),
    )
    result = generate(spec, dry_run=False)

    assert result["status"] == "applied"
    # La donnée qui alimente la paie est bien planned_calendar.calendrier_prevu.
    pc = captured["payloads"][0]["planned_calendar"]
    assert "calendrier_prevu" in pc
    assert pc["source"]["template_ids"] == ["tpl-1"]
    fridays = [e for e in pc["calendrier_prevu"] if date(2026, 2, e["jour"]).isoweekday() == 5]
    assert all(e["heures_prevues"] == 5 for e in fridays)


def test_generate_dry_run_n_ecrit_pas(monkeypatch):
    days = _days("mbc", "MBC — Standard (37,5h)")

    monkeypatch.setattr(calendar_generation.plans_repo, "get_templates_by_ids",
                        lambda c, ids: {ids[0]: {"id": ids[0], "day_configs": days}})
    monkeypatch.setattr(calendar_generation.plans_repo, "resolve_scope_employees",
                        lambda c, st, sr: [{"id": "e1", "statut": None, "first_name": "A", "last_name": "B"}])
    monkeypatch.setattr(calendar_generation.schedule_repository, "get_schedules_for_months",
                        lambda e, ym: [])
    monkeypatch.setattr(calendar_generation, "day_numbers_observed_holidays", lambda y, m, c: set())

    def _boom(*a, **k):
        raise AssertionError("aucune écriture ne doit avoir lieu en dry-run")

    monkeypatch.setattr(calendar_generation.schedule_repository, "bulk_upsert_schedules", _boom)

    spec = GenerationSpec(
        company_id="c", template_cycle=["t"], start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31), cycle_anchor=date(2026, 3, 2),
    )
    result = generate(spec, dry_run=True)
    assert result["status"] == "preview"
    assert result["employees"][0]["months"][0]["weekly_totals"]
