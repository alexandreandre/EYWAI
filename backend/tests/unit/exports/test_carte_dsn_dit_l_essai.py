"""La carte « Déclaration mensuelle » dit ce que l'export produit vraiment (Elsa, 20/11).

Tant que le dépôt réel est fermé (`DEPOSABLE = False`), l'aperçu bloque la DSN
réelle et seul le fichier d'essai sort : la carte le dit d'emblée. Le jour où
le dépôt s'ouvre, ce test rappelle de changer la carte.
"""

from pathlib import Path

import pytest

from app.modules.dsn_export.domain import etat_conformite

pytestmark = pytest.mark.unit

CARTE = (
    Path(__file__).resolve().parents[4]
    / "frontend" / "src" / "components" / "exports" / "DsnTab.tsx"
)


def _description_de_la_carte() -> str:
    source = CARTE.read_text(encoding="utf-8")
    debut = source.index('id: "dsn_mensuelle"')
    bloc = source[debut : source.index("icon:", debut)]
    return bloc.split("description:", 1)[1]


def test_la_carte_dit_l_essai_tant_que_le_depot_est_ferme():
    description = _description_de_la_carte()
    if etat_conformite.DEPOSABLE:
        assert "ne se dépose pas encore" not in description, (
            "Le dépôt réel est ouvert : changer la description de la carte "
            "« Déclaration mensuelle » dans frontend/src/components/exports/DsnTab.tsx."
        )
    else:
        assert "fichier d'essai seulement" in description
        assert "ne se dépose pas encore" in description
