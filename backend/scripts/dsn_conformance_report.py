"""Affiche l'écart entre notre DSN et celle du cabinet, société par société.

Même diff que les tests, mais lisible et paramétrable : sert à piloter le
chantier de conformité lot par lot.

Usage :
    python scripts/dsn_conformance_report.py
    python scripts/dsn_conformance_report.py --societe colorplast --bloc S21.G00.40
    python scripts/dsn_conformance_report.py --tout       # sans filtre de périmètre
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
from app.modules.dsn_export.domain.conformance import comparer  # noqa: E402
from app.modules.dsn_export.domain.settings import depuis_dict  # noqa: E402
from app.modules.dsn_export.domain.writer import encode_dsn_bytes  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "data" / "_dsn_conformance"


def charger_perimetre():
    """Reprend le périmètre courant des tests pour ne pas le dupliquer."""
    sys.path.insert(0, str(RACINE / "backend" / "tests" / "unit" / "dsn_export"))
    import test_conformance_reelle as tcr  # type: ignore

    return tcr.BLOCS_A_VENIR, tcr.ECARTS_ATTENDUS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe")
    parser.add_argument("--bloc", help="ne montrer qu'un bloc, ex. S21.G00.40")
    parser.add_argument(
        "--tout", action="store_true", help="ignorer le périmètre par lot"
    )
    parser.add_argument("--limite", type=int, default=25)
    args = parser.parse_args()

    a_venir, ecarts = charger_perimetre()
    if args.tout:
        a_venir = []
    if args.bloc:
        a_venir = [b for b in a_venir if b != args.bloc]

    for input_json in sorted(FIXTURES.glob("*/*/input.json")):
        societe = input_json.parent.parent.name
        if args.societe and societe != args.societe:
            continue
        donnees = json.loads(input_json.read_text())
        fichier, avertissements = build_parsed_dsn_from_payroll(
            donnees["company"],
            donnees["employees_data"],
            donnees["periode"],
            settings=depuis_dict(donnees.get("dsn_settings")),
        )
        rapport = comparer(
            encode_dsn_bytes(fichier),
            (input_json.parent / "reference.dsn").read_bytes(),
            ecarts_attendus=ecarts,
            rubriques_hors_perimetre=a_venir,
        )
        if args.bloc:
            rapport.manquantes = [r for r in rapport.manquantes if r.startswith(args.bloc)]
            rapport.valeurs = [v for v in rapport.valeurs if v[1].startswith(args.bloc)]
            rapport.cardinalites = [
                c for c in rapport.cardinalites if args.bloc in c[0]
            ]
        print(f"\n{'=' * 70}\n{societe} {donnees['periode']}")
        print(rapport.texte(limite=args.limite))
        if avertissements:
            print(f"\n{len(avertissements)} avertissement(s) de construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
