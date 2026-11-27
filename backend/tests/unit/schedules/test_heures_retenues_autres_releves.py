"""Heures retenues : les relevés des autres clients ne changent pas (relecture du 27/11).

La colonne des heures retenues par l'entreprise ne se reconnaît que sur un
titre exact (« Total heures » à côté d'un total pointé, « Heures retenues »,
« Heures payées »), ou, sans titre, sur une colonne d'heures plausibles,
proche des heures pointées et confirmée par les lignes de total. Partout
ailleurs le lecteur rend ce qu'il rendait avant ce lot.

Classeurs synthétiques, salariés pseudonymes.
"""

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook

from app.modules.schedules.application.timesheet_import.structured_parser import (
    parse_tabular_file,
)


def _classeur(entete, lignes) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(entete)
    for ligne in lignes:
        ws.append(ligne)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _lire(entete, lignes, **options):
    return parse_tabular_file(
        _classeur(entete, lignes), "releve.xlsx", target_year=2026, target_month=10,
        options={"skip_period_filter": True, **options},
    )


def d(j):
    return datetime(2026, 10, j)


def _jours(res):
    return [(r.raw_name, r.jour, r.heures) for r in res.rows]


def _sans_retenue(res):
    assert "hours_retained" not in res.column_mapping
    assert all(r.heures_retenues is None for r in res.rows)
    assert not any("retenu" in w.lower() for w in res.warnings)
    assert not any("vérifier" in w for w in res.warnings)


# --- 1. Titres proches mais pas exacts ------------------------------------


def test_total_heures_semaine_n_est_pas_la_colonne_retenue():
    res = _lire(
        ["Date", "Nom", "Entrée", "Sortie", "Heures", "Total heures semaine"],
        [[d(1), "A", "08:00", "15:45", 7, None], [d(2), "A", "08:00", "15:45", 7, 14]],
    )
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0)]
    assert res.column_mapping["hours"] == "Heures"


def test_total_heures_nuit_n_est_pas_la_colonne_retenue():
    res = _lire(
        ["Date", "Nom", "Heures travaillées", "Total heures nuit"],
        [[d(1), "A", 7.5, 0], [d(2), "A", 8, 2]],
    )
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.5), ("A", 2, 8.0)]


def test_total_heures_theoriques_n_est_pas_la_colonne_retenue():
    res = _lire(
        ["Date", "Nom", "Entrée", "Sortie", "Heures", "Total heures théoriques"],
        [[d(1), "A", "08:00", "17:00", 8.25, 7], [d(2), "A", "08:00", "15:45", 7, 7]],
    )
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 8.25), ("A", 2, 7.0)]


def test_autres_titres_composes_jamais_retenus():
    for titre in ("Total heures sup", "Total heures contrat", "Heures prévues",
                  "Total heures badgées", "Total heures pointées", "Heures normales",
                  "Total heures jour férié"):
        res = _lire(
            ["Date", "Nom", "Tot H Poin", titre],
            [[d(1), "A", 7.0, 6.5], [d(2), "A", 7.0, 6.5]],
        )
        assert "hours_retained" not in res.column_mapping, titre
        assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0)], titre


def test_heures_normales_sup_et_total_garde_l_ancien_comportement():
    res = _lire(
        ["Date", "Nom", "Heures normales", "Heures sup", "Total heures"],
        [[d(1), "A", 7, 1, 8], [d(2), "A", 7, 0, 7]],
    )
    _sans_retenue(res)
    assert res.column_mapping["hours"] == "Heures normales"
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0)]


def test_heures_et_total_heures_en_duree_garde_l_ancien_comportement():
    res = _lire(
        ["Date", "Nom", "Heures", "Total heures"],
        [[d(1), "A", 7.5, "7:30"], [d(2), "A", 8, "8:00"]],
    )
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.5), ("A", 2, 8.0)]


def test_titres_exacts_accents_et_casse():
    for titre in ("TOTAL HEURES", "Heures retenues", "heures payées", "Heures Payees."):
        res = _lire(
            ["Date", "Nom", "Entrée 1", "Sortie 1", "Tot H Poin", titre],
            [[d(1), "A", 815, 1547, 6.78, 6.75], [d(2), "A", 800, 1545, 7.0, 7]],
        )
        assert res.column_mapping.get("hours_retained") == titre, titre
        assert res.rows[0].heures == 6.75


# --- 2. Colonne sans titre : plausible, proche des heures pointées -------

PAIRES = ["Date", "Nom", "Entrée 1", "Sortie 1", "Entrée 2", "Sortie 3", "Tot H", None, "Commentaires"]


