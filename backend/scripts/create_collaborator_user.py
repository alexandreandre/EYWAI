#!/usr/bin/env python3
"""
Crée un compte **collaborateur** (profil + accès entreprise + Auth Supabase) avec l’email
et le mot de passe que vous choisissez.

L’**identifiant de connexion** côté app est l’**email** (contrat Supabase Auth).

Prérequis (variables d’environnement, ex. fichier ``backend/.env``) :
  - ``SUPABASE_URL``, ``SUPABASE_KEY``
  - ``SUPABASE_SERVICE_KEY`` ou ``SUPABASE_SERVICE_ROLE_KEY`` en **service_role**
    (obligatoire pour ``auth.admin.create_user``).

Usage (depuis le dossier ``backend/``) :

  python scripts/create_collaborator_user.py \\
    --company-id <UUID_ENTREPRISE> \\
    --email collaborateur@exemple.fr \\
    --password 'VotreMotDePasse'

Optionnel :
  --first-name Prénom  --last-name Nom   (sinon : Collaborateur / partie locale de l’email)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _default_names_from_email(email: str) -> tuple[str, str]:
    local = email.split("@", 1)[0].strip() or "user"
    safe = re.sub(r"[^a-zA-Z0-9\-_]", " ", local).strip() or "Collaborateur"
    return "Collaborateur", safe[:1].upper() + safe[1:] if safe else "Compte"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Créer un utilisateur collaborateur (email + mot de passe) pour une entreprise."
    )
    parser.add_argument(
        "--company-id",
        required=True,
        help="UUID de l’entreprise (table companies.id).",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email = identifiant de connexion Supabase.",
    )
    parser.add_argument(
        "--password",
        required=True,
        help="Mot de passe du compte.",
    )
    parser.add_argument("--first-name", default="", help="Prénom affiché (profil).")
    parser.add_argument("--last-name", default="", help="Nom affiché (profil).")
    args = parser.parse_args()

    first = (args.first_name or "").strip()
    last = (args.last_name or "").strip()
    if not first or not last:
        first, last = _default_names_from_email(args.email)

    # Import après parsing CLI pour charger ``load_dotenv()`` via ``app.core.settings``.
    from app.modules.super_admin.infrastructure import commands as sa_commands

    try:
        out = sa_commands.create_company_user(
            args.company_id.strip(),
            {
                "email": args.email.strip().lower(),
                "password": args.password,
                "first_name": first,
                "last_name": last,
                "role": "collaborateur",
            },
        )
    except LookupError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Erreur inattendue : {e}", file=sys.stderr)
        return 1

    user = out.get("user") or {}
    print("Compte collaborateur créé.")
    print(f"  user_id   : {user.get('id')}")
    print(f"  email     : {out.get('user', {}).get('email') or args.email.strip().lower()}")
    print(f"  rôle      : {user.get('role')}")
    print(f"  entreprise: {args.company_id.strip()}")
    print(f"  nom affiché : {user.get('first_name')} {user.get('last_name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
