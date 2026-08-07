"""
Audit du corpus paie des conventions collectives (``full_text``).

Répond à une question précise : le corpus paie contient-il des versions
d'articles PÉRIMÉES, mélangées aux versions en vigueur ?

Le doute est légitime. KALI sert plusieurs versions d'un même article — celle en
vigueur et celles qu'elle remplace (``etat`` = REMPLACE / ABROGE). Le corpus RH
(``base_text``) est filtré pour n'en garder que les versions applicables ; le
corpus paie, lui, ne l'est pas, parce qu'y toucher change les grilles de minima
sur lesquelles reposent les bulletins.

Ce script mesure l'écart au lieu de le supposer. Il rejoue la construction du
corpus paie deux fois — telle qu'elle est faite aujourd'hui, puis avec le filtre
de version — et montre ce qui disparaîtrait.

Mesuré le 07/08/2026 :
    IDCC 3248 (métallurgie) : écart NUL. Corpus propre.
    IDCC 0292 (plasturgie)  : 3 238 caractères, soit 4 %, et uniquement
                              4 lignes de préambule (« les parties signataires
                              entendent remplacer la grille de 1979 »).
                              Aucune grille, aucun taux, aucun coefficient.

Conclusion : ne pas filtrer le corpus paie. Le gain est nul et le changement
déclencherait une ré-extraction des règles de paie pour rien.

Attention à ne pas confondre avec les homonymes légitimes : un article « 1 »
peut apparaître douze fois dans le corpus paie de la métallurgie, parce qu'il y
a douze accords salariaux départementaux, chacun avec son propre article 1.
Compter les numéros en double ne prouve donc RIEN — seule la comparaison avec
et sans filtre est concluante.

Usage :
    venv/bin/python scripts/audit_corpus_paie.py
    venv/bin/python scripts/audit_corpus_paie.py --idcc 0292
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _charger_env() -> None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for ligne in env_file.read_text().splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_env()

from app.core.database import get_supabase_client  # noqa: E402
from app.modules.collective_agreements.infrastructure.kali_client import (  # noqa: E402
    KaliClient,
)

# Au-delà de ce seuil, l'écart ne peut plus être tenu pour du texte de contexte
# et mérite un examen article par article avant toute décision.
SEUIL_ALERTE_CARACTERES = 5_000


def _corpus_paie(client: KaliClient, top_sections: list, idcc: str, *, filtre: bool) -> str:
    """Reconstruit le corpus paie, avec ou sans filtre de version."""
    original = client._fetch_subsection_text
    if filtre:
        def _filtre(sub, **kwargs):
            kwargs["versions_en_vigueur_seulement"] = True
            return original(sub, **kwargs)

        client._fetch_subsection_text = _filtre
    try:
        salaires, _, _ = client._collect_salary_texts(top_sections, idcc=idcc)
        annexes, _, _ = client._collect_payroll_annexes(top_sections, idcc=idcc)
    finally:
        client._fetch_subsection_text = original
    return "\n\n".join(salaires + annexes)


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--idcc", help="n'auditer qu'une convention")
    args = parseur.parse_args()

    lignes = (
        get_supabase_client()
        .table("collective_agreements_catalog")
        .select("idcc, name")
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    conventions = [
        ligne for ligne in lignes
        if not args.idcc or str(ligne.get("idcc")) == args.idcc
    ]
    if not conventions:
        raise SystemExit("Aucune convention à auditer.")

    client = KaliClient()
    client.require_configured()
    suspectes = 0

    for convention in conventions:
        idcc = str(convention["idcc"])
        print(f"\nIDCC {idcc} — {str(convention.get('name'))[:60]}")
        try:
            meta = client.resolve_convention(idcc)
            conteneur = client._post("consult/kaliCont", {"id": meta.kalicont_id})
            top = (conteneur.get("conteneur") or conteneur).get("sections") or []
        except Exception as exc:  # noqa: BLE001
            print(f"  KALI indisponible : {exc}")
            continue

        actuel = _corpus_paie(client, top, idcc, filtre=False)
        filtre = _corpus_paie(client, top, idcc, filtre=True)
        ecart = len(actuel) - len(filtre)
        part = 100 * ecart / len(actuel) if actuel else 0.0
        print(f"  actuel {len(actuel)} car. | filtré {len(filtre)} car. "
              f"| écart {ecart} ({part:.1f} %)")

        if ecart == 0:
            print("  aucune version périmée.")
            continue

        retirees = [
            ligne[1:].strip()
            for ligne in difflib.unified_diff(
                actuel.splitlines(), filtre.splitlines(), lineterm="", n=0
            )
            if ligne.startswith("-") and not ligne.startswith("---")
        ]
        print(f"  {len(retirees)} ligne(s) concernée(s) :")
        for ligne in retirees[:5]:
            print(f"    {ligne[:150]}")

        # Un écart n'est préoccupant que s'il porte sur des montants : c'est de
        # là que viendraient des minima faux sur un bulletin.
        chiffrees = [
            ligne for ligne in retirees
            if any(mot in ligne.lower() for mot in ("€", "euro", "coefficient", "taux", "indice"))
        ]
        if chiffrees or ecart > SEUIL_ALERTE_CARACTERES:
            suspectes += 1
            print("  À EXAMINER : l'écart touche des montants ou dépasse le seuil.")
            for ligne in chiffrees[:5]:
                print(f"    {ligne[:150]}")
        else:
            print("  Écart sans enjeu : texte de contexte, aucun montant.")

    print()
    if suspectes:
        print(f"{suspectes} convention(s) à examiner avant tout backtest.")
        return 1
    print("Aucune convention ne justifie de toucher au corpus paie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
