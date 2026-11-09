"""Tests unitaires — temps retenu mensuel (prorata prime d'ancienneté)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.temps_travail_mois import compute_temps_retenu_mois


def _cal_travail(heures: float, *, jour: int = 1) -> dict:
    return {
        "date_complete": f"2026-04-{jour:02d}",
        "type": "travail",
        "heures": heures,
    }


def _cal_arret(jour: int) -> dict:
    return {
        "date_complete": f"2026-04-{jour:02d}",
        "type": "arret_maladie",
        "heures": 0,
    }


class TestTempsTravailMois:
    def test_mode_none_ratio_un(self):
        result = compute_temps_retenu_mois(
            mode="none",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.ratio == 1.0

    def test_heures_contrat_plein_mois(self):
        heures_jour = 151.67 / 22
        cal = [_cal_travail(heures_jour, jour=d) for d in range(1, 23)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.reference == 151.67
        assert result.temps_retenu == pytest.approx(151.67, abs=0.02)
        assert result.ratio == pytest.approx(1.0, abs=0.01)

    def test_heures_contrat_avec_hs(self):
        """153,77 h sur 151,67 h de référence (cas CAVANDE Excel)."""
        heures_jour = 153.77 / 22
        cal = [_cal_travail(heures_jour, jour=d) for d in range(1, 23)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.temps_retenu == 153.77
        assert result.ratio == round(153.77 / 151.67, 6)

    def test_heures_contrat_zero_sans_maintien(self):
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.ratio == 0.0

    def test_maintien_compte_heures_journalieres(self):
        cal = [_cal_travail(7.0, jour=1), _cal_arret(2), _cal_arret(3)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien={2, 3},
            maladie_si_maintien=True,
        )
        assert result.temps_retenu == 7.0 + 14.0
        assert result.detail["heures_maintien"] == 14.0

    def test_maintien_non_compte_sans_jours_maintien(self):
        cal = [_cal_arret(2), _cal_arret(3)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien=set(),
        )
        assert result.ratio == 0.0

    def test_sans_pointage_policy_plein_mois(self):
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=[],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            sans_pointage_policy="plein_mois",
            actual_hours_raw=[{"jour": 1, "type": "sans_pointage"}],
        )
        assert result.ratio == 1.0
        assert result.detail.get("sans_pointage") is True

    def test_jours_forfait(self):
        cal = [
            {"date_complete": f"2026-04-{d:02d}", "type": "travail"}
            for d in range(1, 19)
        ]
        result = compute_temps_retenu_mois(
            mode="jours_forfait",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
        )
        assert result.temps_retenu == 18.0
        assert 0 < result.ratio <= 1.0

    def test_jours_forfait_compte_les_jours_du_moteur_forfait(self):
        """Le moteur forfait (analyser_jours_forfait) type ses jours travaillés « travail_base »
        (1 jour = 1). Seul « travail » était compté : ratio nul, prime d'ancienneté à 0 pour tous
        les forfaits jours non cadres (Cartol, LEWIS, octobre 2026 à blanc)."""
        cal = [
            {"date_complete": f"2026-10-{d:02d}", "type": "travail_base", "heures": 1.0}
            for d in range(1, 18)
        ]
        result = compute_temps_retenu_mois(
            mode="jours_forfait",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 10, 1),
            date_fin=date(2026, 10, 31),
        )
        assert result.temps_retenu == 17.0
        assert result.ratio == 1.0

    def test_jours_forfait_un_jour_d_absence_non_maintenu_reste_hors_du_temps(self):
        cal = [
            {"date_complete": f"2026-10-{d:02d}", "type": "travail_base", "heures": 1.0}
            for d in range(1, 17)
        ] + [{"date_complete": "2026-10-17", "type": "absence_non_remuneree", "heures": 1.0}]
        result = compute_temps_retenu_mois(
            mode="jours_forfait",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 10, 1),
            date_fin=date(2026, 10, 31),
        )
        assert result.temps_retenu == 16.0
        assert result.ratio == round(16 / 17, 6)


class TestMoisSansPointageAvecArretPartiel:
    """Art. 142 CCN métallurgie : la prime « varie avec l'horaire de travail » ; règle de Martine :
    elle se maintient en cas de maladie maintenue. Sans pointage, les jours hors arrêt restent
    présumés travaillés : seul un arrêt non maintenu fait baisser la prime."""

    def _calcul(self, cal: list[dict], *, jours_maintien: set[int], annee: int = 2026, mois: int = 4):
        fin = date(annee, mois + 1, 1).toordinal() - 1
        return compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(annee, mois, 1),
            date_fin=date.fromordinal(fin),
            jours_maintien=jours_maintien,
            sans_pointage_policy="plein_mois",
            actual_hours_raw=[],
        )

    def test_arret_partiel_entierement_maintenu_prime_pleine(self):
        # avril 2026 : arrêt des mercredi 1er au vendredi 3, maintenus ; le reste présumé travaillé
        result = self._calcul([_cal_arret(1), _cal_arret(2), _cal_arret(3)], jours_maintien={1, 2, 3})
        assert result.ratio == 1.0
        assert result.temps_retenu == 151.67
        assert result.detail["heures_arret_non_maintenues"] == 0.0

    def test_jour_d_arret_non_maintenu_retire_ses_heures(self):
        # carence du jeudi 16/04 : 7 h non maintenues sur 151,67 h
        cal = [_cal_arret(16), _cal_arret(17)]
        result = self._calcul(cal, jours_maintien={17})
        assert result.temps_retenu == 144.67
        assert result.ratio == round(144.67 / 151.67, 6)
        assert result.detail["heures_arret_non_maintenues"] == 7.0

    def test_arret_sur_tout_le_mois_ne_bouge_pas(self):
        # février 2026 : du lundi 2 au vendredi 27, tout est en arrêt maintenu
        ouvres = [d for d in range(2, 28) if date(2026, 2, d).weekday() < 5]
        cal = [
            {"date_complete": f"2026-02-{d:02d}", "type": "arret_maladie", "heures": 0}
            for d in ouvres
        ]
        result = self._calcul(cal, jours_maintien=set(ouvres), mois=2)
        assert result.temps_retenu == 140.0
        assert result.ratio == round(140 / 151.67, 6)

    def test_arret_sur_tout_le_mois_maintien_epuise_reste_a_zero(self):
        ouvres = [d for d in range(2, 28) if date(2026, 2, d).weekday() < 5]
        cal = [
            {"date_complete": f"2026-02-{d:02d}", "type": "arret_maladie", "heures": 0}
            for d in ouvres
        ]
        assert self._calcul(cal, jours_maintien=set(), mois=2).ratio == 0.0

    def test_mois_sans_arret_ni_pointage_reste_plein(self):
        assert self._calcul([], jours_maintien=set()).ratio == 1.0

    def test_mois_pointe_avec_arret_compte_toujours_les_heures_pointees(self):
        cal = [_cal_travail(7.0, jour=1), _cal_arret(2), _cal_arret(3)]
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=cal,
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien={2, 3},
            actual_hours_raw=[{"jour": 1, "mois": 4, "annee": 2026, "heures_faites": 7.0}],
        )
        assert result.temps_retenu == 21.0

    def test_politique_mois_a_zero_garde_la_lecture_stricte(self):
        result = compute_temps_retenu_mois(
            mode="heures_contrat",
            calendrier_saisie=[_cal_arret(1), _cal_arret(2)],
            duree_hebdo=35.0,
            date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30),
            jours_maintien={1, 2},
            sans_pointage_policy="zero",
            actual_hours_raw=[],
        )
        assert result.temps_retenu == 14.0
