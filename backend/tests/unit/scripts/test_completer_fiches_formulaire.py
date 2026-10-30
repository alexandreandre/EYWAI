"""Le script qui complète les fiches ne change que les clés de son lot, rangées
là où le formulaire de la fiche les écrit."""

import pytest

from app.modules.dsn_export.domain.fiche_a_completer import manques_fiche_dsn
from scripts.completer_fiches_formulaire import (
    CORRECTIONS,
    Correction,
    colonnes_corrigees,
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


def test_le_lot_ne_porte_que_des_valeurs_que_le_formulaire_accepte():
    for c in CORRECTIONS:
        fiche = {"classification_conventionnelle": {}, "specificites_paie": None}
        assert colonnes_corrigees(fiche, [c])
