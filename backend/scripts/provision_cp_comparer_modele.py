"""Compare l'export provision CP au modèle Cegid transmis par Elsa.

Lecture seule, aucune écriture. À relancer quand EYWAI aura douze mois d'historique
de paie (juin 2027) : c'est à ce moment-là seulement que l'égalité au centime a un sens.

Usage :
    ./venv/bin/python scripts/provision_cp_comparer_modele.py \\
        --societe "Cartol Industrie" --periode 2026-07 \\
        --modele "../data/_inbox/whatsapp-elsa/00000595-PROVISION CP.pdf"
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.exports.infrastructure.export_provision_cp import (  # noqa: E402
    collecter_lignes,
)


def _cle(texte: str) -> str:
    sans_accent = (
        unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^A-Z]", "", sans_accent.upper())


def lire_modele(chemin: str) -> list[dict]:
    texte = subprocess.run(
        ["pdftotext", "-layout", chemin, "-"], capture_output=True, text=True, check=True
    ).stdout
    lignes = []
    for ligne in texte.splitlines():
        nombres = re.findall(r"-?[\d ]+\.\d\d", ligne)
        if len(nombres) != 8:
            continue
        valeurs = [float(n.replace(" ", "")) for n in nombres]
        libelle = re.sub(r"\s+", " ", ligne.strip())
        libelle = libelle[: libelle.find(nombres[0].strip()[:4])].strip()
        if libelle.lower().startswith("total"):
            continue
        mots = libelle.split()
        lignes.append(
            {
                "cle": {_cle(m) for m in mots[1:] if _cle(m)},
                "libelle": " ".join(mots[1:]),
                "solde_jours": valeurs[2],
                "salaire_reference": valeurs[3],
                "taux_charges": valeurs[4],
                "provision": valeurs[6],
                "total": valeurs[7],
            }
        )
    return lignes


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--societe", required=True)
    parseur.add_argument("--periode", required=True)
    parseur.add_argument("--modele", required=True)
    args = parseur.parse_args()

    societes = supabase.table("companies").select("id, company_name").execute().data or []
    trouvees = [s for s in societes if _cle(args.societe) in _cle(s["company_name"])]
    if len(trouvees) != 1:
        print(f"Société introuvable ou ambiguë : {args.societe}")
        return 1
    company_id = trouvees[0]["id"]

    modele = lire_modele(args.modele)
    nos_lignes, avertissements = collecter_lignes(company_id, args.periode)
    print(f"Modèle : {len(modele)} lignes | EYWAI : {len(nos_lignes)} lignes")
    for a in avertissements:
        print(f"  avertissement : {a}")

    index = {
        frozenset({_cle(m) for m in l.nom.split() if _cle(m)}): l for l in nos_lignes
    }
    apparies, orphelins = [], []
    for ligne_modele in modele:
        correspondances = [
            nl
            for cles, nl in index.items()
            if ligne_modele["cle"] and ligne_modele["cle"] <= cles
        ]
        if len(correspondances) == 1:
            apparies.append((ligne_modele, correspondances[0]))
        else:
            orphelins.append(ligne_modele["libelle"])

    print(f"\nAppariés : {len(apparies)} | non rapprochés : {len(orphelins)}")
    for nom in orphelins:
        print(f"  non rapproché : {nom}")

    if not apparies:
        return 0

    for champ in ("solde_jours", "salaire_reference", "taux_charges", "provision", "total"):
        ecarts = [abs(getattr(n, champ) - m[champ]) for m, n in apparies]
        exacts = sum(1 for e in ecarts if e < 0.01)
        print(
            f"\n{champ:20s} : {exacts}/{len(ecarts)} exacts | "
            f"écart médian {statistics.median(ecarts):10.2f} | max {max(ecarts):10.2f}"
        )

    total_modele = sum(m["total"] for m, _ in apparies)
    total_eywai = sum(n.total for _, n in apparies)
    print(
        f"\nTotal modèle {total_modele:12.2f} EUR | total EYWAI {total_eywai:12.2f} EUR | "
        f"écart {total_eywai - total_modele:+12.2f} EUR "
        f"({(total_eywai - total_modele) / total_modele * 100:+.1f} %)"
    )
    print("\nRappel : l'écart sur le salaire de référence est attendu tant qu'EYWAI n'a")
    print("pas la paie 2025. Ne pas corriger le moteur sur cette base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
