"""Reprise MAJI et Zone 404 : juillet à septembre 2026 copiés de Quadra, bascule au 30/09.

Demande du 03/11/2026 : mettre juillet, août et septembre sur l'environnement de test,
pour faire octobre dans Martine. Même doctrine et même programme que Comitech
(`scripts/reprise_comitech.py`) : le passé appartient à Quadra, il se copie ; au mois de
bascule, un solde d'ouverture par salarié (cumuls, base de la réduction générale,
congés, repos des cadres), puis la bascule de la société.

Ce qui change pour ces deux sociétés :
- janvier à juin sont déjà en base, calculés par Martine (rejeu du 14/09) : seuls
  juillet, août et septembre sont écrits (`mois_ecrits`) ; l'ouverture au 30/09 se lit,
  elle, sur les bulletins Quadra de janvier à septembre ;
- leurs bulletins n'impriment pas le numéro de sécurité sociale : la fiche se retrouve
  par le matricule Quadra (`fiche_du_bulletin`) ;
- moins de 50 salariés : Tdelta de la réduction 2026 à 0,3781.

Les PDF mensuels sont dans data/<société>/bulletins/2026-MM/ (juin à septembre découpés
du PDF « 2026-06-a-09 » le 03/11).

Usage (depuis backend/) :
    python -m scripts.reprise_maji_zone --societe zone             # simulation
    python -m scripts.reprise_maji_zone --societe maji --sans A,B  # simulation, sans ces matricules
    python -m scripts.reprise_maji_zone --societe maji --apply     # écrit
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETES = {
    "maji": "113b2f33-82ec-4cec-8d3a-f16cda8f74f2",
    "zone": "03fb17a5-134b-4c6e-9927-2083370c44d4",
}
#: Moins de 50 salariés (R-F3, verification_rgdu/chemins.py).
TDELTA = 0.3781
BASCULE = 9
MOIS_ECRITS = (7, 8, 9)


def main(societe: str, appliquer: bool, sans: tuple[str, ...] = ()) -> int:
    from scripts import reprise_comitech as programme

    programme.regler_pour(societe, SOCIETES[societe], TDELTA)
    return programme.main(appliquer, BASCULE, sans, MOIS_ECRITS)


if __name__ == "__main__":
    if "--societe" not in sys.argv:
        raise SystemExit("--societe maji|zone")
    societe = sys.argv[sys.argv.index("--societe") + 1]
    if societe not in SOCIETES:
        raise SystemExit(f"Société inconnue : {societe}")
    sans: tuple[str, ...] = ()
    if "--sans" in sys.argv:
        sans = tuple(m.strip().upper() for m in sys.argv[sys.argv.index("--sans") + 1].split(",") if m.strip())
    raise SystemExit(main(societe, "--apply" in sys.argv, sans))
