"""Tests unitaires — résolution temporelle salary_history."""

from datetime import date

import pytest

from app.modules.employees.domain.salary_timeline import (
    calculer_rappel_mois_anterieurs,
    calculer_salaire_mois_prorata,
    changements_dans_mois,
    construire_evolution_salaire_mois,
    est_augmentation_planifiee,
    salaire_actif_a_date,
)

pytestmark = pytest.mark.unit


def _entry(eff: str, ancien: float, nouveau: float) -> dict:
    return {
        "effective_date": eff,
        "ancien_salaire": {"valeur": ancien},
        "nouveau_salaire": {"valeur": nouveau},
    }


class TestSalaireActifADate:
    def test_sans_historique_retourne_initial(self):
        assert salaire_actif_a_date([], date(2026, 6, 15), 2500.0) == 2500.0

    def test_derniere_entree_applicable(self):
        tl = [
            _entry("2026-03-01", 2000, 2200),
            _entry("2026-06-09", 2200, 2500),
        ]
        assert salaire_actif_a_date(tl, date(2026, 6, 8), 2000) == 2200.0
        assert salaire_actif_a_date(tl, date(2026, 6, 9), 2000) == 2500.0

    def test_date_future_non_appliquee(self):
        tl = [_entry("2026-07-01", 2200, 2500)]
        assert salaire_actif_a_date(tl, date(2026, 6, 30), 2200) == 2200.0

    def test_avant_premiere_evolution_retourne_ancien_salaire_historise(self):
        tl = [_entry("2026-06-01", 1823.07, 1867.06)]

        assert salaire_actif_a_date(tl, date(2026, 5, 31), 1867.06) == 1823.07


class TestProrataMois:
    def test_effet_premier_du_mois(self):
        assert calculer_salaire_mois_prorata(
            2000, 2500, date(2026, 6, 1), 2026, 6
        ) == 2500.0

    def test_effet_neuf_juin(self):
        # 8 jours ancien + 22 jours nouveau
        res = calculer_salaire_mois_prorata(
            2000, 2500, date(2026, 6, 9), 2026, 6
        )
        attendu = (2000 * 8 / 30) + (2500 * 22 / 30)
        assert res == pytest.approx(attendu, abs=0.02)


class TestRappel:
    def test_entree_initiale_ne_genere_pas_de_rappel_de_salaire(self):
        tl = [_entry("2026-03-23", 0, 1850.37)]

        r = calculer_rappel_mois_anterieurs(tl, 2026, 6)

        assert r["montant"] == 0.0
        assert r["periode_debut"] is None
        assert r["periode_fin"] is None

    def test_rappel_mars_a_mai_sur_bulletin_juin(self):
        tl = [_entry("2026-03-01", 2000, 2200)]
        r = calculer_rappel_mois_anterieurs(tl, 2026, 6)
        assert r["montant"] == pytest.approx(600.0, abs=0.02)  # 3 × 200
        assert r["periode_debut"] == "2026-03-01"
        assert r["periode_fin"] == "2026-05-31"

    def test_rappel_mi_mars(self):
        tl = [_entry("2026-03-10", 2000, 2200)]
        r = calculer_rappel_mois_anterieurs(tl, 2026, 6)
        # Mars : 21/30 × 200 ; avril + mai : 400
        assert r["montant"] == pytest.approx(200 * 21 / 30 + 400, abs=0.02)

    def test_pas_rappel_si_historique_deja_paye(self):
        entry = _entry("2026-04-01", 1911.04, 1956.94)
        entry["nouveau_salaire"]["rappel_deja_verse"] = True

        r = calculer_rappel_mois_anterieurs([entry], 2026, 6)

        assert r["montant"] == 0.0
        assert r["periode_debut"] is None
        assert r["periode_fin"] is None


class TestEvolutionMois:
    def test_entree_initiale_en_cours_de_mois_n_est_pas_une_revalorisation(self):
        tl = [_entry("2026-03-23", 0, 1850.37)]

        evo = construire_evolution_salaire_mois(tl, 2026, 3, 1867.06)

        assert evo["salaire_debut_mois"] == 1850.37
        assert evo["salaire_fin_mois"] == 1850.37
        assert evo["prorata"] is None

    def test_changement_mi_mois_juin(self):
        tl = [_entry("2026-06-09", 2600, 2678)]
        evo = construire_evolution_salaire_mois(tl, 2026, 6, 2600)
        assert evo["salaire_debut_mois"] == 2600.0
        assert evo["prorata"] is not None
        assert evo["prorata"]["jours_ancien"] == 8
        assert evo["prorata"]["jours_nouveau"] == 22
        assert evo["rappel"]["montant"] == 0.0


class TestPlanifiee:
    def test_date_future(self):
        assert est_augmentation_planifiee(date(2026, 7, 1), date(2026, 6, 9)) is True
        assert est_augmentation_planifiee(date(2026, 6, 9), date(2026, 6, 9)) is False


class TestChangementsDansMois:
    def test_filtre_mois(self):
        tl = [
            _entry("2026-05-31", 2000, 2100),
            _entry("2026-06-09", 2100, 2200),
            _entry("2026-07-01", 2200, 2300),
        ]
        assert len(changements_dans_mois(tl, 2026, 6)) == 1


