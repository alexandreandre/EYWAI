"""Formules de la provision des congés : la règle légale (retour d'Elsa du 05/11/2026).

Chaque période vaut le plus élevé du maintien et du dixième (C. trav. L3141-24) ; le dixième
reconstitue les absences assimilées (en entier) et la maladie ordinaire (80 %) ; le maintien
compte les primes versées chaque mois. Sources : service-public F33359 et F37482.
"""

import pytest

from app.modules.exports.domain import provision_cp as module

pytestmark = pytest.mark.unit


def _periode(restants, droits=25.0, base=None):
    return module.PeriodeProvision(restants=restants, droits=droits, base=base)


class TestValoriserPeriode:
    def test_le_dixieme_quand_il_est_plus_eleve(self):
        v = module.valoriser_periode(_periode(10.0, 25.0, 36000.0), valeur_jour=120.0)
        assert v.montant == 1440.0  # 10 % de 36 000 × 10/25, contre 1 200 au maintien
        assert v.methode == "dixième"

    def test_le_maintien_quand_il_est_plus_eleve(self):
        v = module.valoriser_periode(_periode(10.0, 25.0, 24000.0), valeur_jour=120.0)
        assert v.montant == 1200.0  # 960 au dixième
        assert v.methode == "maintien"

    def test_sans_remuneration_de_la_periode_le_maintien_seul(self):
        v = module.valoriser_periode(_periode(10.0, 25.0, None), valeur_jour=120.0)
        assert (v.montant, v.methode) == (1200.0, "maintien seul")

    def test_sans_droits_legaux_le_maintien_seul(self):
        v = module.valoriser_periode(_periode(3.0, 0.0, 9000.0), valeur_jour=100.0)
        assert (v.montant, v.methode) == (300.0, "maintien seul")

    def test_des_conges_pris_d_avance_diminuent_la_dette(self):
        v = module.valoriser_periode(_periode(-2.0, 25.0, 30000.0), valeur_jour=100.0)
        assert (v.montant, v.methode) == (-200.0, "pris d'avance")

    def test_aucun_jour_restant(self):
        assert module.valoriser_periode(_periode(0.0), valeur_jour=100.0).montant == 0.0

    @pytest.mark.parametrize(
        "restants,droits,base,valeur",
        [(10.0, 25.0, 36000.0, 120.0), (10.0, 25.0, 24000.0, 120.0), (2.78, 3.78, 4171.35, 98.48),
         (4.0, 0.0, 5000.0, 90.0), (7.5, 20.83, None, 101.1)],
    )
    def test_meme_regle_que_le_bulletin_de_sortie(self, restants, droits, base, valeur):
        from app.modules.payroll.engine.iccp_fin_contrat import PeriodeConges, indemnite_par_periode

        moteur = indemnite_par_periode(
            PeriodeConges(libelle="", brut=base, droits=droits, restants=restants),
            taux=0.10, valeur_jour=valeur,
        )
        assert module.valoriser_periode(_periode(restants, droits, base), valeur_jour=valeur).montant == moteur.retenu


class TestReconstitution:
    def test_la_maladie_ordinaire_compte_a_80_pour_cent(self):
        lignes = [{"libelle": "Salaire de base", "gain": 3551.41},
                  {"libelle": "Absence maladie 240926-280926", "perte": 484.28}]
        assert module.ajustement_dixieme(lignes) == round(484.28 * 0.8, 2)

    def test_un_libelle_de_martine_se_lit_pareil(self):
        assert module.ajustement_dixieme(
            [{"libelle": "Absence arrêt maladie du 01/09 au 30/09", "perte": 1000.0}]
        ) == 800.0

    @pytest.mark.parametrize("libelle", [
        "Absence accident du travail du 02/09", "Absence maladie professionnelle du 02/09",
        "Absence congé maternité du 01/09 au 30/09", "Absence congé paternité du 01/09",
        "Absence congé d'adoption du 01/09",
    ])
    def test_les_absences_assimilees_comptent_en_entier(self, libelle):
        assert module.ajustement_dixieme([{"libelle": libelle, "perte": 500.0}]) == 500.0

    @pytest.mark.parametrize("libelle", [
        "Absence congés payés ", "Absence non rémunérée du 03/09", "Absence pour entrée ou sortie",
        "Absence injustifiée du 03/09 (journee)", "Absence événement familial du 03/09",
    ])
    def test_les_autres_absences_ne_sont_pas_reconstituees(self, libelle):
        assert module.ajustement_dixieme([{"libelle": libelle, "perte": 500.0}]) == 0.0

    def test_la_retenue_des_heures_structurelles_suit_l_absence_du_mois(self):
        lignes = [{"libelle": "Absence maladie 010926-300926", "perte": 1964.73},
                  {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 280.62}]
        assert module.ajustement_dixieme(lignes) == round((1964.73 + 280.62) * 0.8, 2)

    def test_le_complement_employeur_est_remplace_par_la_reconstitution(self):
        lignes = [{"libelle": "Absence maladie 010926-150926", "perte": 1000.0},
                  {"libelle": "Maintien de salaire", "gain": 900.0}]
        assert module.ajustement_dixieme(lignes) == -100.0  # 800 reconstitués, 900 retirés

    def test_le_maintien_d_un_evenement_familial_reste(self):
        lignes = [{"libelle": "Absence événement familial du 03/09", "perte": 100.0},
                  {"libelle": "Maintien de salaire (événement familial)", "gain": 100.0}]
        assert module.ajustement_dixieme(lignes) == 0.0

    def test_un_bulletin_sans_absence(self):
        assert module.ajustement_dixieme([{"libelle": "Salaire de base", "gain": 2000.0}]) == 0.0


