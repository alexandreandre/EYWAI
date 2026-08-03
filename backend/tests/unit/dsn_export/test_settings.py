"""Paramétrage DSN : normalisations et reprise depuis une DSN du cabinet."""

from __future__ import annotations

from app.modules.dsn_export.domain.settings import (
    SOURCE_REPRISE,
    DsnSettings,
    depuis_dict,
    extraire_depuis_dsn,
    normaliser_idcc,
    normaliser_naf,
    normaliser_telephone,
    vers_dict,
)

ENTETE = "\r\n".join(
    [
        "S10.G00.00.001,'Cegid Quadra Paie'",
        "S10.G00.01.001,'751168337'",
        "S10.G00.01.002,'00028'",
        "S10.G00.01.003,'MONT BLANC COMPOSITE'",
        "S10.G00.01.004,'1984 AVENUE DES LANDIERS'",
        "S10.G00.01.005,'73000'",
        "S10.G00.01.006,'CHAMBERY'",
        "S10.G00.02.001,'02'",
        "S10.G00.02.002,'MARTIN'",
        "S10.G00.02.004,'paie@example.fr'",
        "S10.G00.02.005,'04 79 00 00 00'",
        "S20.G00.07.001,'MARTIN'",
        "S20.G00.07.002,'0479000000'",
        "S20.G00.07.003,'paie@example.fr'",
        "S20.G00.07.004,'01'",
        "S20.G00.07.001,'MARTIN'",
        "S20.G00.07.002,'0479000000'",
        "S20.G00.07.003,'paie@example.fr'",
        "S20.G00.07.004,'13'",
        "S21.G00.06.003,'2229A'",
        "S21.G00.06.007,'SOUS LA VUAZ'",
        "S21.G00.06.015,'0292'",
    ]
).encode("latin-1")


def test_naf_perd_son_point():
    assert normaliser_naf("25.61Z") == "2561Z"
    assert normaliser_naf("2229A") == "2229A"
    assert normaliser_naf(None) == ""


def test_idcc_est_cadre_sur_quatre_chiffres():
    assert normaliser_idcc("292") == "0292"
    assert normaliser_idcc(3248) == "3248"
    assert normaliser_idcc("") == ""


def test_telephone_ne_garde_que_les_chiffres():
    assert normaliser_telephone("04 79 00 00 00") == "0479000000"
    assert normaliser_telephone("+33 4 79 00") == "+33479 00".replace(" ", "")


def test_reprise_lit_emetteur_contacts_et_idcc():
    settings = extraire_depuis_dsn(ENTETE, fichier="2026-05.dsn")
    assert settings.emetteur_siren == "751168337"
    assert settings.emetteur_raison_sociale == "MONT BLANC COMPOSITE"
    assert settings.contact_emetteur_nom == "MARTIN"
    assert settings.contact_emetteur_telephone == "0479000000"
    assert settings.naf == "2229A"
    assert settings.idcc == "0292"
    assert settings.complement_adresse == "SOUS LA VUAZ"
    assert settings.source == SOURCE_REPRISE
    assert settings.source_fichier == "2026-05.dsn"


def test_reprise_garde_un_contact_par_destinataire():
    settings = extraire_depuis_dsn(ENTETE)
    codes = [c.code_destinataire for c in settings.contacts_declaration]
    assert codes == ["01", "13"]
    assert all(c.email == "paie@example.fr" for c in settings.contacts_declaration)


def test_reprise_n_extrait_rien_de_nominatif_salarie():
    """Le paramétrage ne doit jamais capter d'état civil de salarié."""
    avec_salarie = ENTETE + b"\r\nS21.G00.30.001,'1850175123456'\r\nS21.G00.30.002,'DUPONT'"
    settings = extraire_depuis_dsn(avec_salarie)
    serialise = str(vers_dict(settings))
    assert "DUPONT" not in serialise
    assert "1850175123456" not in serialise


def test_aller_retour_par_le_stockage():
    settings = extraire_depuis_dsn(ENTETE, fichier="2026-05.dsn")
    reconstruit = depuis_dict(vers_dict(settings))
    assert reconstruit.emetteur_siren == settings.emetteur_siren
    assert len(reconstruit.contacts_declaration) == len(settings.contacts_declaration)
    assert reconstruit.idcc == settings.idcc


def test_parametrage_vide_signale_ses_manques():
    manques = DsnSettings().manques()
    assert "SIREN de l'émetteur" in manques
    assert "contacts de la déclaration" in manques
    assert not DsnSettings().est_complet()


def test_parametrage_repris_est_complet():
    assert extraire_depuis_dsn(ENTETE).est_complet()
