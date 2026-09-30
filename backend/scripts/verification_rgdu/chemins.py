"""Où sont les données, où vont les rapports, quelles sociétés et quels mois."""
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Pour l'annotation de type de `parametres_de` seulement : l'import réel se
    # fait dans la fonction, pour éviter une dépendance circulaire à l'exécution.
    from scripts.verification_rgdu.oracle import Parametres

RACINE = Path(__file__).resolve().parents[3]
DATA = RACINE / "data"
RAPPORT = DATA / "_rapports" / "rgdu-2026"
TEXTES = RACINE / "docs" / "reference" / "reduction-generale-2026"
ANNEE = 2026

# Tdelta (R-F3) : Mont-Blanc à 0,3821 (50 salariés et plus), preuve un coefficient
# implicite de 0,40210 dans ses bulletins Quadra ; Colorplast et Comitech à 0,3781
# (moins de 50 salariés), preuve leur effectif (environ 9 et environ 16).
SOCIETES: dict[str, dict] = {
    "colorplast": {"company_id": "dbe2b9f5-44dd-41bc-a625-36ed33d160f7", "mois": tuple(range(1, 9)), "dossier": "colorplast", "tdelta": 0.3781},
    "comitech": {"company_id": "12cd8c71-da13-43f9-9151-475c4d5e8812", "mois": tuple(range(1, 9)), "dossier": "comitech", "tdelta": 0.3781},
    # company_id de Mont-Blanc : lu en base à la tâche 8 (lecture seule), laissé à None ici.
    "mbc": {"company_id": None, "mois": tuple(range(1, 8)), "dossier": "mbc", "tdelta": 0.3821},
}


def parametres_de(societe: str) -> "Parametres":
    """Les paramètres de la formule RGDU (oracle.Parametres) pour `societe`, avec
    son Tdelta (R-F3). Lève `KeyError` si `societe` est inconnue de `SOCIETES`.

    L'import d'`oracle` est fait ici, pas en tête de module, pour éviter une
    dépendance circulaire (oracle.py reste indépendant du reste du chantier)."""
    from scripts.verification_rgdu.oracle import Parametres

    return Parametres(tdelta=SOCIETES[societe]["tdelta"])
