"""Le libellé d'une note de frais au bulletin se lit. [G13]

Relevé à l'écran (vidéo G, 11/10/2026) : « remb restaurant 2026-10-07 » et
« remb indemnités kilométriques 2026-10-08 » — l'identifiant interne de la ligne,
sans majuscule, date au format ISO. Le bulletin dit ce qui est remboursé et le
jour de la dépense, à la française.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.frais_professionnels import (
    entree_de_note_de_frais,
    libelle_de_note_de_frais,
    ligne_de_frais_professionnels,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("type_de_frais", "jour", "attendu"),
    [
        ("Restaurant", "2026-10-07", "Note de frais : restaurant du 07/10/2026"),
        ("Hôtel", "2026-10-07", "Note de frais : hôtel du 07/10/2026"),
        ("Fournitures", "2026-07-31", "Note de frais : fournitures du 31/07/2026"),
        ("Transport", "2026-10-07", "Note de frais : transport du 07/10/2026"),
        ("Indemnités kilométriques", "2026-10-08", "Indemnités kilométriques du 08/10/2026"),
        ("Autre", "2026-10-07", "Note de frais du 07/10/2026"),
    ],
)
def test_libelle_lisible(type_de_frais, jour, attendu):
    assert libelle_de_note_de_frais(type_de_frais, jour) == attendu


def test_la_ligne_du_bulletin_porte_le_libelle():
    note = {"type": "Restaurant", "amount": 42.0, "date": "2026-10-07"}

    ligne = ligne_de_frais_professionnels(entree_de_note_de_frais(note, dans_le_mns=False))

    assert ligne["libelle"] == "Note de frais : restaurant du 07/10/2026"
    # L'identifiant ne change pas : rapprochements et exports le lisent.
    assert ligne["prime_id"] == "remb_restaurant_2026-10-07"


def test_aussi_quand_la_note_reste_dans_le_montant_net_social():
    note = {"type": "Indemnités kilométriques", "amount": 627.3, "date": "2026-09-30"}

    entree = entree_de_note_de_frais(note, dans_le_mns=True)

    assert entree["libelle"] == "Indemnités kilométriques du 30/09/2026"