def test_paniers_sans_titre_ne_sont_pas_des_heures():
    res = _lire(PAIRES, [
        [d(1), "A", 800, 1200, 1300, 1600, 7, 1, None],
        [d(2), "A", 800, 1200, 1300, 1600, 7, 1, None],
        [None, None, None, None, None, None, 14, 2, None],
        [d(1), "B", 800, 1200, 1300, 1700, 8, 1, None],
        [d(2), "B", 800, 1200, 1300, 1600, 7, 0, None],
        [None, None, None, None, None, None, 15, 1, None],
    ])
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0), ("B", 1, 8.0), ("B", 2, 7.0)]
    # Lignes de total sans badge : ignorées en silence.
    assert res.warnings == []


def test_horaire_theorique_sans_titre_n_est_pas_retenu():
    res = _lire(PAIRES[:-1], [
        [d(1), "A", 800, 1200, 1300, 1700, 8, 7],
        [d(2), "A", 800, 1200, 1300, 1600, 7, 7],
        [None, None, None, None, None, None, 15, 14],
        [d(1), "B", 800, 1200, 1300, 1800, 9, 7],
        [d(2), "B", 800, 1200, 1300, 1600, 7, 7],
        [None, None, None, None, None, None, 16, 14],
    ])
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 8.0), ("A", 2, 7.0), ("B", 1, 9.0), ("B", 2, 7.0)]
    assert res.warnings == []


def test_numero_de_semaine_sans_titre_sans_alerte():
    res = _lire(["Date", "Nom", "Heures", None], [[d(1), "A", 7, 40], [d(2), "A", 7, 40]])
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0)]
    assert res.warnings == []


def test_colonne_loin_des_heures_pointees_n_est_pas_retenue():
    """Plausible et confirmée par les totaux, mais à plus de 1,5 h des heures
    pointées sur la plupart des jours badgés : rejetée."""
    res = _lire(PAIRES, [
        [d(1), "A", 800, 1200, 1300, 1600, 7, 3, None],
        [d(2), "A", 800, 1200, 1300, 1600, 7, 4.5, None],
        [None, None, None, None, None, None, 14, 7.5, None],
        [d(1), "B", 800, 1200, 1300, 1700, 8, 2, None],
        [d(2), "B", 800, 1200, 1300, 1600, 7, 3.25, None],
        [None, None, None, None, None, None, 15, 5.25, None],
    ])
    _sans_retenue(res)
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0), ("B", 1, 8.0), ("B", 2, 7.0)]


def test_colonne_plausible_et_proche_lue_avec_une_note():
    res = _lire(PAIRES, [
        [d(1), "A", 815, 1200, 1300, 1547, 6.78, 6.75, None],
        [d(2), "A", 800, 1200, 1300, 1834, 9.82, 9.75, None],
        [None, None, None, None, None, None, None, 16.5, None],
        [d(1), "B", 800, 1200, 1300, 1600, 7, 7, None],
        [d(2), "B", 744, 1200, 1300, 1416, 6.28, 5.5, None],
        [None, None, None, None, None, None, None, 12.5, None],
    ])
    assert res.column_mapping["hours_retained"] == "_col_8"
    assert _jours(res) == [("A", 1, 6.75), ("A", 2, 9.75), ("B", 1, 7.0), ("B", 2, 5.5)]
    note = [w for w in res.warnings if w.startswith("Heures lues dans la colonne")]
    assert note == [
        "Heures lues dans la colonne sans titre (8e colonne) : retenues par l'entreprise, "
        "elles remplacent le calcul des badges ; aucune revue d'heures en plus sur ces jours."
    ]


def test_colonne_titree_lue_avec_une_note():
    res = _lire(
        ["Date", "Nom", "Entrée 1", "Sortie 1", "Tot H Poin", "Total heures"],
        [[d(1), "A", 815, 1547, 6.78, 6.75]],
    )
    assert res.warnings == [
        "Heures lues dans la colonne « Total heures » (6e colonne) : retenues par l'entreprise, "
        "elles remplacent le calcul des badges ; aucune revue d'heures en plus sur ces jours."
    ]


# --- 4. Cellules texte dans la colonne candidate ---------------------------


def _lignes_avec(textes):
    lignes = []
    for i, (nom, retenues) in enumerate((("A", [6.75, 7, 7, 7.25, 7]), ("B", [7, 7, 6.5, 7, 7]))):
        for j, r in enumerate(retenues, start=1):
            valeur = textes.get((nom, j), r)
            lignes.append([d(j), nom, 800, 1200, 1300, 1545, 7.0, valeur, None])
        lignes.append([None] * 7 + [sum(x for k, x in enumerate(retenues, 1) if (nom, k) not in textes), None])
    return lignes


