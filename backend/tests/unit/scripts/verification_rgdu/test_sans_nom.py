"""Aucun nom de salarié ne doit sortir dans un fichier versionné."""
import pytest

from scripts.verification_rgdu import sans_nom

pytestmark = pytest.mark.unit


def test_un_nom_de_la_table_est_trouve(monkeypatch):
    monkeypatch.setattr(sans_nom, "_mots_interdits", lambda: {"DUPONTEL"})
    assert sans_nom.noms_trouves("Écart pour Dupontel en mars") == ["DUPONTEL"]


def test_un_texte_sans_nom_passe(monkeypatch):
    monkeypatch.setattr(sans_nom, "_mots_interdits", lambda: {"DUPONTEL"})
    assert sans_nom.noms_trouves("Écart pour le salarié A en mars") == []
