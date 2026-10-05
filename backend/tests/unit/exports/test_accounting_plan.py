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


class TestFamillesElementsHorsBrut:
    """Les éléments hors brut n'ont pas d'identifiant stable : prime_id est
    fabriqué depuis le libellé libre saisi par la RH. Le rattachement passe donc
    par une famille."""

    def test_variantes_daccent_et_de_casse_donnent_la_meme_famille(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_TRANSPORT,
            resolve_element_family,
        )

        assert resolve_element_family("Indemnité de transport") == FAMILLE_TRANSPORT
        assert resolve_element_family("Indemnite de transport") == FAMILLE_TRANSPORT
        assert (
            resolve_element_family("", "indemnité_de_transport") == FAMILLE_TRANSPORT
        )
        assert (
            resolve_element_family("", "indemnite_de_transport") == FAMILLE_TRANSPORT
        )

    def test_prets_rattaches_quel_que_soit_le_nom_du_salarie(self):
        """Un identifiant par salarié ne doit jamais devenir une ligne de
        paramétrage — et surtout pas y faire entrer des noms de personnes."""
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_PRET,
            resolve_element_family,
        )

        for libelle in (
            "Contrat de pret DUPONT Jean",
            "Contrat de prêt MARTIN Claude",
            "Contrat de pret DURAND",
            "Remboursement prêt salarié",
        ):
            assert resolve_element_family(libelle) == FAMILLE_PRET, libelle

    def test_variantes_davance_de_participation(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_AVANCE_PARTICIPATION,
            resolve_element_family,
        )

        for libelle in (
            "Avance participation 2025 (déjà versée)",
            "Acompte sur participation 2025 (déjà versé)",
            "Acompte participation 2025 (déjà versé)",
        ):
            assert (
                resolve_element_family(libelle) == FAMILLE_AVANCE_PARTICIPATION
            ), libelle

    def test_paniers_et_cantine(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_CANTINE,
            FAMILLE_PANIER,
            resolve_element_family,
        )

        assert resolve_element_family("Paniers jours non soumis") == FAMILLE_PANIER
        assert resolve_element_family("Indemnité de panier") == FAMILLE_PANIER
        assert resolve_element_family("Paniers repas chauffeur") == FAMILLE_PANIER
        assert resolve_element_family("Cantine") == FAMILLE_CANTINE
        assert resolve_element_family("Remise Cantine (avantage)") == FAMILLE_CANTINE

    def test_libelle_inconnu_signale_et_non_devine(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_INCONNUE,
            resolve_element_family,
        )

        assert resolve_element_family("Prime exceptionnelle de mars") == FAMILLE_INCONNUE
        assert resolve_element_family("") == FAMILLE_INCONNUE

    def test_famille_sans_compte_par_defaut_doit_etre_parametree(self):
        """Panier et cantine n'apparaissent pas sur l'OD de référence : leur
        compte dépend du plan du cabinet, on ne l'invente pas."""
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_CANTINE,
            FAMILLE_PANIER,
            FAMILLE_TRANSPORT,
            default_accounts_for_family,
        )

        assert default_accounts_for_family(FAMILLE_TRANSPORT) is not None
        assert default_accounts_for_family(FAMILLE_PANIER) is None
        assert default_accounts_for_family(FAMILLE_CANTINE) is None


class TestCotisationsDesBulletinsRepris:
    """Les bulletins repris de l'ancien logiciel portent leurs propres coti_id.

    Sans rattachement, chaque ligne sort en anomalie et l'OD ne s'équilibre
    pas (Comitech, juin et août 2026 : plus de 3 500 € non postés par mois).
    """

    def test_coti_id_de_la_reprise_rattaches(self):
        assert resolve_organisme_from_coti_id("vieillesse_plafonnee") == ORGANISME_URSSAF
        assert resolve_organisme_from_coti_id("vieillesse_deplafonnee") == ORGANISME_URSSAF
        assert resolve_organisme_from_coti_id("autres_contributions") == ORGANISME_URSSAF
        assert resolve_organisme_from_coti_id("prevoyance") == ORGANISME_PREVOYANCE
        assert (
            resolve_organisme_from_coti_id("retraite_supplementaire")
            == ORGANISME_RETRAITE_SUP
        )

    def test_contribution_cpf_cdd_recouvree_par_l_urssaf(self):
        assert resolve_organisme_from_coti_id("cpf_cdd") == ORGANISME_URSSAF

    def test_csg_sur_ijss_sans_coti_id_va_au_compte_des_ijss(self):
        """En subrogation, la caisse verse les IJSS nettes de CSG/CRDS : cette
        CSG ne se paie pas à l'URSSAF, elle réduit la somme à recevoir."""
        from app.modules.exports.domain.accounting_plan import ORGANISME_IJSS

        assert resolve_organisme_from_coti_id(None, "CSG déductible IJSS") == ORGANISME_IJSS
        assert (
            resolve_organisme_from_coti_id(None, "CSG/CRDS IJSS non déductible")
            == ORGANISME_IJSS
        )


