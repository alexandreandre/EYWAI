"""Aperçu d'import DSN : des éléments perdus à l'enregistrement sont dits."""

from app.modules.dsn_import.application.service import anomalie_elements_non_enregistres


def test_tout_enregistre_rien_a_dire():
    assert anomalie_elements_non_enregistres(12, 12) is None
    assert anomalie_elements_non_enregistres(0, 0) is None


def test_des_elements_perdus_sont_dits_sans_bloquer():
    anomalie = anomalie_elements_non_enregistres(12, 9)
    assert anomalie["severity"] == "warning"
    assert anomalie["type"] == "elements_non_enregistres"
    assert anomalie["message"].startswith("3 élément(s) de la DSN sur 12 n'ont pas pu être enregistrés")


def test_rien_enregistre_du_tout():
    assert "12 élément(s) de la DSN sur 12" in anomalie_elements_non_enregistres(12, 0)["message"]
