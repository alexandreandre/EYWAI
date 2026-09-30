"""Heures saisies au réel un jour où le prévu est un arrêt ou une absence non travaillée.

Constat du 30/09/2026 : une salariée en arrêt tout septembre gardait des heures
pointées sur douze jours ; le moteur en faisait 70,75 h sup à 50 %. Le module
pur dit quels jours sont en conflit ; la génération, l'import et l'écran s'en
servent.
"""

from __future__ import annotations

import pytest

from app.modules.schedules.domain.conflits_arret import (
    JourEnConflit,
    jours_en_conflit,
    jours_sans_heures,
    message_de_refus,
)

pytestmark = pytest.mark.unit


def _prevu(jour: int, type_: str, heures: float = 0.0, **extra) -> dict:
    return {"jour": jour, "type": type_, "heures_prevues": heures, **extra}


def _reel(jour: int, heures: float | None, type_: str = "travail", **extra) -> dict:
    return {"jour": jour, "type": type_, "heures_faites": heures, **extra}


class TestJoursEnConflit:
    def test_prevu_arret_et_reel_neuf_heures_est_en_conflit(self):
        conflits = jours_en_conflit(
            [_prevu(7, "arret_maladie")], [_reel(7, 9.0)]
        )

        assert conflits == [
            JourEnConflit(jour=7, type_prevu="arret_maladie", heures_saisies=9.0)
        ]

    def test_prevu_arret_et_reel_a_zero_n_est_pas_en_conflit(self):
        assert jours_en_conflit([_prevu(7, "arret_maladie")], [_reel(7, 0.0)]) == []

    def test_prevu_arret_et_reel_vide_n_est_pas_en_conflit(self):
        assert jours_en_conflit([_prevu(7, "arret_maladie")], [_reel(7, None)]) == []
        assert jours_en_conflit([_prevu(7, "arret_maladie")], []) == []

    def test_prevu_travail_et_reel_neuf_heures_n_est_pas_en_conflit(self):
        assert jours_en_conflit([_prevu(7, "travail", 7.0)], [_reel(7, 9.0)]) == []

    def test_prevu_conges_payes_et_reel_huit_heures_est_en_conflit(self):
        conflits = jours_en_conflit([_prevu(21, "conges_payes")], [_reel(21, 8.0)])

        assert conflits == [
            JourEnConflit(jour=21, type_prevu="conges_payes", heures_saisies=8.0)
        ]

    def test_tous_les_arrets_sont_des_conflits(self):
        """Le moteur reconnaît un arrêt par son préfixe (`calcul_brut`) : accident
        du travail, maternité… repris de la DSN sous leur propre type."""
        prevu = [_prevu(1, "arret_at"), _prevu(2, "arret_maternite")]
        reel = [_reel(1, 7.0), _reel(2, 7.0)]

        assert [c.type_prevu for c in jours_en_conflit(prevu, reel)] == [
            "arret_at",
            "arret_maternite",
        ]

    @pytest.mark.parametrize(
        "type_",
        [
            "conge",
            "rtt",
            "evenement_familial",
            "absence_non_remuneree",
            "absence_injustifiee",
            "sans_solde",
        ],
    )
    def test_les_absences_non_travaillees_sont_des_conflits(self, type_):
        assert [c.type_prevu for c in jours_en_conflit([_prevu(3, type_)], [_reel(3, 4.0)])] == [
            type_
        ]

    @pytest.mark.parametrize("type_", ["weekend", "repos", "ferie", "travail", "work"])
    def test_un_jour_de_repos_ou_de_travail_n_est_jamais_un_conflit(self, type_):
        """Travailler un samedi ou un férié se paie, en heures sup s'il le faut."""
        assert jours_en_conflit([_prevu(5, type_)], [_reel(5, 6.0)]) == []

    def test_un_week_end_sans_heures_est_ignore(self):
        prevu = [_prevu(5, "weekend"), _prevu(6, "weekend"), _prevu(7, "arret_maladie")]
        reel = [_reel(5, 0.0), _reel(6, None), _reel(7, 0.0)]

        assert jours_en_conflit(prevu, reel) == []

    def test_une_demi_journee_de_conge_avec_des_heures_n_est_pas_un_conflit(self):
        """Le salarié a travaillé l'autre demi-journée : l'analyseur garde les deux."""
        prevu = [_prevu(14, "conges_payes", quotite_absence=0.5, demi_journee="matin")]

        assert jours_en_conflit(prevu, [_reel(14, 4.0)]) == []

    def test_plusieurs_mois_de_la_fenetre(self):
        """Le même numéro de jour dans deux mois ne se confond pas."""
        prevu = [
            _prevu(31, "arret_maladie", annee=2026, mois=8),
            _prevu(1, "travail", 7.0, annee=2026, mois=8),
            _prevu(1, "arret_maladie", annee=2026, mois=9),
            _prevu(2, "arret_maladie", annee=2026, mois=9),
        ]
        reel = [
            _reel(2, 7.5, annee=2026, mois=9),
            _reel(1, 7.0, annee=2026, mois=8),
            _reel(31, 8.0, annee=2026, mois=8),
            _reel(1, 6.0, annee=2026, mois=9),
        ]

        assert jours_en_conflit(prevu, reel) == [
            JourEnConflit(31, "arret_maladie", 8.0, annee=2026, mois=8),
            JourEnConflit(1, "arret_maladie", 6.0, annee=2026, mois=9),
            JourEnConflit(2, "arret_maladie", 7.5, annee=2026, mois=9),
        ]

    def test_le_detail_d_un_jour_est_au_format_de_l_api(self):
        jour = JourEnConflit(7, "arret_maladie", 9.0, annee=2026, mois=9)

        assert jour.en_detail() == {"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}

    def test_un_samedi_d_arret_valide_avec_des_heures_est_en_conflit(self):
        """La validation d'un arrêt ne retype pas ses week-ends (planning « weekend »,
        métadonnées d'arrêt seulement) : les absences validées les rattachent à l'arrêt."""
        prevu = [
            _prevu(12, "weekend", annee=2026, mois=9),
            _prevu(13, "weekend", annee=2026, mois=9),
        ]
        reel = [_reel(12, 5.0, annee=2026, mois=9), _reel(13, 3.0, annee=2026, mois=9)]
        absences = [
            {"type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-12"]},
            {"type": "conge_paye", "status": "validated", "selected_days": ["2026-09-13"]},
        ]

        assert jours_en_conflit(prevu, reel) == []
        assert jours_en_conflit(prevu, reel, absences) == [
            JourEnConflit(12, "arret_maladie", 5.0, annee=2026, mois=9)
        ]

    def test_un_ferie_et_un_repos_couverts_par_un_arret_valide_sont_des_conflits(self):
        prevu = [
            _prevu(14, "ferie", annee=2026, mois=7),
            _prevu(15, "repos", annee=2026, mois=7),
        ]
        reel = [_reel(14, 7.0, annee=2026, mois=7), _reel(15, 6.0, annee=2026, mois=7)]
        absences = [
            {"type": "arret_at", "status": "validated", "selected_days": ["2026-07-14", "2026-07-15"]}
        ]

        assert jours_en_conflit(prevu, reel, absences) == [
            JourEnConflit(14, "arret_at", 7.0, annee=2026, mois=7),
            JourEnConflit(15, "arret_at", 6.0, annee=2026, mois=7),
        ]

    def test_un_jour_travaille_couvert_par_un_arret_valide_garde_la_regle_du_type_prevu(self):
        """L'arrêt validé ne rattache que les jours que sa validation ne retype pas
        (week-end, repos, férié) ; un jour prévu travaillé reste jugé sur son type."""
        prevu = [_prevu(14, "travail", 7.0, annee=2026, mois=9)]
        reel = [_reel(14, 7.0, annee=2026, mois=9)]
        absences = [
            {"type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-14"]}
        ]

        assert jours_en_conflit(prevu, reel, absences) == []

    def test_jours_sans_heures_liste_les_jours_qui_ne_peuvent_porter_aucune_heure(self):
        """La même règle, sans le réel : l'effacement accepte exactement ces jours."""
        prevu = [
            _prevu(11, "arret_maladie", annee=2026, mois=9),
            _prevu(12, "weekend", annee=2026, mois=9),
            _prevu(13, "weekend", annee=2026, mois=9),
            _prevu(14, "travail", 7.0, annee=2026, mois=9),
            _prevu(15, "conges_payes", annee=2026, mois=9, quotite_absence=0.5),
        ]
        absences = [
            {"type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-12"]}
        ]

        assert jours_sans_heures(prevu, absences) == {
            (2026, 9, 11): "arret_maladie",
            (2026, 9, 12): "arret_maladie",
        }

    def test_un_jour_en_double_au_prevu_est_juge_sur_sa_derniere_entree(self):
        """Même règle que la fusion du planning et l'effacement : la dernière
        entrée du jour fait foi."""
        reel = [_reel(7, 9.0)]

        assert jours_en_conflit([_prevu(7, "arret_maladie"), _prevu(7, "travail", 7.0)], reel) == []
        assert [c.jour for c in jours_en_conflit([_prevu(7, "travail", 7.0), _prevu(7, "arret_maladie")], reel)] == [7]

    def test_une_absence_non_validee_ne_compte_pas(self):
        prevu = [_prevu(12, "weekend", annee=2026, mois=9)]
        reel = [_reel(12, 5.0, annee=2026, mois=9)]
        absences = [
            {"type": "arret_maladie", "status": "pending", "selected_days": ["2026-09-12"]}
        ]

        assert jours_en_conflit(prevu, reel, absences) == []


