"""Quand le code PCS-ESE change, Martine note l'ancien code et la date, pour le bloc S21.G00.41.

Guide OETH de l'Urssaf (v2.5, 7 avril 2026, p. 46) : une correction de code PCS-ESE se déclare
« salarié par salarié, au niveau du bloc « Changements Contrat – S21.G00.41 » » avec la date de
modification, l'ancien code (S21.G00.41.019) et la profondeur de recalcul.
"""

from datetime import date

from app.modules.pcs_ese.domain.changement import appliquer_changement_pcs, en_attente

J = date(2026, 11, 6)


def ap(avant, apres, *, depuis_import=False, deposees=frozenset()):
    return appliquer_changement_pcs(
        avant, apres, aujourd_hui=J, depuis_import=depuis_import, periodes_declarees=deposees
    )


def test_9999_vers_vrai_code_note_l_ancien():
    r = ap({"pcs": "9999"}, {"pcs": "674a"})
    assert r["pcs"] == "674a"
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-06"}


def test_premier_code_rien_a_declarer():
    assert "pcs_changement" not in ap({}, {"pcs": "674a"})
    assert "pcs_changement" not in ap(None, {"pcs": "674a"})


def test_code_inchange_garde_le_changement_en_cours():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "674a", "idcc": "0292"})
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-02"}


def test_deux_changements_avant_depot_garde_le_premier_ancien():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "625h"})
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-06"}


def test_retour_a_l_ancien_rien_a_declarer():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    assert "pcs_changement" not in ap(avant, {"pcs": "9999"})


def test_changement_deja_declare_remplace():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-09-10"}}
    r = ap(avant, {"pcs": "625h"}, deposees={"2026-09"})
    assert r["pcs_changement"] == {"ancien": "674a", "date": "2026-11-06"}


def test_le_client_ne_fabrique_pas_de_changement():
    r = ap({"pcs": "674a"}, {"pcs": "674a", "pcs_changement": {"ancien": "1", "date": "2020-01-01"}})
    assert "pcs_changement" not in r


def test_le_client_ne_retire_pas_le_changement():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "674a"})
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-02"}


def test_import_ne_remet_pas_9999_ni_ne_note():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "9999", "idcc": "0292"}, depuis_import=True)
    assert r["pcs"] == "674a" and r["idcc"] == "0292"
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-02"}


def test_import_vrai_code_different_pas_de_changement_a_declarer():
    r = ap({"pcs": "674a"}, {"pcs": "625h"}, depuis_import=True)
    assert r["pcs"] == "625h" and "pcs_changement" not in r


def test_classification_absente_inchangee():
    assert ap({"pcs": "674a"}, None) is None


def test_en_attente():
    c = {"ancien": "9999", "date": "2026-11-06"}
    assert en_attente(c, frozenset())
    assert en_attente(c, {"2026-10"})
    assert not en_attente(c, {"2026-11"})
    assert not en_attente(c, {"2026-10", "2026-12"})
    assert not en_attente(None, frozenset())


def test_contrat_commence_ce_mois_rien_a_declarer():
    # Embauché le 03/11, code corrigé le 06/11 : le contrat n'a jamais été déclaré avec
    # l'ancien code, aucun bloc ne partira ; la fiche ne doit pas l'annoncer.
    r = appliquer_changement_pcs(
        {"pcs": "674a"}, {"pcs": "674b"}, aujourd_hui=J, depuis_import=False,
        periodes_declarees=frozenset(), debut_contrat="2026-11-03",
    )
    assert "pcs_changement" not in r
    r = appliquer_changement_pcs(
        {"pcs": "674a"}, {"pcs": "674b"}, aujourd_hui=J, depuis_import=False,
        periodes_declarees=frozenset(), debut_contrat="2026-10-31",
    )
    assert r["pcs_changement"] == {"ancien": "674a", "date": "2026-11-06"}


def test_ancien_code_hors_liste_rien_a_declarer():
    # « 311a » tapé autrefois dans la case libre : S21.G00.41.019 le ferait refuser (CRE-11).
    assert "pcs_changement" not in ap({"pcs": "311a"}, {"pcs": "674a"})
