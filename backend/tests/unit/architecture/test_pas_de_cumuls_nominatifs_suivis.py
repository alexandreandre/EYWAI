"""Aucun fichier de paie d'un salarié réel n'est suivi par git.

Le générateur écrit ses fichiers de travail sous
`app/runtime/payroll/data/employes/<NOM_Prénom>/`. Le dépôt est public : des
cumuls de salariés réels y ont été commités plusieurs fois par accident, puis
retirés le 26/09/2026. Seuls les dossiers fictifs de test (`TEST_MIG_*`) et le
`.gitkeep` y ont leur place.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[4]
DOSSIER = "backend/app/runtime/payroll/data/employes"


def _fichiers_suivis() -> list[str]:
    if shutil.which("git") is None or not (RACINE_DEPOT / ".git").exists():
        pytest.skip("dépôt git indisponible")
    sortie = subprocess.run(
        ["git", "ls-files", DOSSIER], cwd=RACINE_DEPOT, capture_output=True, text=True, check=True
    )
    return sortie.stdout.splitlines()


def test_seuls_les_dossiers_fictifs_sont_suivis():
    interdits = [
        f for f in _fichiers_suivis() if "/TEST_MIG_" not in f and not f.endswith("/.gitkeep")
    ]
    assert interdits == [], f"{len(interdits)} fichier(s) de salarié réel suivis par git"
