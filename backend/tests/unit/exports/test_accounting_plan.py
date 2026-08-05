"""Référentiel comptable : rattachement des cotisations aux organismes."""

import pytest

from app.modules.exports.domain.accounting_plan import (
    COTI_TO_ORGANISME,
    ORGANISME_MUTUELLE,
    ORGANISME_PREVOYANCE,
    ORGANISME_RETRAITE,
    ORGANISME_RETRAITE_SUP,
    ORGANISME_URSSAF,
    default_accounts_for,
    resolve_organisme_from_coti_id,
)

pytestmark = pytest.mark.unit


class TestResolutionParCotiId:
    def test_cotisations_urssaf_reconnues(self):
        """Les cotisations recouvrées par l'URSSAF ne portent pas 'URSSAF' dans
        leur libellé — c'est le défaut que ce référentiel corrige."""
        for coti_id in (
            "securite_sociale_maladie",
            "allocations_familiales",
            "assurance_chomage",
            "ags",
            "at_mp",
            "retraite_secu_plafond",
            "retraite_secu_deplafond",
            "csg_deductible",
            "csg_non_deductible",
            "csa",
            "fnal",
            "dialogue_social",
            "versement_mobilite",
            "CFP",
            "taxe_apprentissage",
            "taxe_apprentissage_solde",
            "forfait_social",
            "reduction_generale",
            "deduction_hs_patronale",
            "reduction_hs_salariale",
            "exoneration_apprenti_salariale",
        ):
            assert resolve_organisme_from_coti_id(coti_id) == ORGANISME_URSSAF, coti_id

    def test_cotisations_retraite_complementaire(self):
        for coti_id in (
            "retraite_comp_t1",
            "retraite_comp_t2",
            "ceg_t1",
            "ceg_t2",
            "cet",
            "apec",
        ):
            assert resolve_organisme_from_coti_id(coti_id) == ORGANISME_RETRAITE, coti_id

    def test_mutuelle_prevoyance_et_retraite_sup_distinguees(self):
        assert resolve_organisme_from_coti_id("mutuelle") == ORGANISME_MUTUELLE
        assert resolve_organisme_from_coti_id("prevoyance_cadre") == ORGANISME_PREVOYANCE
        assert (
            resolve_organisme_from_coti_id("prevoyance_non_cadre")
            == ORGANISME_PREVOYANCE
        )
        assert resolve_organisme_from_coti_id("retraite_sup") == ORGANISME_RETRAITE_SUP

    def test_libelle_ignore_quand_coti_id_present(self):
        """Le libellé varie par société ; il ne doit jamais primer."""
        assert (
            resolve_organisme_from_coti_id("mutuelle", "GAN Isolé 2026 (EMU3)")
            == ORGANISME_MUTUELLE
        )
        assert (
            resolve_organisme_from_coti_id("mutuelle", "AG2R MUTUELLE")
            == ORGANISME_MUTUELLE
        )

    def test_csg_participation_sans_coti_id_rattachee_a_urssaf(self):
        """Cas observé en production : la CSG sur participation n'a pas de coti_id."""
        assert (
            resolve_organisme_from_coti_id(None, "CSG déductible — Participation 2025")
            == ORGANISME_URSSAF
        )

    def test_coti_id_inconnu_leve_une_cle_explicite(self):
        assert resolve_organisme_from_coti_id("cotisation_martienne") == "INCONNU"

    def test_tous_les_coti_id_de_production_sont_couverts(self):
        """31 identifiants relevés sur les bulletins de juin 2026."""
        attendus = {
            "ags",
            "allocations_familiales",
            "apec",
            "assurance_chomage",
            "at_mp",
            "ceg_t1",
            "ceg_t2",
            "cet",
            "csg_deductible",
            "csg_non_deductible",
            "deduction_hs_patronale",
            "exoneration_apprenti_salariale",
            "forfait_social",
            "mutuelle",
            "prevoyance_cadre",
            "prevoyance_non_cadre",
            "reduction_generale",
            "reduction_hs_salariale",
            "retraite_comp_t1",
            "retraite_comp_t2",
            "retraite_secu_deplafond",
            "retraite_secu_plafond",
            "retraite_sup",
            "securite_sociale_maladie",
            "CFP",
            "csa",
            "dialogue_social",
            "fnal",
            "taxe_apprentissage",
            "taxe_apprentissage_solde",
            "versement_mobilite",
        }
        assert attendus <= set(COTI_TO_ORGANISME)


class TestComptesParDefaut:
    def test_chaque_organisme_a_un_couple_de_comptes(self):
        for organisme in set(COTI_TO_ORGANISME.values()):
            pair = default_accounts_for(organisme)
            assert pair is not None, organisme
            assert pair.compte_charge.startswith("6"), organisme
            assert pair.compte_tiers.startswith("4"), organisme

    def test_organismes_ont_des_comptes_de_tiers_distincts(self):
        """Le défaut d'aujourd'hui écrase tout sur 431000 ; chaque organisme
        doit avoir sa propre dette."""
        tiers = {
            default_accounts_for(o).compte_tiers
            for o in (
                ORGANISME_URSSAF,
                ORGANISME_RETRAITE,
                ORGANISME_MUTUELLE,
                ORGANISME_PREVOYANCE,
                ORGANISME_RETRAITE_SUP,
            )
        }
        assert len(tiers) == 5

    def test_organisme_inconnu_sans_comptes(self):
        assert default_accounts_for("INCONNU") is None
