"""Essai en lecture d'une nouvelle clé Supabase (R-613), sans rien écrire.

    ESSAI_SUPABASE_CLE=sb_secret_... SUPABASE_URL=https://....supabase.co python scripts/essai_cle_supabase.py

Lit une ligne de `companies`, en ne gardant que son identifiant, puis appelle l'administration
d'Auth pour vérifier les droits service_role. N'affiche ni la clé ni aucune donnée.
"""
import os
import sys

from supabase import create_client


def main() -> int:
    url, cle = os.environ["SUPABASE_URL"], os.environ["ESSAI_SUPABASE_CLE"]
    if not cle.startswith("sb_secret_"):
        print("Refus : ESSAI_SUPABASE_CLE doit être une clé sb_secret_.")
        return 2
    client = create_client(url, cle)
    lignes = client.table("companies").select("id").limit(1).execute().data
    print(f"Lecture de la base : {len(lignes)} ligne (attendu : 1).")
    utilisateurs = client.auth.admin.list_users(page=1, per_page=1)
    print(f"Administration d'Auth : {len(utilisateurs)} utilisateur lu (attendu : 1).")
    return 0 if lignes and utilisateurs else 1


if __name__ == "__main__":
    sys.exit(main())
