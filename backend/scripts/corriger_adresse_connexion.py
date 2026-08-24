"""
Remplacer une adresse fabriquée par la vraie adresse du salarié.

148 salariés actifs se connectent aujourd'hui avec une adresse forgée à
l'import DSN (`import.xxx@…dsn-import.local`) ou à la création du compte
(`prenom.nom@eywai.access.local`). Ces boîtes n'existent pas : la personne ne
peut ni recevoir de lien d'activation, ni réinitialiser son mot de passe, ni
recevoir son bulletin.

Deux écritures par salarié, qui doivent aller ensemble :
  - le compte Auth, via l'API d'administration — elle seule met à jour
    l'identité de connexion ; un UPDATE SQL sur `auth.users` la laisserait
    désynchronisée et la connexion casserait ;
  - `employees.email`, l'adresse à laquelle l'application écrit.

    python -m scripts.corriger_adresse_connexion --employe DUPONT --adresse a@b.fr
    python -m scripts.corriger_adresse_connexion --fichier data/_audits/adresses/xxx.xlsx
    ... puis relancer avec --appliquer

Sans `--appliquer`, rien n'est écrit. Le projet visé est affiché avant toute
écriture : `backend/.env` pointe sur la PRODUCTION.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

FORME_ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _projet_vise() -> str:
    url = os.environ.get("SUPABASE_URL", "")
    ref = url.split("//")[-1].split(".")[0] if "//" in url else "?"
    return ref


def _trouver_salarie(cle: str) -> List[Dict]:
    """Fiches correspondant à un identifiant, un matricule ou un nom."""
    champs = "id, matricule, first_name, last_name, email, user_id, company_id"
    if re.fullmatch(r"[0-9a-fA-F-]{36}", cle):
        return (
            supabase.table("employees").select(champs).eq("id", cle).execute().data
            or []
        )
    trouves = (
        supabase.table("employees").select(champs).eq("matricule", cle).execute().data
        or []
    )
    if trouves:
        return trouves
    return (
        supabase.table("employees")
        .select(champs)
        .ilike("last_name", cle)
        .execute()
        .data
        or []
    )


def _adresse_deja_prise(adresse: str, sauf_user_id: Optional[str]) -> bool:
    """Un AUTRE compte Auth porte-t-il déjà cette adresse ?"""
    try:
        page = supabase.auth.admin.list_users()
    except Exception as exc:  # pragma: no cover - dépend du service
        print(f"  impossible de vérifier les doublons : {str(exc)[:70]}")
        return False
    comptes = getattr(page, "users", page) or []
    for compte in comptes:
        courriel = (getattr(compte, "email", "") or "").lower()
        if courriel == adresse.lower() and str(getattr(compte, "id", "")) != str(
            sauf_user_id or ""
        ):
            return True
    return False


def _verifier(fiche: Dict, adresse: str) -> Optional[str]:
    """Motif de refus, ou None si la correction est légitime."""
    if not FORME_ADRESSE.match(adresse):
        return f"« {adresse} » n'est pas une adresse"
    if is_dsn_import_placeholder_email(adresse):
        return "l'adresse cible est elle-même fabriquée"
    actuelle = (fiche.get("email") or "").strip()
    if actuelle and not is_dsn_import_placeholder_email(actuelle):
        if actuelle.lower() == adresse.lower():
            return "déjà à jour"
        return f"la fiche porte déjà une adresse réelle ({actuelle}) — à trancher à la main"
    return None


def corriger(fiche: Dict, adresse: str, appliquer: bool) -> Tuple[bool, str]:
    refus = _verifier(fiche, adresse)
    if refus:
        return False, refus

    user_id = fiche.get("user_id")
    if user_id and _adresse_deja_prise(adresse, str(user_id)):
        return False, "adresse déjà portée par un autre compte"

    if not appliquer:
        cible = "compte Auth + fiche" if user_id else "fiche seule (aucun compte lié)"
        return True, f"à corriger — {cible}"

    if user_id:
        supabase.auth.admin.update_user_by_id(
            str(user_id), {"email": adresse, "email_confirm": True}
        )
    supabase.table("employees").update({"email": adresse}).eq(
        "id", fiche["id"]
    ).execute()
    return True, "corrigé"


def _lire_fichier(chemin: Path) -> List[Tuple[str, str]]:
    """(clé du salarié, adresse) depuis un classeur produit par
    `scripts.adresses_manquantes` — colonne « Adresse à renseigner »."""
    import openpyxl

    classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    feuille = classeur.active
    lignes = list(feuille.iter_rows(values_only=True))
    if not lignes:
        return []
    entetes = [str(c or "").strip() for c in lignes[0]]
    try:
        i_cle = entetes.index("Matricule")
        i_adresse = entetes.index("Adresse à renseigner")
    except ValueError:
        raise SystemExit(
            "Colonnes attendues absentes : « Matricule » et « Adresse à renseigner »."
        )
    couples = []
    for ligne in lignes[1:]:
        cle = str(ligne[i_cle] or "").strip()
        adresse = str(ligne[i_adresse] or "").strip()
        if cle and adresse:
            couples.append((cle, adresse))
    return couples


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--employe", help="identifiant, matricule ou nom")
    parseur.add_argument("--adresse", help="la vraie adresse")
    parseur.add_argument("--fichier", help="classeur d'adresses à renseigner")
    parseur.add_argument("--appliquer", action="store_true")
    options = parseur.parse_args()

    if options.fichier:
        couples = _lire_fichier(Path(options.fichier))
    elif options.employe and options.adresse:
        couples = [(options.employe, options.adresse)]
    else:
        parseur.error("donner --fichier, ou --employe et --adresse")

    print(f"\nProjet visé : {_projet_vise()}")
    print(f"Mode        : {'ÉCRITURE' if options.appliquer else 'simulation'}")
    print("=" * 66)

    corriges = refuses = 0
    for cle, adresse in couples:
        fiches = _trouver_salarie(cle)
        if len(fiches) != 1:
            quoi = "aucune fiche" if not fiches else f"{len(fiches)} fiches"
            print(f"  {cle:<22} {quoi} — ignoré")
            refuses += 1
            continue
        fiche = fiches[0]
        nom = f"{fiche.get('last_name')} {fiche.get('first_name')}"
        ok, message = corriger(fiche, adresse, options.appliquer)
        marque = "✓" if ok else "·"
        print(f"  {marque} {nom:<28} {adresse:<32} {message}")
        corriges += ok
        refuses += not ok

    print("=" * 66)
    verbe = "corrigées" if options.appliquer else "à corriger"
    print(f"{corriges} {verbe}, {refuses} laissées de côté")
    if not options.appliquer and corriges:
        print("Relancer avec --appliquer pour écrire.\n")
    else:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
