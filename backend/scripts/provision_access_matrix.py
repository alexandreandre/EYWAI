#!/usr/bin/env python3
"""Préflight/apply contrôlé de la matrice d'accès EYWAI.

Par défaut : lecture seule, plan JSON.
--apply exige project_ref exact + confirmation production.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.access_control.infrastructure.scoped_repository import (  # noqa: E402
    scoped_permission_repository,
)
from app.modules.users.application.access_provisioning import (  # noqa: E402
    AccessProvisioner,
    PRODUCTION_CONFIRMATION,
    PROJECT_REF,
    load_manifest,
    write_access_workbook,
)


class SupabaseProvisioningGateway:
    """Port Supabase — écritures uniquement après garde-fous --apply."""

    def __init__(self) -> None:
        self.client = get_supabase_admin_client()

    def list_companies(self) -> list[dict[str, Any]]:
        return (
            self.client.table("companies").select("id,company_name").execute().data
            or []
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = (
            self.client.table("profiles")
            .select("id,first_name,last_name,role,company_id,must_change_password")
            .execute()
            .data
            or []
        )
        email_by_id: dict[str, str] = {}
        page = 1
        while True:
            batch = self.client.auth.admin.list_users(page=page, per_page=200) or []
            if not batch:
                break
            for user in batch:
                email_by_id[str(user.id)] = user.email or ""
            if len(batch) < 200:
                break
            page += 1
        accesses = self.list_accesses()
        companies_by_user: dict[str, set[str]] = {}
        for acc in accesses:
            if acc.get("is_active") is False:
                continue
            companies_by_user.setdefault(str(acc["user_id"]), set()).add(
                str(acc["company_id"])
            )
        enriched: list[dict[str, Any]] = []
        for row in rows:
            uid = str(row["id"])
            enriched.append(
                {
                    **row,
                    "email": email_by_id.get(uid) or None,
                    "company_ids": sorted(companies_by_user.get(uid, set())),
                    "primary_company_id": row.get("company_id"),
                }
            )
        return enriched

    def list_accesses(self) -> list[dict[str, Any]]:
        try:
            return (
                self.client.table("user_company_accesses")
                .select("id,user_id,company_id,role,is_active,is_primary")
                .execute()
                .data
                or []
            )
        except Exception:
            rows = (
                self.client.table("user_company_accesses")
                .select("id,user_id,company_id,role,is_primary")
                .execute()
                .data
                or []
            )
            for row in rows:
                row["is_active"] = True
            return rows

    def list_employees(self) -> list[dict[str, Any]]:
        return (
            self.client.table("employees")
            .select("id,user_id,first_name,last_name,company_id,email")
            .execute()
            .data
            or []
        )

    def list_teams(self, company_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("teams")
            .select("id,name,company_id,status")
            .eq("company_id", company_id)
            .execute()
            .data
            or []
        )

    def list_permissions_by_code(self) -> dict[str, str]:
        rows = (
            self.client.table("permissions")
            .select("id,code,is_active")
            .eq("is_active", True)
            .execute()
            .data
            or []
        )
        return {str(r["code"]): str(r["id"]) for r in rows if r.get("code")}

    def get_user_permission_snapshot(
        self, user_id: str, company_id: str
    ) -> list[dict[str, Any]]:
        try:
            return scoped_permission_repository.list_grants_for_user_company(
                user_id, company_id
            )
        except Exception:
            return []

    def create_account(
        self,
        email: str,
        name: str,
        password: str,
        *,
        company_id: str,
        role: str = "custom",
        username: str | None = None,
    ) -> str:
        first_name, _, last_name = name.partition(" ")
        user_id: str | None = None
        try:
            created = self.client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "username": username,
                    },
                }
            )
            user = getattr(created, "user", created)
            user_id = str(user.id)
        except Exception as exc:
            # Compte Auth orphelin d'un apply partiel : réutiliser + poser le MDP
            msg = str(exc).lower()
            if "already" not in msg and "registered" not in msg and "exists" not in msg:
                raise
            page = 1
            while page <= 20 and user_id is None:
                batch = self.client.auth.admin.list_users(page=page, per_page=200) or []
                if not batch:
                    break
                for user in batch:
                    if (user.email or "").casefold() == email.casefold():
                        user_id = str(user.id)
                        self.client.auth.admin.update_user_by_id(
                            user_id,
                            {
                                "password": password,
                                "user_metadata": {
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "username": username,
                                },
                            },
                        )
                        break
                if len(batch) < 200:
                    break
                page += 1
            if user_id is None:
                raise RuntimeError(
                    f"Compte Auth existant introuvable pour {email}"
                ) from exc

        payload = {
            "id": user_id,
            "first_name": first_name,
            "last_name": last_name or first_name,
            "role": role,
            "company_id": company_id,
            "must_change_password": True,
        }
        if username:
            payload["username"] = username
        try:
            self.client.table("profiles").upsert(payload, on_conflict="id").execute()
        except Exception:
            payload.pop("must_change_password", None)
            try:
                self.client.table("profiles").upsert(payload, on_conflict="id").execute()
            except Exception:
                payload.pop("username", None)
                self.client.table("profiles").upsert(payload, on_conflict="id").execute()
        return user_id

    def create_access(self, user_id: str, company_id: str, role: str) -> None:
        payload = {
            "user_id": user_id,
            "company_id": company_id,
            "role": role,
            "is_primary": False,
            "is_active": True,
        }
        try:
            self.client.table("user_company_accesses").upsert(
                payload, on_conflict="user_id,company_id"
            ).execute()
        except Exception:
            payload.pop("is_active", None)
            self.client.table("user_company_accesses").upsert(
                payload, on_conflict="user_id,company_id"
            ).execute()

    def update_access_role(self, access_id: str, role: str) -> None:
        self.client.table("user_company_accesses").update({"role": role}).eq(
            "id", access_id
        ).execute()

    def deactivate_access(self, access_id: str) -> None:
        try:
            self.client.table("user_company_accesses").update(
                {"is_active": False}
            ).eq("id", access_id).execute()
        except Exception as exc:
            raise RuntimeError(
                "Impossible de désactiver l'accès (colonne is_active absente ? "
                "Appliquer la migration user_permission_scopes)."
            ) from exc

    def set_must_change_password(self, user_id: str, value: bool) -> None:
        try:
            self.client.table("profiles").update(
                {"must_change_password": value}
            ).eq("id", user_id).execute()
        except Exception as exc:
            raise RuntimeError(
                "Colonne profiles.must_change_password absente — appliquer la migration."
            ) from exc

    def replace_permission_grants(
        self,
        user_id: str,
        company_id: str,
        granted_by: str,
        grants: list[dict[str, Any]],
    ) -> None:
        scoped_permission_repository.replace_grants_atomic(
            user_id=user_id,
            company_id=company_id,
            granted_by=granted_by,
            grants=grants,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Autorise les écritures après garde-fous."
    )
    parser.add_argument("--project-ref", default="", help="Project ref production exact.")
    parser.add_argument(
        "--confirm-production",
        default="",
        help=f"Doit être exactement {PRODUCTION_CONFIRMATION}.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "app/modules/users/data/access_manifest.json",
    )
    parser.add_argument(
        "--excel-out",
        type=Path,
        default=None,
        help="Chemin local du .xlsx (uniquement après --apply).",
    )
    return parser.parse_args()


def main() -> int:
    import json

    args = parse_args()
    if args.apply and (
        args.project_ref != PROJECT_REF
        or args.confirm_production != PRODUCTION_CONFIRMATION
    ):
        raise SystemExit(
            "--apply exige --project-ref slleauhyjnmiawosvlcg et "
            "--confirm-production=APPLY_ACCESS_MATRIX"
        )
    if args.apply and os.environ.get("SUPABASE_PROJECT_REF") not in (
        None,
        "",
        PROJECT_REF,
    ):
        raise SystemExit(
            "SUPABASE_PROJECT_REF ne cible pas le projet de production attendu"
        )

    gateway = SupabaseProvisioningGateway()
    provisioner = AccessProvisioner(load_manifest(args.manifest), gateway)
    plan = provisioner.plan()
    print(plan.to_json())
    if plan.has_conflicts:
        return 2
    if not args.apply:
        return 0

    passwords: dict[str, str] = {}
    # Accordeur : super_admin plateforme (FK profiles)
    granted_by = "00da85da-9490-459a-a576-d44e4d70a1d4"
    provisioner.apply(plan, passwords_out=passwords, granted_by=granted_by)

    # Réémission contrôlée : comptes techniques (must_change_password=True).
    manifest = load_manifest(args.manifest)
    usernames: dict[str, str] = {}
    for person in manifest.get("people") or []:
        if person.get("account") != "technical_login":
            continue
        key = person["key"]
        name = (person.get("identity") or {}).get("name") or ""
        username = (person.get("identity") or {}).get("username")
        if not username and name:
            from app.modules.employees.domain.rules import (
                build_collaborator_username_base,
            )

            parts = name.split(None, 1)
            username = build_collaborator_username_base(
                parts[0], parts[1] if len(parts) > 1 else parts[0]
            )
        if username:
            usernames[key] = username
        if key in passwords:
            continue
        # Retrouver le profil par username / nom
        profiles = gateway.list_profiles()
        matches = [
            p
            for p in profiles
            if (p.get("username") or "").casefold() == (username or "").casefold()
            or (
                f"{p.get('first_name') or ''} {p.get('last_name') or ''}".casefold()
                == name.casefold()
            )
        ]
        if len(matches) != 1:
            continue
        profile = matches[0]
        if not profile.get("must_change_password"):
            continue
        from app.modules.users.application.access_provisioning import (
            generate_initial_password,
        )

        new_password = generate_initial_password()
        gateway.client.auth.admin.update_user_by_id(
            str(profile["id"]), {"password": new_password}
        )
        gateway.set_must_change_password(str(profile["id"]), True)
        passwords[key] = new_password
    excel_path = args.excel_out or (
        ROOT / "reports" / "access-provisioning-credentials.xlsx"
    )
    write_access_workbook(
        plan, excel_path, passwords=passwords, usernames=usernames
    )
    print(
        json.dumps(
            {
                "applied": True,
                "excel": str(excel_path),
                "passwords_issued": sorted(passwords.keys()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