class TestPlusieursChangementsMemeMois:
    """Le dernier changement chronologique du mois fait foi pour le prorata."""

    def test_deux_augmentations_juin_derniere_prise_en_compte(self):
        tl = [
            _entry("2026-06-10", 2000, 2100),
            _entry("2026-06-20", 2100, 2300),
        ]
        evo = construire_evolution_salaire_mois(tl, 2026, 6, 2000)
        assert evo["salaire_fin_mois"] == 2300.0
        assert evo["prorata"] is not None
        assert evo["prorata"]["ancien"] == 2100.0
        assert evo["prorata"]["nouveau"] == 2300.0
        assert evo["prorata"]["jours_ancien"] == 19
        assert evo["prorata"]["jours_nouveau"] == 11
        attendu = calculer_salaire_mois_prorata(2100, 2300, date(2026, 6, 20), 2026, 6)
        assert evo["prorata"]["montant_mois"] == pytest.approx(attendu, abs=0.02)

    def test_augmentation_future_n_impacte_pas_bulletin_courant(self):
        tl = [_entry("2026-07-01", 2200, 2500)]
        evo = construire_evolution_salaire_mois(tl, 2026, 6, 2200)
        assert evo["prorata"] is None
        assert evo["salaire_debut_mois"] == 2200.0
        assert evo["salaire_fin_mois"] == 2200.0
        assert evo["rappel"]["montant"] == 0.0


class TestRappelSelonBulletinsPayes:
    """Ne rappeler que les mois réellement payés à l'ancien taux.

    Demory (Colorplast) : SMIC revalorisé au 01/06, juin déjà payé au nouveau
    taux, et le bulletin de juillet rappelait 16,69 € — comme l'aurait fait
    chaque bulletin suivant. `bases_des_bulletins` dit sur quel salaire
    mensuel chaque bulletin antérieur a été établi.
    """

    def test_mois_deja_paye_au_nouveau_taux_sans_rappel(self):
        tl = [_entry("2026-06-01", 1850.37, 1867.06)]
        r = calculer_rappel_mois_anterieurs(
            tl, 2026, 7, bases_des_bulletins={(2026, 6): 1867.06}
        )
        assert r["montant"] == 0.0
        assert r["periode_debut"] is None
        assert r["periode_fin"] is None

    def test_mois_payes_a_l_ancien_taux_rappeles(self):
        tl = [_entry("2026-03-01", 2000, 2200)]
        r = calculer_rappel_mois_anterieurs(
            tl, 2026, 6,
            bases_des_bulletins={(2026, 3): 2000, (2026, 4): 2000, (2026, 5): 2200},
        )
        assert r["montant"] == pytest.approx(400.0, abs=0.02)
        assert r["periode_debut"] == "2026-03-01"
        assert r["periode_fin"] == "2026-05-31"

    def test_mois_sans_bulletin_n_est_pas_rappele(self):
        # Payé hors EYWAI (cabinet) : rien ne prouve un rappel dû, il se
        # saisit à la main s'il l'est.
        tl = [_entry("2026-03-01", 2000, 2200)]
        r = calculer_rappel_mois_anterieurs(tl, 2026, 6, bases_des_bulletins={(2026, 5): 2000})
        assert r["montant"] == pytest.approx(200.0, abs=0.02)

    def test_mois_paye_a_un_taux_intermediaire(self):
        tl = [_entry("2026-03-01", 2000, 2200)]
        r = calculer_rappel_mois_anterieurs(
            tl, 2026, 6,
            bases_des_bulletins={(2026, 3): 2100, (2026, 4): 2200, (2026, 5): 2200},
        )
        assert r["montant"] == pytest.approx(100.0, abs=0.02)

    def test_mois_de_prise_d_effet_en_cours_de_mois(self):
        tl = [_entry("2026-03-10", 2000, 2200)]
        # Mars payé à l'ancien taux : 21/30 de la différence ; avril et mai au nouveau.
        r = calculer_rappel_mois_anterieurs(
            tl, 2026, 6,
            bases_des_bulletins={(2026, 3): 2000, (2026, 4): 2200, (2026, 5): 2200},
        )
        assert r["montant"] == pytest.approx(200 * 21 / 30, abs=0.02)
        # Mars déjà payé au prorata exact : rien.
        r2 = calculer_rappel_mois_anterieurs(
            tl, 2026, 6,
            bases_des_bulletins={(2026, 3): 2140, (2026, 4): 2200, (2026, 5): 2200},
        )
        assert r2["montant"] == 0.0

    def test_sans_information_le_comportement_historique_reste(self):
        tl = [_entry("2026-03-01", 2000, 2200)]
        assert calculer_rappel_mois_anterieurs(tl, 2026, 6)["montant"] == pytest.approx(600.0)

    def test_construire_evolution_transmet_les_bases(self):
        tl = [_entry("2026-06-01", 1850.37, 1867.06)]
        evo = construire_evolution_salaire_mois(
            tl, 2026, 7, 1867.06, bases_des_bulletins={(2026, 6): 1867.06}
        )
        assert evo["rappel"]["montant"] == 0.0
        assert evo["salaire_fin_mois"] == 1867.06
