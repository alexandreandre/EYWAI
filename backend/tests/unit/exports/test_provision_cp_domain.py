"""Tests des formules de provision CP — valeurs réelles de l'état Cegid CARTOL du 21/07/2026."""

import pytest

from app.modules.exports.domain import provision_cp as module

pytestmark = pytest.mark.unit


class TestCalculerLigne:
    def test_bertaud_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="BERTAUD",
            nom="SYLVAIN BERTAUD",
            date_entree="2010-03-01",
            solde_n1=28.00,
            solde_n=4.16,
            salaire_reference=2640.86,
            taux_charges=25.74,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 32.16
        assert ligne.provision == 3860.46
        assert ligne.montant_charges == 993.68
        assert ligne.total == 4854.14

    def test_blin_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="BLIN",
            nom="Fabien BLIN",
            date_entree="2022-09-05",
            solde_n1=3.00,
            solde_n=4.16,
            salaire_reference=2978.39,
            taux_charges=36.33,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 7.16
        assert ligne.provision == 969.33
        assert ligne.montant_charges == 352.16
        assert ligne.total == 1321.49

    def test_faucher_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="FAUCHER",
            nom="DAMIEN FAUCHER",
            date_entree="2015-01-05",
            solde_n1=27.00,
            solde_n=4.16,
            salaire_reference=12797.15,
            taux_charges=48.92,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 31.16
        assert ligne.provision == 18125.42
        assert ligne.montant_charges == 8866.96
        assert ligne.total == 26992.38

    def test_diviseur_non_standard(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2020-01-01",
            solde_n1=20.0,
            solde_n=0.0,
            salaire_reference=2200.0,
            taux_charges=0.0,
            mois_retenus="12/12",
            diviseur=21.67,
        )
        assert ligne.provision == round(20.0 * 2200.0 / 21.67, 2)

    def test_solde_negatif_donne_une_provision_negative(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2026-01-01",
            solde_n1=0.0,
            solde_n=-2.08,
            salaire_reference=2200.0,
            taux_charges=30.0,
            mois_retenus="6/12",
        )
        assert ligne.solde_jours == -2.08
        assert ligne.provision < 0
        assert ligne.total < 0

    def test_anomalie_conservee_telle_quelle(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2026-05-01",
            solde_n1=0.0,
            solde_n=2.08,
            salaire_reference=1800.0,
            taux_charges=30.0,
            mois_retenus="0/12",
            anomalie="aucun bulletin",
        )
        assert ligne.anomalie == "aucun bulletin"


class TestCalculerTotaux:
    def test_totaux_et_taux_moyen_pondere(self):
        lignes = [
            module.calculer_ligne("A", "A", "2020-01-01", 10.0, 2.0, 2000.0, 20.0, "12/12"),
            module.calculer_ligne("B", "B", "2020-01-01", 20.0, 2.0, 3000.0, 40.0, "12/12"),
        ]
        totaux = module.calculer_totaux(lignes)

        assert totaux["solde_n1"] == 30.0
        assert totaux["solde_n"] == 4.0
        assert totaux["solde_jours"] == 34.0
        assert totaux["provision"] == round(sum(l.provision for l in lignes), 2)
        assert totaux["montant_charges"] == round(sum(l.montant_charges for l in lignes), 2)
        assert totaux["total"] == round(totaux["provision"] + totaux["montant_charges"], 2)
        # taux moyen = charges totales / provision totale, jamais la moyenne des taux
        assert totaux["taux_charges"] == round(
            totaux["montant_charges"] / totaux["provision"] * 100, 2
        )

    def test_totaux_sur_liste_vide(self):
        totaux = module.calculer_totaux([])
        assert totaux["provision"] == 0.0
        assert totaux["taux_charges"] == 0.0


class TestMoisDeReference:
    def test_douze_mois_a_cheval_sur_deux_annees(self):
        mois = module.mois_de_reference(2026, 7)
        assert len(mois) == 12
        assert mois[0] == (2025, 8)
        assert mois[-1] == (2026, 7)

    def test_fenetre_reduite(self):
        assert module.mois_de_reference(2026, 3, fenetre=4) == [
            (2025, 12),
            (2026, 1),
            (2026, 2),
            (2026, 3),
        ]


class TestResoudreReference:
    def test_moyenne_sur_les_mois_presents(self):
        bulletins = {(2026, m): (2000.0 + m, 600.0) for m in range(1, 7)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        attendu = sum(2000.0 + m for m in range(1, 7)) / 6
        assert ref.salaire_reference == round(attendu, 2)
        assert ref.taux_charges == round(600.0 * 6 / (attendu * 6) * 100, 2)
        assert ref.mois_retenus == "6/12"
        assert ref.anomalie == ""

    def test_mois_a_brut_nul_ignore(self):
        bulletins = {(2026, 1): (2000.0, 600.0), (2026, 2): (0.0, 0.0)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 2),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        assert ref.salaire_reference == 2000.0
        assert ref.mois_retenus == "1/12"

    def test_aucun_bulletin_repli_sur_le_contractuel(self):
        ref = module.resoudre_reference(
            bulletins={},
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        assert ref.salaire_reference == 1900.0
        assert ref.taux_charges == 35.0
        assert ref.mois_retenus == "0/12"
        assert ref.anomalie == "aucun bulletin : salaire contractuel et taux société utilisés"

    def test_aucun_bulletin_et_aucun_contractuel(self):
        ref = module.resoudre_reference(
            bulletins={},
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=None,
            taux_societe=None,
        )
        assert ref.salaire_reference == 0.0
        assert ref.taux_charges == 0.0
        assert ref.anomalie == "aucun bulletin et aucun salaire contractuel"

    def test_bulletin_hors_fenetre_ignore(self):
        bulletins = {(2024, 3): (9999.0, 9999.0), (2026, 6): (2000.0, 600.0)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=None,
            taux_societe=None,
        )
        assert ref.salaire_reference == 2000.0
        assert ref.mois_retenus == "1/12"
