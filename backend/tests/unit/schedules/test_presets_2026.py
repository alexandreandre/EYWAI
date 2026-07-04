"""Tests des presets 2026 : cohérence des totaux et matérialisation éditable."""
from app.modules.schedules.application import preset_apply
from app.modules.schedules.application.presets_2026 import get_registry, list_presets
from app.modules.schedules.domain.calendar_generation_rules import normalize_day_config


def test_registry_couvre_les_cinq_societes():
    keys = set(get_registry().keys())
    assert {"comitech", "colorplast", "mbc", "lewis", "cartol"} <= keys


def test_totaux_hebdo_recalcules_coherents():
    by_name = {
        t["name"]: t["weekly_hours"]
        for p in list_presets()
        for t in p["templates"]
    }
    assert by_name["Comitech — Été (39h)"] == 39.0
    assert by_name["Comitech — Hiver (39h)"] == 39.0
    assert by_name["Colorplast — Standard (39h)"] == 39.0
    assert by_name["MBC — Standard (37,5h)"] == 37.5
    assert by_name["MBC — 3×8 pauses (37,5h)"] == 37.5
    assert by_name["Cartol — Bureau 35H (Tania Espirito Santo)"] == 35.0


def test_mbc_3x8_template_breaks():
    preset = get_registry()["mbc"]
    tpl = next(t for t in preset.templates if t.name == "MBC — 3×8 pauses (37,5h)")
    cfg = normalize_day_config(tpl.days[0])
    assert cfg["hours"] == 7.5
    assert cfg["paid_break_minutes"] == 20
    assert cfg["unpaid_break_minutes"] == 30


def test_plans_ambigus_flagges_needs_confirmation():
    plans = {
        p["name"]: p
        for preset in list_presets()
        for p in preset["plans"]
    }
    # Lewis cycle + activité partielle et Cartol été = données à confirmer.
    assert plans["Lewis — Cycle 70h/2sem (après août 2026)"]["needs_confirmation"] is True
    assert plans["Lewis — Activité partielle été 2026"]["needs_confirmation"] is True
    # Modèle simple non ambigu = pas de flag.
    assert plans["Colorplast — 2026"]["needs_confirmation"] is False


def test_lewis_cycle_a_deux_modeles():
    plans = {
        p["name"]: p for preset in list_presets() for p in preset["plans"]
    }
    cycle = plans["Lewis — Cycle 70h/2sem (après août 2026)"]["template_names"]
    assert len(cycle) == 2


def test_apply_preset_materialise_modeles_et_plans(monkeypatch):
    created_templates = []
    created_plans = []

    def fake_upsert_template(company_id, payload, template_id=None):
        created_templates.append(payload)
        return {"id": f"tpl-{len(created_templates)}", **payload}

    monkeypatch.setattr(preset_apply.mod_repo, "upsert_week_template", fake_upsert_template)
    monkeypatch.setattr(preset_apply.plans_repo, "find_template_by_name", lambda c, n: None)
    monkeypatch.setattr(preset_apply.plans_repo, "find_employees_by_name", lambda c, names: {})
    monkeypatch.setattr(preset_apply.plans_repo, "find_plan_by_name", lambda c, name: None)

    def fake_create_plan(company_id, payload):
        created_plans.append(payload)
        return {"id": f"plan-{len(created_plans)}", **payload}

    monkeypatch.setattr(preset_apply.plans_repo, "create_plan", fake_create_plan)

    result = preset_apply.apply_preset("colorplast", "colorplast")
    assert result["status"] == "success"
    assert result["templates_created"] == 1
    assert result["plans_created"] == 1
    # Le plan référence bien un cycle de modèles matérialisés.
    assert created_plans[0]["template_cycle"] == ["tpl-1"]


def test_apply_preset_flagge_affectation_non_resolue(monkeypatch):
    created_plans = []

    monkeypatch.setattr(
        preset_apply.mod_repo, "upsert_week_template",
        lambda c, p, template_id=None: {"id": "tpl", **p},
    )
    monkeypatch.setattr(preset_apply.plans_repo, "find_template_by_name", lambda c, n: None)
    # Aucun salarié nommé n'est trouvé.
    monkeypatch.setattr(preset_apply.plans_repo, "find_employees_by_name", lambda c, names: {})
    monkeypatch.setattr(preset_apply.plans_repo, "find_plan_by_name", lambda c, name: None)
    monkeypatch.setattr(
        preset_apply.plans_repo, "create_plan",
        lambda c, p: created_plans.append(p) or {"id": "x", **p},
    )
    monkeypatch.setattr(
        "app.modules.planning.infrastructure.repository.planning_repository.update_company_planning_settings",
        lambda c, p: p,
    )

    preset_apply.apply_preset("mbc", "mbc")
    rina = next(p for p in created_plans if "Rina" in p["name"])
    assert rina["needs_confirmation"] is True
    assert "Affectation à confirmer" in rina["notes"]


def test_apply_preset_est_idempotent(monkeypatch):
    """Ré-appliquer un preset met à jour les plans existants au lieu de dupliquer."""
    from app.modules.schedules.application import preset_apply

    store: dict[str, dict] = {}

    monkeypatch.setattr(
        preset_apply.mod_repo, "upsert_week_template",
        lambda c, p, template_id=None: {"id": f"tpl-{p['name']}", **p},
    )
    monkeypatch.setattr(preset_apply.plans_repo, "find_template_by_name", lambda c, n: None)
    monkeypatch.setattr(preset_apply.plans_repo, "find_employees_by_name", lambda c, names: {})
    monkeypatch.setattr(
        preset_apply.plans_repo, "find_plan_by_name",
        lambda c, name: store.get(name),
    )

    def fake_create(c, payload):
        row = {"id": f"plan-{payload['name']}", **payload}
        store[payload["name"]] = row
        return row

    def fake_update(c, plan_id, payload):
        name = payload["name"]
        store[name] = {"id": plan_id, **payload}
        return store[name]

    monkeypatch.setattr(preset_apply.plans_repo, "create_plan", fake_create)
    monkeypatch.setattr(preset_apply.plans_repo, "update_plan", fake_update)

    r1 = preset_apply.apply_preset("comp", "colorplast")
    r2 = preset_apply.apply_preset("comp", "colorplast")
    # Deux passages → même nombre de plans (pas de doublon).
    assert r1["plans_created"] == r2["plans_created"]
    assert len(store) == r1["plans_created"]


def test_generate_all_ordonne_par_precedence_de_portee(monkeypatch):
    """Les plans salarié (exceptions) passent après les plans société."""
    from app.modules.schedules.application import calendar_generation as cg

    order: list[str] = []
    plans = [
        {"id": "e1", "scope_type": "employees", "start_date": "2026-01-01", "name": "Rina"},
        {"id": "c1", "scope_type": "company", "start_date": "2026-01-01", "name": "Standard"},
    ]
    monkeypatch.setattr(cg.plans_repo, "list_plans", lambda c, active_only=True: plans)
    monkeypatch.setattr(cg.plans_repo, "update_plan", lambda c, pid, payload: None)

    def fake_generate(spec, *, dry_run=False, recalculate_payroll=False):
        order.append(spec.plan_id or "?")
        return {"status": "preview", "employee_count": 1}

    monkeypatch.setattr(cg, "generate", fake_generate)
    # spec_from_plan a besoin de company_id ; on l'injecte.
    for p in plans:
        p["company_id"] = "comp"
        p["template_cycle"] = ["t"]

    cg.generate_all_active_plans("comp", year=2026, dry_run=True)
    # company (c1) avant employees (e1).
    assert order == ["c1", "e1"]
