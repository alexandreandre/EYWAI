"""Où sont les données, où vont les rapports, quelles sociétés et quels mois."""
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
DATA = RACINE / "data"
RAPPORT = DATA / "_rapports" / "rgdu-2026"
TEXTES = RACINE / "docs" / "reference" / "reduction-generale-2026"
ANNEE = 2026

SOCIETES: dict[str, dict] = {
    "colorplast": {"company_id": "dbe2b9f5-44dd-41bc-a625-36ed33d160f7", "mois": tuple(range(1, 9)), "dossier": "colorplast"},
    "comitech": {"company_id": "12cd8c71-da13-43f9-9151-475c4d5e8812", "mois": tuple(range(1, 9)), "dossier": "comitech"},
    # company_id de Mont-Blanc : lu en base à la tâche 8 (lecture seule), laissé à None ici.
    "mbc": {"company_id": None, "mois": tuple(range(1, 8)), "dossier": "mbc"},
}
