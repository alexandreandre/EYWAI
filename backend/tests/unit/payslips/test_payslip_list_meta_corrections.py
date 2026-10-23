"""La liste des bulletins dit les lignes corrigées et les corrections en attente,
et sa réponse garde ce que l'étape 1 y mettait déjà."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections
from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta
from app.modules.payslips.schemas.responses import PayslipInfo

pytestmark = pytest.mark.unit


def _bulletin_corrige():
    ligne = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    correction = CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", base=160.0, saisie_id="c1")
    JournalDesCorrections([correction]).corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    return {
        "calcul_du_brut": [ligne],
        "corrections_en_attente": [{"saisie_id": "c3", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)",
                                    "motif": "CDD prolongé", "raison": "…"}],
    }


def test_la_liste_dit_les_lignes_corrigees_et_les_corrections_en_attente():
    meta = payslip_list_meta(_bulletin_corrige())
    assert meta["lignes_corrigees"] == [{"famille": "brut:salaire_base", "libelle": "Salaire de base"}]
    assert meta["corrections_en_attente"] == 1


def test_sans_correction_la_liste_n_en_dit_rien():
    for donnees in ({}, None):
        meta = payslip_list_meta(donnees)
        assert meta["lignes_corrigees"] == [] and meta["corrections_en_attente"] == 0


def test_la_reponse_de_liste_garde_regularisations_lignes_corrigees_et_attente():
    info = PayslipInfo(
        id="p", name="n", month=10, year=2026, url="u",
        regularisations=["Mutuelle"],
        lignes_corrigees=[{"famille": "brut:salaire_base", "libelle": "Salaire de base"}],
        corrections_en_attente=1,
    )
    sortie = info.model_dump()
    assert sortie["regularisations"] == ["Mutuelle"]
    assert sortie["lignes_corrigees"] == [{"famille": "brut:salaire_base", "libelle": "Salaire de base"}]
    assert sortie["corrections_en_attente"] == 1
