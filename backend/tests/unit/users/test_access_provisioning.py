"""Tests unitaires — provisioning accès idempotent (sans I/O live)."""

from __future__ import annotations

from pathlib import Path

from app.modules.users.application.access_provisioning import (
    AccessProvisioner,
    InMemoryProvisioningGateway,
    generate_initial_password,
    load_manifest,
    normalize_identity,
    write_access_workbook,
)


def _base_gateway(**kwargs) -> InMemoryProvisioningGateway:
    companies = [
        {"id": "c-mbc", "company_name": "Mont Blanc Composite"},
        {"id": "c-cartol", "company_name": "Cartol Industrie"},
        {"id": "c-lewis", "company_name": "LEWIS"},
        {"id": "c-color", "company_name": "Colorplast"},
        {"id": "c-comi", "company_name": "Comitech Composite"},
        {"id": "c-maji", "company_name": "MAJI"},
        {"id": "c-z404", "company_name": "Zone 404 Mars"},
    ]
    permissions = {
        "payslips.validate": "p-pay-val",
        "expenses.approve": "p-exp-app",
        "schedules.validate": "p-sch-val",
        "schedules.view_all": "p-sch-view",
        "schedules.update": "p-sch-upd",
        "advances.approve": "p-adv-app",
        "advances.view_all": "p-adv-view",
        "advances.process": "p-adv-proc",
        "enroll_employee_training": "p-train",
        "view_objectives_reporting": "p-obj-view",
        "evaluate_objective": "p-obj-eval",
        "create_individual_objective": "p-obj-create",
        "analytics.export": "p-an-exp",
        "analytics.view_all": "p-an-view",
        "contracts.view_all": "p-ctr-view",
        "bank_dispatch.send": "p-bank",
    }
    return InMemoryProvisioningGateway(
        companies=companies,
        permissions=permissions,
        teams={
            "c-mbc": [
                {"id": "t-mod", "name": "MOD", "company_id": "c-mbc"},
                {"id": "t-moi", "name": "MOI", "company_id": "c-mbc"},
            ]
        },
        **kwargs,
    )


def test_normalize_identity_unicode():
    assert normalize_identity("Gaëlle  BOUALI") == "gaelle bouali"


def test_dorothee_is_noop():
    manifest = load_manifest(
        Path("app/modules/users/data/access_manifest.json")
    )
    gw = _base_gateway(
        profiles=[
            {
                "id": "u-doro",
                "first_name": "Dorothée",
                "last_name": "Boulay",
                "email": "doro@x.test",
            }
        ]
    )
    plan = AccessProvisioner(manifest, gw).plan()
    doro = [i for i in plan.items if "dorothee" in i.subject]
    assert doro and all(i.decision == "no-op" for i in doro)


def test_technical_account_create_then_second_run_noop(tmp_path: Path):
    manifest = {
        "version": 1,
        "companies": {"mbc": ["Mont Blanc Composite"]},
        "permission_sets": {},
        "people": [
            {
                "key": "gaelle",
                "identity": {
                    "name": "Gaëlle Bouali",
                    "email": "gaelle.bouali@eywai.access.local",
                },
                "account": "technical_login",
                "accesses": [{"company": "mbc", "role": "rh", "scope_mode": "company"}],
            }
        ],
    }
    gw = _base_gateway()
    p = AccessProvisioner(manifest, gw)
    plan1 = p.plan()
    assert any(i.action == "create_account" for i in plan1.items)
    assert any(i.action == "create_access" for i in plan1.items)
    passwords = p.apply(plan1)
    assert "gaelle" in passwords

    plan2 = AccessProvisioner(manifest, gw).plan()
    assert not plan2.has_conflicts
    assert all(i.decision == "no-op" for i in plan2.items)

    out = tmp_path / "out.xlsx"
    write_access_workbook(plan1, out, passwords=passwords, usernames={"gaelle": "gaelle.bouali"})
    assert out.exists()
    assert oct(out.stat().st_mode)[-3:] == "600"


def test_vanessa_deactivate_duplicate_not_delete():
    manifest = {
        "version": 1,
        "companies": {"maji": ["MAJI"], "zone_404": ["Zone 404 Mars"]},
        "permission_sets": {"bank_only": ["bank_dispatch.send"]},
        "people": [
            {
                "key": "vanessa",
                "identity": {"name": "Vanessa Amate"},
                "account": "existing_only",
                "canonical_employee_account": True,
                "prefer_role": "collaborateur",
                "accesses": [
                    {
                        "company": "maji",
                        "role": "admin",
                        "scope_mode": "company",
                        "permission_set": "bank_only",
                    }
                ],
                "duplicate_access": {"deactivate": True},
            }
        ],
    }
    gw = _base_gateway(
        profiles=[
            {
                "id": "u-van-collab",
                "first_name": "Vanessa",
                "last_name": "Amate",
                "role": "collaborateur",
                "email": "van@emp.test",
            },
            {
                "id": "u-van-admin",
                "first_name": "Vanessa",
                "last_name": "Amate",
                "role": "admin",
                "email": "van@admin.test",
            },
        ],
        accesses=[
            {
                "id": "a1",
                "user_id": "u-van-collab",
                "company_id": "c-maji",
                "role": "collaborateur",
                "is_active": True,
            },
            {
                "id": "a2",
                "user_id": "u-van-admin",
                "company_id": "c-maji",
                "role": "admin",
                "is_active": True,
            },
        ],
    )
    p = AccessProvisioner(manifest, gw)
    plan = p.plan()
    assert not plan.has_conflicts
    assert any(i.action == "update_access_role" for i in plan.items)
    assert any(i.action == "deactivate_duplicate" for i in plan.items)
    p.apply(plan)
    assert any(
        a["id"] == "a2" and a.get("is_active") is False for a in gw.accesses
    )
    assert any(a["id"] == "a1" and a.get("role") == "admin" for a in gw.accesses)
    # Pas de suppression
    assert len(gw.accesses) == 2
    assert len(gw.profiles) == 2


