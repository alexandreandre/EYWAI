"""Sorties du rejeu : CSV nominatif (hors git), résumé agrégé et couverture sans aucune clé."""
import csv

import pytest

from scripts.verification_rgdu.comparaison import LigneComparee
from scripts.verification_rgdu.rapport import couverture, detail_a_juger, ecrire_csv, resume_agrege

pytestmark = pytest.mark.unit

CLE_A = "1999999999999/AAA"
CLE_B = "2888888888888/BBB2"


def _lignes():
    a = LigneComparee("colorplast", CLE_A, 3, 2283.0, "dsn", 2000.0, 2000.0, 12000.0, 7000.0,
                      "a_juger_quadra", 45.0, 0.0)
    b = LigneComparee("colorplast", CLE_B, 3, 1823.03, "implicite", 1823.03, None, 9000.0, 5000.0,
                      "identique", 0.0, 0.0)
    c = LigneComparee("colorplast", CLE_B, 4, None, "", 1823.03, 1823.07, 11000.0, 6823.03,
                      "donnee_manquante", 0.0, 0.0, note="mois non calculable")
    d = LigneComparee("colorplast", CLE_A, 4, 1900.0, "dsn", 1800.0, 1850.0, 14000.0, 9283.0,
                      "point_non_tranche", -12.5, 3.25, smic_loi_variante=1900.0, variante="point_1_subrogation")
    return [a, b, c, d]


def test_le_resume_agrege_ne_contient_aucune_cle_de_salarie():
    l = LigneComparee("colorplast", "1999999999999", 3, 2283.0, "dsn", 2000.0, 2000.0, 12000.0, 7000.0, "a_juger_quadra", 45.0, 0.0)
    texte = resume_agrege([l])
    assert "1999999999999" not in texte
    assert "a_juger_quadra" in texte and "45.00" in texte


def test_le_resume_compte_par_preclassement_et_par_mois_sans_cle():
    texte = resume_agrege(_lignes())
    for cle in (CLE_A, CLE_B, "AAA", "BBB2", "1999999999999", "2888888888888"):
        assert cle not in texte
    assert "| colorplast | a_juger_quadra | 1 | 45.00 | 45.00 | 0.00 | 0.00 |" in texte
    assert "| colorplast | point_non_tranche | 1 | -12.50 | 12.50 | 3.25 | 3.25 |" in texte
    assert "| colorplast | 3 | 2 |" in texte and "| colorplast | 4 | 2 |" in texte


def test_la_couverture_compte_les_trois_colonnes_par_mois_sans_cle():
    texte = couverture(_lignes())
    assert CLE_A not in texte and CLE_B not in texte
    # société, mois, lignes, Quadra DSN, Quadra implicite, Quadra absent, loi, variante, EYWAI
    assert "| colorplast | 3 | 2 | 1 | 1 | 0 | 2 | 0 | 1 |" in texte
    assert "| colorplast | 4 | 2 | 1 | 0 | 1 | 2 | 1 | 2 |" in texte


def test_le_detail_a_juger_tronque_les_cles_et_trie_par_impact():
    texte = detail_a_juger(_lignes())
    assert CLE_A not in texte and "1999999999999" not in texte
    assert "| 199 |" in texte
    assert texte.index("a_juger_quadra") < texte.index("point_non_tranche")   # 45 € avant 12,50 €
    assert "identique" not in texte


def test_le_csv_porte_toutes_les_colonnes_et_les_colonnes_du_classement_final(tmp_path):
    chemin = tmp_path / "sous" / "colorplast.csv"
    ecrire_csv(_lignes(), chemin, regles=["R-H1", "R-H1", "R-H7", "R-H4"])
    with open(chemin, encoding="utf-8") as f:
        rangs = list(csv.DictReader(f))
    assert len(rangs) == 4
    assert rangs[0]["cle"] == CLE_A and rangs[0]["preclassement"] == "a_juger_quadra"
    assert rangs[3]["variante"] == "point_1_subrogation" and rangs[3]["smic_loi_variante"] == "1900.0"
    assert rangs[2]["regles_loi"] == "R-H7" and rangs[2]["note"] == "mois non calculable"
    assert all(r["classement_final"] == "" and r["regle"] == "" and r["note_classement"] == "" for r in rangs)
