"""Jeu d'or des feuilles Colorplast : la comparaison attendu / lu est pure."""

from scripts.pointages_jeu_d_or_colorplast import bilan, comparer


def test_comparer_distingue_juste_faux_manquant_et_illisible():
    attendu = {
        "2026-07-13": 8.5,
        "2026-07-14": None,
        "2026-07-15": 8.5,
        "2026-07-16": 8.5,
        "2026-07-17": "illisible",
    }
    lu = {"2026-07-13": 8.5, "2026-07-14": 0.0, "2026-07-15": 6.5}

    assert comparer(attendu, lu) == [
        ("2026-07-13", 8.5, 8.5, "juste"),
        ("2026-07-14", None, 0.0, "juste"),
        ("2026-07-15", 8.5, 6.5, "faux"),
        ("2026-07-16", 8.5, None, "manquant"),
        ("2026-07-17", "illisible", None, "illisible"),
    ]


def test_un_jour_sans_heures_attendu_et_non_rendu_est_vide_pas_manquant():
    """Férié hachuré, case barrée : le modèle ne rend souvent aucun jour. Rien
    attendu, rien lu — c'est juste, mais compté à part pour rester visible."""
    attendu = {"2026-07-13": 0.0, "2026-07-14": None, "2026-07-15": 8.5}

    assert comparer(attendu, {"2026-07-15": 8.5}) == [
        ("2026-07-13", 0.0, None, "vide"),
        ("2026-07-14", None, None, "vide"),
        ("2026-07-15", 8.5, 8.5, "juste"),
    ]
    assert bilan([("2026-07-13", 0.0, None, "vide"), ("2026-07-15", 8.5, 8.5, "juste")]) == (2, 0, 0)


def test_le_bilan_compte_le_manquant_comme_faux_et_ecarte_l_illisible():
    lignes = [
        ("2026-07-13", 8.5, 8.5, "juste"),
        ("2026-07-15", 8.5, 6.5, "faux"),
        ("2026-07-16", 8.5, None, "manquant"),
        ("2026-07-17", "illisible", None, "illisible"),
    ]

    assert bilan(lignes) == (1, 2, 1)