class TestMessageDeRefus:
    def test_arret_sur_un_mois(self):
        conflits = [
            JourEnConflit(j, "arret_maladie", 7.0, annee=2026, mois=9) for j in (7, 8, 9)
        ]

        assert message_de_refus("Octavie", conflits) == (
            "Octavie est en arrêt, mais des heures sont saisies les 7, 8 et 9 septembre."
        )

    def test_un_seul_jour(self):
        conflits = [JourEnConflit(1, "arret_maladie", 7.0, annee=2026, mois=9)]

        assert message_de_refus("Octavie", conflits) == (
            "Octavie est en arrêt, mais des heures sont saisies le 1er septembre."
        )

    def test_chaque_mois_est_nomme(self):
        conflits = [
            JourEnConflit(31, "arret_maladie", 8.0, annee=2026, mois=8),
            JourEnConflit(1, "arret_maladie", 6.0, annee=2026, mois=9),
            JourEnConflit(2, "arret_maladie", 7.5, annee=2026, mois=9),
        ]

        assert message_de_refus("Octavie", conflits) == (
            "Octavie est en arrêt, mais des heures sont saisies le 31 août "
            "et les 1er et 2 septembre."
        )

    def test_une_absence_qui_n_est_pas_un_arret_est_nommee_sans_genrer(self):
        conflits = [JourEnConflit(21, "conges_payes", 8.0, annee=2026, mois=9)]

        assert message_de_refus("Octavie", conflits) == (
            "Octavie a une absence (congés payés), mais des heures sont saisies "
            "le 21 septembre."
        )

    def test_arret_et_absence_font_deux_phrases(self):
        conflits = [
            JourEnConflit(7, "arret_maladie", 7.0, annee=2026, mois=9),
            JourEnConflit(21, "conges_payes", 8.0, annee=2026, mois=9),
            JourEnConflit(22, "rtt", 8.0, annee=2026, mois=9),
        ]

        assert message_de_refus("Octavie", conflits) == (
            "Octavie est en arrêt, mais des heures sont saisies le 7 septembre. "
            "Octavie a une absence (congés payés, RTT), mais des heures sont saisies "
            "les 21 et 22 septembre."
        )
