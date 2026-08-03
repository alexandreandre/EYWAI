"""Le harnais de conformité doit voir ce qu'il prétend voir."""

from __future__ import annotations

from app.modules.dsn_export.domain.conformance import (
    EcartAttendu,
    comparer,
    construire_profil,
)


def fichier(*lignes: str) -> bytes:
    return "\r\n".join(lignes).encode("latin-1")


REFERENCE = fichier(
    "S10.G00.00.001,'Cegid Quadra Paie'",
    "S21.G00.06.001,'123456789'",
    "S21.G00.30.001,'1850175123456'",
    "S21.G00.30.002,'DUPONT'",
    "S21.G00.30.005,'01'",
    "S21.G00.40.017,'3248'",
    "S21.G00.81.001,'059'",
    "S21.G00.81.004,'22.74'",
    "S90.G00.90.001,'8'",
)


def test_profil_range_les_rubriques_par_individu():
    profil = construire_profil(REFERENCE)
    assert profil.nb_lignes == 9
    assert "1850175123456" in profil.individus
    assert profil.entete["S21.G00.06.001"] == ["123456789"]
    assert profil.individus["1850175123456"]["S21.G00.40.017"] == ["3248"]


def test_fichier_identique_est_conforme():
    rapport = comparer(REFERENCE, REFERENCE)
    assert rapport.conforme, rapport.texte()


def test_rubrique_absente_est_signalee():
    incomplet = fichier(*[
        ligne
        for ligne in REFERENCE.decode("latin-1").split("\r\n")
        if not ligne.startswith("S90.G00.90.001")
    ])
    rapport = comparer(incomplet, REFERENCE)
    assert rapport.manquantes == ["S90.G00.90.001"]
    assert not rapport.conforme


def test_rubrique_en_trop_est_signalee():
    bavard = REFERENCE + b"\r\nS21.G00.99.001,'X'"
    rapport = comparer(bavard, REFERENCE)
    assert rapport.en_trop == ["S21.G00.99.001"]


def test_valeur_divergente_est_signalee():
    faux = REFERENCE.replace(b"'3248'", b"'1234'")
    rapport = comparer(faux, REFERENCE)
    assert any(r == "S21.G00.40.017" for _, r, _, _ in rapport.valeurs)


def test_montant_equivalent_au_centime_pres_passe():
    arrondi = REFERENCE.replace(b"'22.74'", b"'22.740'")
    rapport = comparer(arrondi, REFERENCE)
    assert rapport.conforme, rapport.texte()


def test_doublon_de_cotisation_est_vu_comme_cardinalite():
    """Deux blocs 81 là où la référence en a un : le cas réel du code 059."""
    double = fichier(
        *REFERENCE.decode("latin-1").split("\r\n")[:-1],
        "S21.G00.81.001,'059'",
        "S21.G00.81.004,'11.37'",
        "S90.G00.90.001,'8'",
    )
    rapport = comparer(double, REFERENCE)
    assert any("S21.G00.81.004" in cle for cle, _, _ in rapport.cardinalites)
    assert not rapport.conforme


def test_ecart_declare_est_tolere_et_reste_visible():
    divergent = REFERENCE.replace(b"S21.G00.30.005,'01'", b"S21.G00.30.005,'02'")
    rapport = comparer(
        divergent,
        REFERENCE,
        ecarts_attendus=[
            EcartAttendu(
                rubrique="S21.G00.30.005",
                motif="sexe déduit du NIR, la référence le contredit",
                depuis="2026-08-03",
            )
        ],
    )
    assert rapport.conforme, rapport.texte()
    assert rapport.ecarts_toleres


def test_hors_perimetre_neutralise_un_bloc_entier():
    sans_bloc_81 = fichier(*[
        ligne
        for ligne in REFERENCE.decode("latin-1").split("\r\n")
        if not ligne.startswith("S21.G00.81")
    ])
    rapport = comparer(
        sans_bloc_81, REFERENCE, rubriques_hors_perimetre=["S21.G00.81"]
    )
    assert rapport.conforme, rapport.texte()


def test_individu_absent_est_signale():
    sans_individu = fichier(
        "S10.G00.00.001,'Cegid Quadra Paie'",
        "S21.G00.06.001,'123456789'",
        "S90.G00.90.001,'8'",
    )
    rapport = comparer(
        sans_individu,
        REFERENCE,
        rubriques_hors_perimetre=["S21.G00.40", "S21.G00.81"],
    )
    assert rapport.individus_manquants == ["1850175123456"]


def test_individus_non_juges_tant_que_leur_bloc_n_est_pas_livre():
    """Un lot qui ne traite pas encore les individus ne doit pas échouer dessus."""
    sans_individu = fichier(
        "S10.G00.00.001,'Cegid Quadra Paie'",
        "S21.G00.06.001,'123456789'",
        "S90.G00.90.001,'8'",
    )
    rapport = comparer(
        sans_individu,
        REFERENCE,
        rubriques_hors_perimetre=["S21.G00.30", "S21.G00.40", "S21.G00.81"],
    )
    assert rapport.individus_manquants == []
    assert rapport.conforme, rapport.texte()