def test_quelques_cellules_texte_comptent_comme_vides():
    res = _lire(PAIRES, _lignes_avec({("A", 3): "CP"}))
    assert res.column_mapping.get("hours_retained") == "_col_8"
    jour = next(r for r in res.rows if r.raw_name == "A" and r.jour == 3)
    assert jour.heures_retenues is None
    assert jour.heures == 7.0
    assert any("retenues vides" in n for n in jour.notes)
    assert next(r for r in res.rows if r.raw_name == "A" and r.jour == 1).heures == 6.75


def test_trop_de_cellules_texte_alerte_et_calcul_des_badges():
    textes = {("A", 2): "CP", ("A", 3): "abs", ("B", 2): "CP", ("B", 4): "abs"}
    res = _lire(PAIRES, _lignes_avec(textes))
    assert "hours_retained" not in res.column_mapping
    assert all(r.heures == 7.0 for r in res.rows)
    assert any("texte" in w for w in res.warnings)


# --- 5. Lignes de total, skip_rows ----------------------------------------


def test_ligne_de_suite_avec_badges_garde_date_illisible():
    res = _lire(
        ["Date", "Nom", "Entrée 1", "Sortie 1", "Entrée 2", "Sortie 3", "Tot H"],
        [[d(1), "A", 800, 1200, 1300, 1600, 7], [None, None, 1800, 2000, None, None, 2]],
    )
    assert _jours(res) == [("A", 1, 7.0)]
    assert res.warnings == ["Ligne 2 : date illisible."]


def test_ligne_de_total_d_un_releve_sans_badges_ignoree():
    res = _lire(
        ["Date", "Nom", "Heures"],
        [[d(1), "A", 7], [d(2), "A", 7], [None, None, 14]],
    )
    assert _jours(res) == [("A", 1, 7.0), ("A", 2, 7.0)]
    assert res.warnings == []


def test_skip_rows_compte_les_lignes_comme_avant():
    """Les lignes de total sans titre ne décalent pas `skip_rows`."""
    lignes = [
        [d(1), "A", 800, 1200, 1300, 1600, 7, 7, None],
        [None, None, None, None, None, None, None, 7, None],
        [d(2), "B", 800, 1200, 1300, 1600, 7, 7, None],
        [d(5), "B", 800, 1200, 1300, 1600, 7, 7, None],
    ]
    res = _lire(PAIRES, lignes, skip_rows=1)
    assert [(r.raw_name, r.jour) for r in res.rows] == [("B", 2), ("B", 5)]


# --- « Heures payées » suivie de « Heures sup » -----------------------------


def test_heures_sup_ne_devient_jamais_la_colonne_des_heures():
    for entete in (["Date", "Nom", "Heures payées", "Heures sup"],
                   ["Date", "Nom", "Heures sup", "Heures payées"]):
        i_payees, i_sup = entete.index("Heures payées"), entete.index("Heures sup")

        def ligne(j, payees, sup):
            l = [d(j), "A", None, None]
            l[i_payees], l[i_sup] = payees, sup
            return l

        res = _lire(entete, [ligne(1, 7, 1), ligne(2, None, 2)])
        assert res.column_mapping["hours"] == "Heures payées", entete
        jours = {r.jour: r for r in res.rows}
        assert jours[1].heures == 7.0
        # Vide dans « Heures payées » : le jour reste vide, avec sa note.
        assert jours[2].heures is None, entete
        assert any("Heures payées" in n for n in jours[2].notes), entete


def test_heures_sup_seule_n_est_pas_la_colonne_des_heures():
    from app.modules.schedules.application.timesheet_import.structured_parser import (
        detect_column_mapping,
    )

    assert "hours" not in detect_column_mapping(["Date", "Nom", "Heures sup"])


def test_fichier_avec_seulement_heures_sup_refuse_avec_une_phrase():
    """Ni heures du jour ni badges : refusé, jamais 0 h partout (scénario 12)."""
    import pytest

    from app.modules.schedules.application.exceptions import ScheduleAppError

    with pytest.raises(ScheduleAppError) as err:
        _lire(["Date", "Nom", "Heures sup"], [[d(1), "A", 2], [d(2), "A", 0]])
    assert str(err.value) == "Colonne des heures du jour introuvable : seulement « Heures sup »."
    assert err.value.status_code == 422
