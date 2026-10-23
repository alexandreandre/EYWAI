"""Un bulletin enregistré dit ses lignes, ce qui s'y corrige et ce qui a été corrigé."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import construire_lignes
from app.modules.payroll.domain.explications_lignes import poser_explications
from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    RAISON_SAISIE,
)
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_du_bulletin,
    corrections_en_attente_du_bulletin,
    explication_de_correction,
    lignes_corrigeables,
    lignes_corrigees_du_bulletin,
    mentions_des_corrections,
)
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

pytestmark = pytest.mark.unit


def _bulletin():
    return {
        "en_tete": {"annee": 2026, "mois": 10},
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None},
            {"libelle": "Prime exceptionnelle", "quantite": None, "taux": None, "gain": 100.0, "perte": None, "saisie_id": "p1"},
        ],
        "details_absences": [
            {"libelle": "Absence non rémunérée du 16/10/26", "quantite": 7.0, "taux": 16.4832, "gain": None, "perte": 115.38},
        ],
        "cotisations_officielles": [
            {"code": "sante", "lignes": [
                {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2600.0, "taux_salarial": 0.0,
                 "taux_patronal": 0.07, "montant_salarial": 0.0, "montant_patronal": 182.0},
                {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None, "taux_salarial": None, "taux_patronal": None,
                 "montant_salarial": 20.0, "montant_patronal": 30.0},
            ]},
        ],
        "synthese_net": {"net_imposable": 2000.0, "impot_prelevement_a_la_source": {"base": 2000.0, "taux": 5.2, "montant": 104.0}},
    }


def _corrige():
    """Le même bulletin, salaire de base et impôt corrigés comme le moteur les pose."""
    bulletin = _bulletin()
    journal = JournalDesCorrections(
        [CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant du 01/10", base=160.0, saisie_id="c1")]
    )
    journal.corriger(bulletin["calcul_du_brut"][0], BLOC_BRUT, "brut:salaire_base")
    bulletin["synthese_net"]["impot_prelevement_a_la_source"].update(
        {"taux": 7.5, "montant": 150.0,
         "correction": {"type": "correction", "ligne": "impot", "libelle": "Impôt", "motif": "Taux DGFiP du mois", "taux": 7.5, "saisie_id": "c2"},
         "valeur_calculee": {"taux": 5.2, "montant": 104.0}}
    )
    return bulletin


def test_le_bulletin_dit_chaque_ligne_et_par_quoi_elle_se_corrige():
    lignes = {l.code: l for l in lignes_corrigeables(_bulletin())}
    assert lignes["brut:salaire_base"].mode == MODE_BASE_OU_TAUX and lignes["brut:salaire_base"].base == 151.67
    assert lignes["brut:saisie:p1"].mode is None and lignes["brut:saisie:p1"].raison == RAISON_SAISIE
    absence = lignes["brut:absence_non_remuneree:16-10-26"]
    assert absence.retenue and absence.montant == 115.38
    assert lignes["cotisation:securite_sociale_maladie"].taux_patronal == 0.07
    assert lignes["cotisation:mutuelle:mutuelle"].mode == MODE_MONTANT
    assert lignes["impot"].mode == MODE_TAUX and lignes["impot"].taux == 5.2
    assert all(l.correction is None for l in lignes.values())


def test_une_ligne_corrigee_dit_sa_correction_et_ce_que_martine_avait_calcule():
    lignes = {l.code: l for l in lignes_corrigeables(_corrige())}
    base = lignes["brut:salaire_base"]
    assert base.correction["saisie_id"] == "c1" and base.valeur_calculee["gain"] == 2500.0
    assert lignes["impot"].correction["saisie_id"] == "c2"
    assert set(corrections_du_bulletin(_corrige())) == {"c1", "c2"}
    assert lignes_corrigees_du_bulletin(_corrige()) == [
        {"famille": "brut:salaire_base", "libelle": "Salaire de base"},
        {"famille": "impot", "libelle": "Impôt sur le revenu prélevé à la source"},
    ]


def test_une_correction_en_attente_se_lit_et_se_restaure():
    bulletin = {**_bulletin(), "corrections_en_attente": [
        {"type": "correction", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)", "motif": "CDD prolongé",
         "montant": 0.0, "saisie_id": "c3", "raison": "La ligne visée n'est plus sur le bulletin."},
    ]}
    assert corrections_en_attente_du_bulletin(bulletin)[0]["saisie_id"] == "c3"
    assert corrections_du_bulletin(bulletin)["c3"].ligne == "brut:precarite"
    assert corrections_en_attente_du_bulletin(_bulletin()) == []


def test_l_info_bulle_d_une_ligne_corrigee_remplace_celle_du_calcul():
    bulletin = _corrige()
    ligne = bulletin["calcul_du_brut"][0]
    assert explication_de_correction(ligne, BLOC_BRUT) == (
        "Corrigée à la main : Avenant du 01/10. Martine avait calculé 2 500,00 €."
    )
    assert explication_de_correction(_bulletin()["calcul_du_brut"][0], BLOC_BRUT) is None
    poser_explications(bulletin)
    assert bulletin["calcul_du_brut"][0]["explication"].startswith("Corrigée à la main")
    assert "explication" not in bulletin["calcul_du_brut"][1]


def test_le_pdf_marque_la_ligne_corrigee_et_dit_pourquoi():
    lignes = construire_lignes(_corrige())
    libelles = [l["libelle"] for l in lignes]
    assert "Salaire de base *" in libelles
    notes = [l["libelle"] for l in lignes if l["type"] == "note"]
    assert "* Ligne corrigée à la main — Salaire de base : Avenant du 01/10 (Martine avait calculé 2 500,00 €)." in notes
    assert "* Taux d'impôt corrigé à la main : Taux DGFiP du mois (Martine avait appliqué un taux de 5,20 %)." in notes
    assert mentions_des_corrections(_bulletin()) == []


def test_sans_correction_le_pdf_est_celui_d_avant():
    lignes = construire_lignes(_bulletin())
    assert not any(l["libelle"].endswith(" *") for l in lignes)
    assert not any("corrigée à la main" in l["libelle"] for l in lignes if l["type"] == "note")


def test_la_valeur_calculee_d_une_cotisation_se_dit_par_part():
    from app.modules.payroll.engine.corrections_du_bulletin import valeur_calculee_fr

    assert valeur_calculee_fr(BLOC_COTISATIONS, {"montant_salarial": 12.4, "montant_patronal": 25.0}) == (
        "12,40 € salarial et 25,00 € patronal"
    )
