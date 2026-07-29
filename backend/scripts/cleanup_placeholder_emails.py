#!/usr/bin/env python3
"""Reprise des adresses e-mail fabriquées (fiches salarié + comptes Auth).

Par défaut : lecture seule, plan JSON. Rien n'est modifié.
--apply exige project_ref exact + confirmation production, et sauvegarde l'état avant
modification.

Trois opérations, activables séparément :

  --clear-fiches     vide `employees.email` quand l'adresse est fabriquée.
                     Sans effet sur les connexions : le login passe par l'identifiant
                     prenom.nom puis par `user_id`, jamais par l'adresse de la fiche.

  --realign-logins   aligne l'adresse du compte Auth sur l'adresse réelle de la fiche,
                     uniquement quand l'adresse du compte est fabriquée.

Les deux opérations sont indépendantes et idempotentes. Un second passage produit un plan
vide.

Exemples :

    python scripts/cleanup_placeholder_emails.py                      # plan complet
    python scripts/cleanup_placeholder_emails.py --realign-logins     # plan restreint
    python scripts/cleanup_placeholder_emails.py --realign-logins --apply \\
        --project-ref <ref> --confirm-production=APPLY_EMAIL_CLEANUP
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.employees.domain.rules import (  # noqa: E402
    is_dsn_import_placeholder_email,
)
from app.modules.users.application.access_provisioning import PROJECT_REF  # noqa: E402

PRODUCTION_CONFIRMATION = "APPLY_EMAIL_CLEANUP"
BACKUP_DIR = ROOT / "reports"


def _load_auth_emails(client: Any) -> dict[str, str]:
    """Adresse de chaque compte Auth, indexée par user_id."""
    emails: dict[str, str] = {}
    page = 1
    while page <= 50:
        batch = client.auth.admin.list_users(page=page, per_page=200) or []
        users = batch if isinstance(batch, list) else getattr(batch, "users", [])
        if not users:
            break
        for user in users:
            emails[str(user.id)] = getattr(user, "email", "") or ""
        if len(users) < 200:
            break
        page += 1
    return emails


def build_plan(client: Any) -> dict[str, Any]:
    companies = {
        str(row["id"]): row.get("company_name") or str(row["id"])
        for row in (client.table("companies").select("id,company_name").execute().data or [])
    }
    employees = (
        client.table("employees")
        .select("id,company_id,first_name,last_name,email,user_id,employment_status")
        .execute()
        .data
        or []
    )
    auth_emails = _load_auth_emails(client)

    clear_fiches: list[dict[str, Any]] = []
    realign_logins: list[dict[str, Any]] = []

    for emp in employees:
        societe = companies.get(str(emp.get("company_id")), "?")
        nom = f"{emp.get('last_name') or ''} {emp.get('first_name') or ''}".strip()
        fiche_email = (emp.get("email") or "").strip()
        user_id = str(emp.get("user_id") or "").strip()

        if is_dsn_import_placeholder_email(fiche_email):
            clear_fiches.append(
                {
                    "employee_id": str(emp["id"]),
                    "societe": societe,
                    "salarie": nom,
                    "statut": emp.get("employment_status"),
                    "adresse_retiree": fiche_email,
                }
            )
        elif fiche_email and user_id:
            login = auth_emails.get(user_id, "")
            if is_dsn_import_placeholder_email(login):
                realign_logins.append(
                    {
                        "employee_id": str(emp["id"]),
                        "user_id": user_id,
                        "societe": societe,
                        "salarie": nom,
                        "login_actuel": login,
                        "login_cible": fiche_email.lower(),
                    }
                )

    return {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "clear_fiches": clear_fiches,
        "realign_logins": realign_logins,
        "resume": {
            "fiches_a_vider": len(clear_fiches),
            "logins_a_realigner": len(realign_logins),
        },
    }


def _write_backup(plan: dict[str, Any]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / f"placeholder_emails_backup_{stamp}.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)
    return path


def apply_plan(
    client: Any,
    plan: dict[str, Any],
    *,
    clear_fiches: bool,
    realign_logins: bool,
) -> dict[str, int]:
    done = {"fiches_videes": 0, "logins_realignes": 0, "echecs": 0}

    if clear_fiches:
        for row in plan["clear_fiches"]:
            try:
                client.table("employees").update({"email": None}).eq(
                    "id", row["employee_id"]
                ).execute()
                done["fiches_videes"] += 1
            except Exception as exc:  # noqa: BLE001 — une fiche en échec n'arrête rien
                done["echecs"] += 1
                print(f"[echec] fiche {row['salarie']} : {exc}", file=sys.stderr)

    if realign_logins:
        for row in plan["realign_logins"]:
            try:
                client.auth.admin.update_user_by_id(
                    row["user_id"],
                    {"email": row["login_cible"], "email_confirm": True},
                )
                done["logins_realignes"] += 1
            except Exception as exc:  # noqa: BLE001 — souvent une adresse déjà prise
                done["echecs"] += 1
                print(f"[echec] login {row['salarie']} : {exc}", file=sys.stderr)

    return done


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear-fiches", action="store_true")
    parser.add_argument("--realign-logins", action="store_true")
    parser.add_argument(
        "--apply", action="store_true", help="Autorise les écritures après garde-fous."
    )
    parser.add_argument("--project-ref", default="", help="Project ref production exact.")
    parser.add_argument(
        "--confirm-production",
        default="",
        help=f"Doit être exactement {PRODUCTION_CONFIRMATION}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Sans sélection explicite, on planifie tout mais on n'applique rien.
    clear_fiches = args.clear_fiches
    realign_logins = args.realign_logins
    if args.apply and not (clear_fiches or realign_logins):
        raise SystemExit(
            "--apply exige --clear-fiches et/ou --realign-logins : "
            "refus d'appliquer une opération non demandée"
        )

    if args.apply and (
        args.project_ref != PROJECT_REF
        or args.confirm_production != PRODUCTION_CONFIRMATION
    ):
        raise SystemExit(
            f"--apply exige --project-ref {PROJECT_REF} et "
            f"--confirm-production={PRODUCTION_CONFIRMATION}"
        )
    if args.apply and os.environ.get("SUPABASE_PROJECT_REF") not in (None, "", PROJECT_REF):
        raise SystemExit("SUPABASE_PROJECT_REF ne cible pas le projet de production attendu")

    client = get_supabase_admin_client()
    plan = build_plan(client)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if not args.apply:
        return 0

    backup = _write_backup(plan)
    print(f"\nSauvegarde de l'état avant modification : {backup}", file=sys.stderr)
    done = apply_plan(
        client, plan, clear_fiches=clear_fiches, realign_logins=realign_logins
    )
    print(json.dumps(done, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1 if done["echecs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
