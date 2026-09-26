"""Un dossier de travail par génération de bulletin.

Le moteur lit ses entrées (contrat, calendriers, saisies, cumuls du mois
précédent) dans ``<dossier>/<employee_folder_name>/`` et se sert du nom de ce
dossier comme identifiant du salarié. Jusqu'au 26/09/2026, ce dossier était
partagé : ``app/runtime/payroll/data/employes/<employee_folder_name>/``. Deux
générations simultanées du même salarié (deux onglets), ou de deux homonymes
de sociétés différentes, y écrivaient les mêmes fichiers ; le nettoyage de
l'une pouvait effacer les cumuls que l'autre allait lire, et ses cumuls
repartaient alors de zéro sans alerte.

Chaque génération reçoit désormais un parent temporaire unique. Le nom du
sous-dossier ne change pas : le moteur voit exactement les mêmes chemins
relatifs et les mêmes fichiers. Le parent est supprimé en entier à la fin.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

PREFIXE = "eywai-paie-"


def nouveau_dossier_de_travail(employee_folder_name: str) -> Path:
    """Crée ``<parent temporaire unique>/<employee_folder_name>/`` et le rend."""
    parent = Path(tempfile.mkdtemp(prefix=PREFIXE))
    chemin = parent / employee_folder_name
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def _parent_temporaire(chemin: Path) -> Path | None:
    racine = Path(tempfile.gettempdir())
    for ancetre in chemin.parents:
        if ancetre.parent == racine and ancetre.name.startswith(PREFIXE):
            return ancetre
    return None


def supprimer_dossier_de_travail(chemin: Path | None) -> None:
    """Supprime le parent temporaire créé par ``nouveau_dossier_de_travail``.

    Ne supprime jamais rien d'autre : un chemin qui ne vient pas de cette
    fonction est ignoré.
    """
    if chemin is None:
        return
    parent = _parent_temporaire(chemin)
    if parent is not None:
        shutil.rmtree(parent, ignore_errors=True)