def test_must_change_password_on_create():
    gw = _base_gateway()
    uid = gw.create_account(
        "x@y.z", "Ada Lovelace", generate_initial_password(), company_id="c-mbc", role="rh"
    )
    gw.set_must_change_password(uid, True)
    assert next(p for p in gw.profiles if p["id"] == uid)["must_change_password"] is True


def test_sync_accesses_deactivates_stale():
    manifest = {
        "version": 1,
        "companies": {"maji": ["MAJI"], "zone_404": ["Zone 404 Mars"], "mbc": ["Mont Blanc Composite"]},
        "permission_sets": {"bank_only": ["bank_dispatch.send"]},
        "people": [
            {
                "key": "gaelle",
                "identity": {
                    "name": "Gaëlle Bouali",
                    "email": "gaelle.bouali@eywai.access.local",
                    "username": "gaelle.bouali",
                },
                "account": "technical_login",
                "sync_accesses": True,
                "accesses": [
                    {
                        "company": "maji",
                        "role": "rh",
                        "scope_mode": "company",
                        "permission_set": "bank_only",
                    },
                    {
                        "company": "zone_404",
                        "role": "rh",
                        "scope_mode": "company",
                        "permission_set": "bank_only",
                    },
                ],
            }
        ],
    }
    gw = _base_gateway(
        profiles=[
            {
                "id": "u-g",
                "first_name": "Gaëlle",
                "last_name": "Bouali",
                "email": "gaelle.bouali@eywai.access.local",
                "role": "rh",
            }
        ],
        accesses=[
            {
                "id": "a-mbc",
                "user_id": "u-g",
                "company_id": "c-mbc",
                "role": "rh",
                "is_active": True,
            },
            {
                "id": "a-maji",
                "user_id": "u-g",
                "company_id": "c-maji",
                "role": "rh",
                "is_active": True,
            },
        ],
    )
    p = AccessProvisioner(manifest, gw)
    plan = p.plan()
    assert not plan.has_conflicts
    assert any(i.action == "deactivate_stale_access" for i in plan.items)
    assert any(i.action == "create_access" and i.details["company_id"] == "c-z404" for i in plan.items)
    p.apply(plan)
    stale = next(a for a in gw.accesses if a["id"] == "a-mbc")
    assert stale["is_active"] is False


def test_baptiste_mod_scope_and_self_deny():
    manifest = {
        "version": 1,
        "companies": {"mbc": ["Mont Blanc Composite"]},
        "permission_sets": {
            "director_mod_validations": ["payslips.validate", "contracts.view_all"]
        },
        "people": [
            {
                "key": "baptiste",
                "identity": {"name": "Baptiste Droz-Vincent"},
                "account": "existing_only",
                "accesses": [
                    {
                        "company": "mbc",
                        "role": "custom",
                        "scope_mode": "teams",
                        "team_names": ["MOD"],
                        "permission_set": "director_mod_validations",
                    }
                ],
                "target_exceptions": [
                    {
                        "company": "mbc",
                        "permission": "payslips.validate",
                        "effect": "deny",
                        "employee": {"self": True},
                    }
                ],
            }
        ],
    }
    gw = _base_gateway(
        profiles=[
            {
                "id": "u-bap",
                "first_name": "Baptiste",
                "last_name": "Droz-Vincent",
                "email": "b@x.test",
            }
        ],
        accesses=[
            {
                "id": "a-b",
                "user_id": "u-bap",
                "company_id": "c-mbc",
                "role": "collaborateur",
                "is_active": True,
            }
        ],
        employees=[
            {
                "id": "e-bap",
                "user_id": "u-bap",
                "first_name": "Baptiste",
                "last_name": "Droz-Vincent",
                "company_id": "c-mbc",
            }
        ],
    )
    p = AccessProvisioner(manifest, gw)
    plan = p.plan()
    assert not plan.has_conflicts
    assert any(i.action == "update_access_role" for i in plan.items)
    grants = next(i for i in plan.items if i.action == "replace_grants")
    pay = next(
        g for g in grants.details["grants"] if g["permission_code"] == "payslips.validate"
    )
    assert pay["scope_mode"] == "teams"
    assert pay["team_ids"] == ["t-mod"]
    assert pay["targets"] == [{"employee_id": "e-bap", "effect": "deny"}]
    p.apply(plan)
    plan2 = AccessProvisioner(manifest, gw).plan()
    assert all(i.decision == "no-op" for i in plan2.items)