class TestFamillesDesBulletinsRecents:
    def test_ppv_reconnue(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_PPV,
            resolve_element_family,
        )

        assert resolve_element_family("Prime de partage de la valeur (PPV)") == FAMILLE_PPV
        assert resolve_element_family("", "prime_partage_valeur") == FAMILLE_PPV
        # Libellé de l'ancien logiciel (bulletins repris, juillet 2026).
        assert resolve_element_family("PRIME PARTAGE DE LA VALEUR") == FAMILLE_PPV

    def test_prime_de_transport_est_du_transport(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_TRANSPORT,
            resolve_element_family,
        )

        assert (
            resolve_element_family("Prime de transport (carburant / frais de trajet)")
            == FAMILLE_TRANSPORT
        )

    def test_notes_de_frais_remboursees_sur_le_bulletin(self):
        """Une note de frais validée entre au bulletin sous « remb_<type>_<date> » ;
        l'ancien logiciel l'appelait « Rbst note de frais »."""
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_NOTE_DE_FRAIS,
            resolve_element_family,
        )

        assert (
            resolve_element_family(
                "remb indemnités kilométriques 2026-09-30",
                "remb_indemnités_kilométriques_2026-09-30",
            )
            == FAMILLE_NOTE_DE_FRAIS
        )
        assert resolve_element_family("Rbst note de frais") == FAMILLE_NOTE_DE_FRAIS

    def test_saisie_quel_que_soit_le_creancier(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_SAISIE,
            resolve_element_family,
        )

        assert resolve_element_family("Saisie Trésor public") == FAMILLE_SAISIE
        assert resolve_element_family("Saisie sur salaire") == FAMILLE_SAISIE

    def test_regularisations_du_net(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_REGULARISATION_NET,
            resolve_element_family,
        )

        assert resolve_element_family("Report NAP négatif") == FAMILLE_REGULARISATION_NET
        assert (
            resolve_element_family("Report NAP négatif 08/2026")
            == FAMILLE_REGULARISATION_NET
        )
        assert resolve_element_family("Trop-perçu mars 2026") == FAMILLE_REGULARISATION_NET

    def test_indemnites_de_rupture(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_INDEMNITE_RUPTURE,
            resolve_element_family,
        )

        assert (
            resolve_element_family("Indemnité légale de licenciement")
            == FAMILLE_INDEMNITE_RUPTURE
        )
        assert (
            resolve_element_family("Indemnité de rupture conventionnelle")
            == FAMILLE_INDEMNITE_RUPTURE
        )

    def test_comptes_par_defaut_des_nouvelles_familles(self):
        from app.modules.exports.domain.accounting_plan import (
            FAMILLE_IJSS,
            FAMILLE_INDEMNITE_RUPTURE,
            FAMILLE_INTERETS_PRET,
            FAMILLE_PPV,
            default_accounts_for_family,
        )

        assert default_accounts_for_family(FAMILLE_PPV).compte_charge == "641300"
        assert default_accounts_for_family(FAMILLE_INDEMNITE_RUPTURE).compte_charge == "641400"
        # Intérêts d'un prêt au personnel : produit financier, pas une dette.
        assert default_accounts_for_family(FAMILLE_INTERETS_PRET).compte_charge == "762400"
        # IJSS subrogées : somme à recevoir de la caisse.
        assert default_accounts_for_family(FAMILLE_IJSS).compte_tiers == "438700"
