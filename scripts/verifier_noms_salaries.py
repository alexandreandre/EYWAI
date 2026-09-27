#!/usr/bin/env python3
"""Refuse un commit qui ajoute le nom d'un salarié réel (dépôt public).

La liste des noms n'est jamais dans git : elle vit dans
`data/_outils/pseudonymes.json` (nom réel -> pseudonyme) et
`data/_outils/noms_regles.json` (mots ambigus), sur le poste. Sans ces
fichiers, le contrôle ne fait rien.

  verifier_noms_salaries.py            lignes ajoutées au commit en cours
  verifier_noms_salaries.py --message F    message de commit (fichier F)

Seules les lignes AJOUTÉES comptent : modifier un fichier qui porte déjà un
nom (un script de reprise, par exemple) ne bloque pas.
Contournement exceptionnel : git commit --no-verify.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TABLE = RACINE / "data/_outils/pseudonymes.json"
REGLES = RACINE / "data/_outils/noms_regles.json"
L = r"A-Za-zÀ-ÿ"


def motif() -> re.Pattern[str] | None:
    if not TABLE.exists():
        return None
    noms = json.loads(TABLE.read_text(encoding="utf-8"))
    regles = json.loads(REGLES.read_text(encoding="utf-8")) if REGLES.exists() else {}
    exclus = set(regles.get("exclus", []))
    maj = set(regles.get("majuscules_seulement", []))
    formes = []
    for nom in noms:
        if nom in exclus:
            continue
        formes.append(nom)
        if nom not in maj:
            formes.append(" ".join("-".join(p.capitalize() for p in w.split("-")) for w in nom.lower().split()))
    alt = "|".join(sorted(map(re.escape, formes), key=len, reverse=True))
    return re.compile(rf"(?<![{L}])({alt})(?![{L}])")


def lignes_ajoutees() -> list[tuple[str, str]]:
    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"],
        capture_output=True, text=True, errors="replace", cwd=RACINE,
    ).stdout
    fichier, sortie = "", []
    for ligne in diff.split("\n"):
        if ligne.startswith("+++ "):
            fichier = ligne[6:] if ligne.startswith("+++ b/") else ""
        elif ligne.startswith("+") and fichier:
            sortie.append((fichier, ligne[1:]))
    return sortie


def main() -> int:
    m = motif()
    if m is None:
        return 0
    if "--message" in sys.argv:
        texte = Path(sys.argv[sys.argv.index("--message") + 1]).read_text(encoding="utf-8", errors="replace")
        trouves = sorted({x.group(1) for x in m.finditer(texte)})
        if trouves:
            print(f"commit-msg : le message nomme un salarié ({', '.join(trouves)}). Dépôt public : utiliser un pseudonyme.")
            return 1
        return 0
    fautes = [(f, l) for f, l in lignes_ajoutees() if m.search(l)]
    if fautes:
        print("pre-commit : nom de salarié réel dans les lignes ajoutées (dépôt public) :")
        for f, l in fautes[:20]:
            print(f"  {f} : {m.sub(lambda x: '[' + x.group(1) + ']', l.strip())[:140]}")
        print("Remplacer par le pseudonyme (data/_outils/pseudonymes.json) ou un nom fictif.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
