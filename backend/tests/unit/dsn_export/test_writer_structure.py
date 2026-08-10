"""Forme du fichier plat : fin de ligne, échappement, bloc total.

Les trois règles vérifiées ici viennent des DSN réellement acceptées par
net-entreprises (celles du cabinet), seule référence dont on dispose.
"""

from __future__ import annotations

from app.modules.dsn_export.application.builder import (
    build_declaration,
    build_entreprise,
    build_envoi,
    build_etablissement,
)
from app.modules.dsn_export.domain.writer import (
    encode_dsn_bytes,
    quote_value,
    serialize_dsn_file,
)
from app.modules.dsn_import.domain.model import DsnFile

SOCIETE = {
    "siret": "80248516900022",
    "name": "COLORPLAST",
    "code_naf": "2229A",
    "address": {"rue": "ZA L'OUSSON NORD", "code_postal": "01300", "ville": "MAGNIEU"},
}


def fichier_minimal() -> DsnFile:
    entreprise = build_entreprise(SOCIETE)
    return DsnFile(
        file_name="test.dsn",
        envoi=build_envoi(),
        declaration=build_declaration("2026-05"),
        entreprise=entreprise,
        etablissement=build_etablissement(SOCIETE, entreprise),
    )


def test_l_apostrophe_n_est_pas_doublee():
    """Le cabinet écrit ``'ZA L'OUSSON NORD'`` : NEODeS n'échappe pas."""
    assert quote_value("L'ACME") == "'L'ACME'"


def test_les_lignes_se_terminent_par_crlf():
    texte = serialize_dsn_file(fichier_minimal())
    assert "\r\n" in texte
    assert "\n" not in texte.replace("\r\n", "")


def test_le_fichier_se_termine_par_le_bloc_total():
    texte = serialize_dsn_file(fichier_minimal())
    lignes = [l for l in texte.split("\r\n") if l]
    assert lignes[-2].startswith("S90.G00.90.001,")
    assert lignes[-1] == "S90.G00.90.002,'1'"


def test_le_total_compte_toutes_les_lignes_bloc_total_compris():
    texte = serialize_dsn_file(fichier_minimal())
    lignes = [l for l in texte.split("\r\n") if l]
    declare = lignes[-2].split(",'")[1].rstrip("'")
    assert int(declare) == len(lignes)


def test_le_fichier_encode_reste_relisible():
    from app.modules.dsn_import.domain.parser import parse_dsn_content

    contenu = encode_dsn_bytes(fichier_minimal())
    relu = parse_dsn_content(contenu, file_name="test.dsn")
    assert relu.envoi.norme == "P26V01"
    assert relu.entreprise.siren == "802485169"


def test_les_rubriques_d_un_bloc_sortent_par_numero_croissant():
    """La norme impose un ordre croissant à l'intérieur d'un bloc.

    Un lecteur qui rencontre un numéro inférieur au précédent tient le bloc pour
    terminé et déclare absentes les rubriques suivantes. Émettre dans l'ordre du
    dictionnaire suffisait à rendre nos DSN non déposables : DSN-VAL comptait
    18 762 anomalies sur cinq sociétés, dont 10 575 « absences » de rubriques
    pourtant présentes. Le tri seul en a supprimé 15 156.
    """
    from app.modules.dsn_export.domain.writer import _emit_rubriques_dict

    desordre = {
        "S21.G00.40.019": "80248516900022",
        "S21.G00.40.002": "06",
        "S21.G00.40.043": "3.15",
        "S21.G00.40.016": "99",
        "_interne": "ignoré",
        "S21.G00.40.001": "01122022",
    }
    sortie: list[str] = []
    _emit_rubriques_dict(desordre, sortie)

    numeros = [ligne.split(",")[0] for ligne in sortie]
    assert numeros == sorted(numeros)
    assert numeros == [
        "S21.G00.40.001",
        "S21.G00.40.002",
        "S21.G00.40.016",
        "S21.G00.40.019",
        "S21.G00.40.043",
    ]


def test_l_ordre_croissant_tient_dans_un_fichier_complet():
    texte = serialize_dsn_file(fichier_minimal())
    precedent: dict[str, str] = {}
    for ligne in texte.split("\r\n"):
        if not ligne or "," not in ligne:
            continue
        rubrique = ligne.split(",")[0]
        bloc, numero = rubrique.rsplit(".", 1)
        if bloc in precedent:
            assert numero > precedent[bloc], (
                f"{rubrique} sort après {bloc}.{precedent[bloc]} : ordre décroissant"
            )
        precedent[bloc] = numero


def test_l_adresse_avec_apostrophe_se_relit_a_l_identique():
    from app.modules.dsn_import.domain.parser import parse_dsn_content

    contenu = encode_dsn_bytes(fichier_minimal())
    relu = parse_dsn_content(contenu, file_name="test.dsn")
    rues = [
        ligne.valeur
        for ligne in relu.raw_rubriques
        if ligne.rubrique == "S21.G00.06.004"
    ]
    assert rues == ["ZA L'OUSSON NORD"]
