"""Le script qui complète les fiches ne change que les clés de son lot, rangées
là où le formulaire de la fiche les écrit."""

import pytest

from app.modules.dsn_export.domain.fiche_a_completer import manques_fiche_dsn
from scripts.completer_fiches_formulaire import (
    CORRECTIONS,
    PREMIER_PRENOM,
    Correction,
    LueEnDsn,
    colonnes_corrigees,
    lire_dsn,
    resoudre,
)


def _correction(colonne, chemin, avant, apres):
    return Correction(
        employee_id="e1", initiales="A.B.", societe="s1",
        colonne=colonne, chemin=chemin, avant=avant, apres=apres, source="test",
    )


def _cdd_sans_pcs_ni_motif():
    return {
        "id": "e1", "company_id": "s1", "contract_type": "CDD",
        "contract_end_date": "2026-12-18", "date_naissance": "1990-01-01",
        "classification_conventionnelle": {"coefficient": "700"},
        "specificites_paie": None,
    }


def test_le_pcs_va_dans_la_classification_et_le_motif_dans_la_reprise():
    fiche = _cdd_sans_pcs_ni_motif()
    nouvelles = colonnes_corrigees(fiche, [
        _correction("classification_conventionnelle", ("pcs",), None, "674a"),
        _correction("specificites_paie", ("dsn_reprise", "motif_recours"), None, "02"),
    ])
    assert nouvelles == {
        "classification_conventionnelle": {"coefficient": "700", "pcs": "674a"},
        "specificites_paie": {"dsn_reprise": {"motif_recours": "02"}},
    }
    assert manques_fiche_dsn({**fiche, **nouvelles}) == []


def test_les_autres_cles_de_la_reprise_restent():
    fiche = {**_cdd_sans_pcs_ni_motif(),
             "specificites_paie": {"pas_type": "13", "dsn_reprise": {"smic_retenu": "1792.30"}}}
    nouvelles = colonnes_corrigees(fiche, [
        _correction("specificites_paie", ("dsn_reprise", "motif_recours"), None, "02"),
    ])
    assert nouvelles == {"specificites_paie": {
        "pas_type": "13", "dsn_reprise": {"smic_retenu": "1792.30", "motif_recours": "02"},
    }}


def test_une_valeur_d_avant_differente_arrete_tout():
    fiche = {**_cdd_sans_pcs_ni_motif(),
             "classification_conventionnelle": {"pcs": "623f"}}
    with pytest.raises(SystemExit, match="la fiche a changé"):
        colonnes_corrigees(fiche, [
            _correction("classification_conventionnelle", ("pcs",), None, "674a"),
        ])


def test_un_motif_hors_de_la_liste_dsn_arrete_tout():
    with pytest.raises(SystemExit, match="motif"):
        colonnes_corrigees(_cdd_sans_pcs_ni_motif(), [
            _correction("specificites_paie", ("dsn_reprise", "motif_recours"), None, "2"),
        ])


def test_une_colonne_hors_du_formulaire_arrete_tout():
    with pytest.raises(SystemExit, match="colonne"):
        colonnes_corrigees(_cdd_sans_pcs_ni_motif(), [
            _correction("employment_status", (), "en_onboarding", "actif"),
        ])


NIR = "1900175123456"

#: Une DSN fictive : un salarié, un contrat, toutes les rubriques que le lot lit.
DSN_FICTIVE = "\n".join([
    "S21.G00.30.001,'190017512345678'",
    "S21.G00.30.002,'IMAGINAIRE'",
    "S21.G00.30.004,'ALIX MARIE-JEANNE'",
    "S21.G00.30.006,'15011990'",
    "S21.G00.30.025,'05'",
    "S21.G00.40.001,'01092026'",
    "S21.G00.40.009,'00003'",
    "S21.G00.40.010,'31082028'",
])


def _individus(tmp_path, texte=DSN_FICTIVE):
    chemin = tmp_path / "2026-09.dsn"
    chemin.write_text(texte, encoding="latin-1")
    return lire_dsn(chemin)


def _fiche_lue():
    return {"nir": NIR + "78", "first_name": "Alix", "date_naissance": None,
            "classification_conventionnelle": {}, "specificites_paie": None}


def test_le_lot_ne_porte_que_des_valeurs_que_le_formulaire_accepte(tmp_path):
    individus = _individus(tmp_path)
    for c in CORRECTIONS:
        fiche = _fiche_lue()
        assert colonnes_corrigees(fiche, [resoudre(c, fiche, individus)])


def _lue(colonne, chemin, rubrique, forme, avant=None):
    return _correction(colonne, chemin, avant, LueEnDsn(rubrique, forme))


def test_les_prenoms_lus_suivent_l_etat_civil_en_minuscules(tmp_path):
    c = resoudre(_lue("first_name", (), "S21.G00.30.004", "prenoms", PREMIER_PRENOM),
                 _fiche_lue(), _individus(tmp_path))
    assert (c.avant, c.apres) == ("Alix", "Alix Marie-Jeanne")


def test_un_prenom_de_fiche_qui_n_est_pas_le_premier_arrete_tout(tmp_path):
    fiche = {**_fiche_lue(), "first_name": "Marie"}
    with pytest.raises(SystemExit, match="premier"):
        resoudre(_lue("first_name", (), "S21.G00.30.004", "prenoms", PREMIER_PRENOM),
                 fiche, _individus(tmp_path))


def test_une_date_lue_passe_au_format_du_formulaire(tmp_path):
    c = resoudre(_lue("date_naissance", (), "S21.G00.30.006", "date"), _fiche_lue(), _individus(tmp_path))
    assert c.apres == "1990-01-15"


def test_un_salarie_absent_de_la_dsn_arrete_tout(tmp_path):
    fiche = {**_fiche_lue(), "nir": "2990175123456"}
    with pytest.raises(SystemExit, match="absent"):
        resoudre(_lue("date_naissance", (), "S21.G00.30.006", "date"), fiche, _individus(tmp_path))


def test_deux_contrats_dans_le_mois_arretent_une_rubrique_du_contrat(tmp_path):
    deux = DSN_FICTIVE + "\nS21.G00.40.001,'20092026'\nS21.G00.40.009,'00004'"
    with pytest.raises(SystemExit, match="2 contrats"):
        resoudre(_lue("classification_conventionnelle", ("numero_contrat_dsn",), "S21.G00.40.009", "code"),
                 _fiche_lue(), _individus(tmp_path, deux))
