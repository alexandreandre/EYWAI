"""Écrit sur disque la DSN qu'EYWAI produit, pour la soumettre à DSN-VAL.

Le validateur officiel de net-entreprises attend un fichier ; ce script le
fabrique à partir des mêmes jeux que les tests de conformité
(`data/_dsn_conformance/<societe>/<periode>/input.json`), sans toucher à la
base. Il écrit à côté la DSN de référence du cabinet, pour pouvoir soumettre
les deux et comparer les diagnostics.

Usage :
    python scripts/dsn_generer_pour_validation.py --societe colorplast
    python scripts/dsn_generer_pour_validation.py            # toutes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.dsn_export.application.builder import (  # noqa: E402
    build_parsed_dsn_from_payroll,
)
from app.modules.dsn_export.domain.settings import depuis_dict  # noqa: E402
from app.modules.dsn_export.domain.writer import encode_dsn_bytes  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "data" / "_dsn_conformance"
SORTIE = FIXTURES / "_a_valider"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe")
    args = parser.parse_args()

    SORTIE.mkdir(parents=True, exist_ok=True)

    for input_json in sorted(FIXTURES.glob("*/*/input.json")):
        societe = input_json.parent.parent.name
        periode = input_json.parent.name
        if args.societe and societe != args.societe:
            continue

        donnees = json.loads(input_json.read_text())
        fichier, avertissements = build_parsed_dsn_from_payroll(
            donnees["company"],
            donnees["employees_data"],
            donnees["periode"],
            settings=depuis_dict(donnees.get("dsn_settings")),
        )
        octets = encode_dsn_bytes(fichier)

        cible = SORTIE / f"{societe}-{periode}-eywai.dsn"
        cible.write_bytes(octets)

        reference = input_json.parent / "reference.dsn"
        copie = SORTIE / f"{societe}-{periode}-cabinet.dsn"
        copie.write_bytes(reference.read_bytes())

        lignes = octets.decode("latin-1").count("\n")
        lignes_ref = copie.read_bytes().decode("latin-1").count("\n")
        print(f"{societe} {periode}")
        print(f"  EYWAI    {cible.name:34} {len(octets):>8} o  {lignes:>6} lignes")
        print(f"  cabinet  {copie.name:34} {copie.stat().st_size:>8} o  {lignes_ref:>6} lignes")
        if avertissements:
            print(f"  {len(avertissements)} avertissement(s) de construction :")
            for message in avertissements[:5]:
                print(f"    - {message}")
            if len(avertissements) > 5:
                print(f"    ... et {len(avertissements) - 5} autres")

    print(f"\nFichiers écrits dans {SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
