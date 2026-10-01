#!/usr/bin/env python3
"""Lance la mise à jour mensuelle des taux, sans navigateur.

Fenêtre : 1er, 2 et 3 du mois, 05:15 UTC (matin, heure de Paris).
Un mois déjà réussi n'est pas relancé. Les sources déjà réussies sont sautées.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Relance toutes les sources, même celles déjà réussies ce mois-ci.",
    )
    args = parser.parse_args(argv)

    from app.modules.rates.application.monthly import run_scheduled_monthly_sync

    return run_scheduled_monthly_sync(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