class TestPrimesRecurrentes:
    def test_une_prime_presente_chaque_mois_au_montant_moyen(self):
        mois = [[{"libelle": "Prime ancienneté", "gain": 60.0}],
                [{"libelle": "Prime ancienneté", "gain": 60.0}, {"libelle": "Prime exceptionnelle", "gain": 500.0}],
                [{"libelle": "Prime ancienneté", "gain": 63.0}]]
        assert module.primes_recurrentes(mois) == 61.0

    def test_une_prime_absente_un_mois_n_est_pas_recurrente(self):
        mois = [[{"libelle": "Prime injection", "gain": 80.0}], [], [{"libelle": "Prime injection", "gain": 80.0}]]
        assert module.primes_recurrentes(mois) == 0.0

    def test_une_prime_ponctuelle_n_est_pas_recurrente_meme_repetee(self):
        mois = [[{"libelle": "Prime exceptionnelle", "gain": 100.0}]] * 3
        assert module.primes_recurrentes(mois) == 0.0

    def test_seuls_les_trois_derniers_mois_comptent(self):
        mois = [[]] + [[{"libelle": "Prime poste difficile", "gain": 45.0}]] * 3
        assert module.primes_recurrentes(mois) == 45.0

    def test_un_seul_bulletin_ne_dit_pas_ce_qui_revient(self):
        assert module.primes_recurrentes([[{"libelle": "Prime ancienneté", "gain": 60.0}]]) == 0.0


class TestCalculerLigne:
    def test_conges_et_repos_valorises_et_charges(self):
        ligne = module.calculer_ligne(
            matricule="M", nom="A B", date_entree="2020-01-01",
            n1=_periode(20.0, 25.0, 30000.0), n=_periode(8.32, 8.32, 9000.0),
            valeur_jour=120.0, taux_charges=25.0, mois_retenus="9/12", solde_repos=2.0,
        )
        assert ligne.provision_n1 == 2400.0  # dixième 2 400 contre 2 400 au maintien
        assert ligne.provision_n == 998.4  # maintien 998,40 contre 900 au dixième
        assert ligne.provision_repos == 240.0
        assert ligne.provision == 3638.4
        assert ligne.montant_charges == 909.6
        assert ligne.total == 4548.0
        assert ligne.solde_jours == 30.32
        assert ligne.methode == "N-1 : dixième ; N : maintien ; repos : maintien"

    def test_sans_repos_ni_conges_n_1(self):
        ligne = module.calculer_ligne(
            matricule="M", nom="A B", date_entree="2026-05-01",
            n1=_periode(0.0, 0.0), n=_periode(2.08, 2.08, 1900.0),
            valeur_jour=87.69, taux_charges=0.0, mois_retenus="1/12",
        )
        assert ligne.methode == "N : dixième"  # 190 au dixième contre 182,40 au maintien
        assert ligne.provision == 190.0

    def test_une_base_inconnue_reste_vide(self):
        ligne = module.calculer_ligne(
            matricule="M", nom="A B", date_entree="2020-01-01",
            n1=_periode(5.0, 25.0, None), n=_periode(1.0, 2.0, 500.0),
            valeur_jour=100.0, taux_charges=0.0, mois_retenus="0/12",
        )
        assert ligne.base_n1 is None
        assert ligne.base_n == 500.0


class TestCalculerTotaux:
    def test_totaux_et_taux_moyen_pondere(self):
        lignes = [
            module.calculer_ligne(matricule=m, nom=m, date_entree="2020-01-01",
                                  n1=_periode(r, 25.0, None), n=_periode(0.0),
                                  valeur_jour=100.0, taux_charges=t, mois_retenus="1/12")
            for m, r, t in (("A", 10.0, 20.0), ("B", 5.0, 50.0))
        ]
        totaux = module.calculer_totaux(lignes)
        assert totaux["provision"] == 1500.0
        assert totaux["montant_charges"] == 450.0
        assert totaux["taux_charges"] == 30.0
        assert totaux["total"] == 1950.0

    def test_totaux_sur_liste_vide(self):
        assert module.calculer_totaux([])["taux_charges"] == 0.0


class TestBornesDesPeriodes:
    def test_septembre_2026(self):
        (d1, f1), (d, f) = module.bornes_des_periodes(module.date(2026, 9, 30))
        assert (d1, f1, d, f) == (module.date(2025, 6, 1), module.date(2026, 5, 31),
                                  module.date(2026, 6, 1), module.date(2026, 9, 30))

    def test_avant_juin(self):
        (d1, _), (d, _) = module.bornes_des_periodes(module.date(2026, 3, 31))
        assert (d1, d) == (module.date(2024, 6, 1), module.date(2025, 6, 1))

    def test_une_periode_qui_commence_en_janvier(self):
        (_, f1), (d, _) = module.bornes_des_periodes(module.date(2026, 9, 30), mois_debut=1)
        assert (f1, d) == (module.date(2025, 12, 31), module.date(2026, 1, 1))


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
