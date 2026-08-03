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
