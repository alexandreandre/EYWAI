"""Nom et extension des fichiers d'export pour le cabinet comptable.

Quadra (ASCII à largeur fixe) et Sage (lignes séparées par « | ») sont des
fichiers texte, quel que soit le format demandé à l'écran : ils se nomment
« .txt ». Seul le format générique est un vrai CSV ou un vrai classeur.
"""

from __future__ import annotations

#: Exports cabinet dont le contenu est toujours du texte brut.
EXPORTS_CABINET_TEXTE = frozenset({"export_cabinet_quadra", "export_cabinet_sage"})

_LIBELLES = {
    "export_cabinet_generique": "cabinet_generique",
    "export_cabinet_quadra": "cabinet_quadra",
    "export_cabinet_sage": "cabinet_sage",
}


def nom_fichier_cabinet(export_type: str, period: str, format_demande: str) -> tuple[str, str]:
    """(nom du fichier, extension) d'un export cabinet."""
    extension = "txt" if export_type in EXPORTS_CABINET_TEXTE else format_demande
    libelle = _LIBELLES.get(export_type, "cabinet")
    return f"{libelle}_{period.replace('-', '_')}.{extension}", extension
