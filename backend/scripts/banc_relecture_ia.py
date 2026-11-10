"""
Banc d'essai de la relecture IA des bulletins : lecture seule, rien n'est écrit.

Fichier de cas (JSON) :
    [{"bulletin": "<id du bulletin>", "ligne": "Salaire de base"},
     {"bulletin": "<id d'un bulletin juste>", "ligne": null}]

Relit les bulletins du fichier, jusqu'à la limite, et rend trouvés, manqués,
fausses alertes, échecs et coût. Appelle l'API Anthropic : chaque bulletin coûte.
Le script vise l'environnement de `backend/.env`.

Usage :
    backend/.venv/bin/python backend/scripts/banc_relecture_ia.py cas.json
    backend/.venv/bin/python backend/scripts/banc_relecture_ia.py cas.json --limite 25 --sortie /tmp/bilan.json
"""

from __future__ import annotations

import argparse
import json
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

from app.modules.relecture_ia.application.service import (
    relire_en_lecture_seule,
)
from app.modules.relecture_ia.domain.banc import bilan_du_banc

LIMITE_PAR_DEFAUT = 10


def main() -> int:
    arguments = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    arguments.add_argument("cas", type=Path, help="Fichier JSON des cas attendus")
    arguments.add_argument("--limite", type=int, default=LIMITE_PAR_DEFAUT)
    arguments.add_argument("--sortie", type=Path, help="Écrit le bilan complet dans ce fichier")
    options = arguments.parse_args()

    cas = json.loads(options.cas.read_text(encoding="utf-8"))
    bulletins = list(dict.fromkeys(str(c["bulletin"]) for c in cas))[: options.limite]
    cas_retenus = [c for c in cas if str(c["bulletin"]) in bulletins]

    bilan = bilan_du_banc(cas_retenus, relire_en_lecture_seule(bulletins))
    print(f"Bulletins relus : {len(bulletins)}")
    print(f"Trouvés : {len(bilan['trouves'])}")
    print(f"Manqués : {len(bilan['manques'])}")
    print(f"Fausses alertes : {len(bilan['fausses_alertes'])}")
    print(f"Échecs : {len(bilan['echecs'])}")
    print(f"Coût : {bilan['cout_usd']} $")
    if options.sortie:
        options.sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
