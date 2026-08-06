"""Lecture des taux dans un fichier à blocs DSN.

Le cas témoin est réel : chez LEWIS, NOBLE Eric est déclaré à 3,50 % en type 13
(barème) en janvier 2026, puis à 26,80 % en type 01 dès février — le taux
personnalisé que la DGFiP a renvoyé dans son compte rendu métier.
"""

from app.modules.pas_rates.domain.extraction import (
    extraire_taux,
    lire_fichier,
    periode_du_fichier,
    siren_du_fichier,
)

ENTETE = (
    "S10.G00.00.006,'P26V01'\n"
    "S20.G00.05.005,'01052026'\n"
    "S21.G00.06.001,'991177304'\n"
    "S21.G00.11.001,'00029'\n"
)


def _individu(nir, nom, prenom, taux, type_taux, identifiant="", date="31052026"):
    bloc = (
        f"S21.G00.30.001,'{nir}'\n"
        f"S21.G00.30.002,'{nom}'\n"
        f"S21.G00.30.004,'{prenom}'\n"
        "S21.G00.40.001,'01012024'\n"
        f"S21.G00.50.001,'{date}'\n"
        "S21.G00.50.002,'2500.00'\n"
    )
    if taux is not None:
        bloc += f"S21.G00.50.006,'{taux}'\n"
    if type_taux:
        bloc += f"S21.G00.50.007,'{type_taux}'\n"
    if identifiant:
        bloc += f"S21.G00.50.008,'{identifiant}'\n"
    return bloc


def _lire(corps: str):
    return lire_fichier((ENTETE + corps).encode("latin-1"), "2026-05.dsn")


def test_taux_personnalise_est_lu_avec_son_type():
    dsn = _lire(_individu("1690199404042", "NOBLE", "Eric", "26.80", "01", "REF1"))
    lignes = extraire_taux(dsn)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.nom == "NOBLE"
    assert ligne.prenom == "Eric"
    assert ligne.taux == 26.8
    assert ligne.type_taux == "01"
    assert ligne.identifiant_taux == "REF1"


def test_taux_bareme_est_lu_comme_tel():
    dsn = _lire(_individu("1690199404042", "NOBLE", "Eric", "3.50", "13"))
    ligne = extraire_taux(dsn)[0]
    assert ligne.taux == 3.5
    assert ligne.type_taux == "13"


def test_taux_zero_est_conserve():
    """Un taux nul transmis par la DGFiP n'est pas une absence de taux."""
    dsn = _lire(_individu("1690199404042", "GROSSET", "Julien", "0.00", "01"))
    ligne = extraire_taux(dsn)[0]
    assert ligne.taux == 0.0
    assert ligne.type_taux == "01"


def test_dernier_versement_du_fichier_fait_foi():
    corps = (
        "S21.G00.30.001,'1690199404042'\n"
        "S21.G00.30.002,'NOBLE'\n"
        "S21.G00.30.004,'Eric'\n"
        "S21.G00.40.001,'01012024'\n"
        "S21.G00.50.001,'30042026'\n"
        "S21.G00.50.006,'3.50'\n"
        "S21.G00.50.007,'13'\n"
        "S21.G00.50.001,'31052026'\n"
        "S21.G00.50.006,'26.80'\n"
        "S21.G00.50.007,'01'\n"
    )
    ligne = extraire_taux(_lire(corps))[0]
    assert ligne.taux == 26.8
    assert ligne.type_taux == "01"


def test_individu_sans_versement_est_absent_du_resultat():
    corps = (
        "S21.G00.30.001,'1690199404042'\n"
        "S21.G00.30.002,'SANS'\n"
        "S21.G00.30.004,'Versement'\n"
        "S21.G00.40.001,'01012024'\n"
    )
    assert extraire_taux(_lire(corps)) == []


def test_periode_et_siren_du_fichier():
    dsn = _lire(_individu("1690199404042", "NOBLE", "Eric", "26.80", "01"))
    assert periode_du_fichier(dsn) == "2026-05"
    assert siren_du_fichier(dsn) == "991177304"


def test_plusieurs_individus_sont_tous_lus():
    corps = _individu("1690199404042", "NOBLE", "Eric", "26.80", "01") + _individu(
        "2800199404042", "PANNETRAT", "Sophie", "0.60", "01"
    )
    lignes = extraire_taux(_lire(corps))
    assert {l.nom for l in lignes} == {"NOBLE", "PANNETRAT"}
