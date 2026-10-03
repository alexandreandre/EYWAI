"""Refaire un import : les jours corrigés à la main depuis le premier import.

Pour chaque salarié et chaque jour que relit le fichier, on compare ce
qu'avait écrit le lot précédent à ce qui est au calendrier aujourd'hui. Une
différence est une correction faite après l'import : la relecture la montre et,
par défaut, la garde. Module pur : l'appelant fournit les trois relevés.
"""

from __future__ import annotations

import pytest

from app.modules.schedules.domain.corrections_a_la_main import (
    ValeurJour,
    corrections_a_la_main,
    jours_du_calendrier_reel,
)

pytestmark = pytest.mark.unit

E1 = "emp-1"
E2 = "emp-2"


def cle(jour: int, employee_id: str = E1, annee: int = 2026, mois: int = 9):
    return (employee_id, annee, mois, jour)


def v(heures, type_="travail") -> ValeurJour:
    return ValeurJour(heures=heures, type=type_)


class TestCorrectionsALaMain:
    def test_un_jour_corrige_apres_l_import_est_signale(self):
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15): v(8.5)},
            ecrits_par_import={cle(15): v(8.5)},
            en_base={cle(15): v(9.0)},
        )

        assert len(corrections) == 1
        c = corrections[0]
        assert (c.employee_id, c.annee, c.mois, c.jour) == (E1, 2026, 9, 15)
        assert c.import_precedent == v(8.5)
        assert c.calendrier == v(9.0)
        assert c.fichier == v(8.5)

    def test_un_jour_que_personne_n_a_touche_n_est_pas_une_correction(self):
        assert (
            corrections_a_la_main(
                jours_du_fichier={cle(15): v(7.0)},
                ecrits_par_import={cle(15): v(8.5)},
                en_base={cle(15): v(8.5)},
            )
            == []
        )

    def test_une_correction_que_le_fichier_relit_a_l_identique_ne_demande_rien(self):
        # Le lecteur corrigé lit 9 h, comme la gestionnaire l'avait saisi.
        assert (
            corrections_a_la_main(
                jours_du_fichier={cle(15): v(9.0)},
                ecrits_par_import={cle(15): v(8.5)},
                en_base={cle(15): v(9.0)},
            )
            == []
        )

    def test_un_jour_efface_a_la_main_est_une_correction(self):
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15): v(8.5)},
            ecrits_par_import={cle(15): v(8.5)},
            en_base={},
        )

        assert len(corrections) == 1
        assert corrections[0].calendrier is None

    def test_un_jour_passe_en_arret_a_la_main_est_une_correction(self):
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15): v(8.5)},
            ecrits_par_import={cle(15): v(8.5)},
            en_base={cle(15): v(None, "arret_maladie")},
        )

        assert [c.calendrier for c in corrections] == [v(None, "arret_maladie")]

    def test_un_type_change_sans_heures_reste_une_correction(self):
        # Congé importé, arrêt saisi ensuite : relire le congé effacerait l'arrêt.
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15): v(None, "conge")},
            ecrits_par_import={cle(15): v(None, "conge")},
            en_base={cle(15): v(None, "arret_maladie")},
        )

        assert len(corrections) == 1

    @pytest.mark.parametrize(
        ("ecrit", "en_base"),
        [
            (v(None, "weekend"), v(None, "repos")),
            (v(None, "conge"), v(None, "conges_payes")),
            (v(None, "travail"), v(None, "repos")),
            (v(None, "weekend"), None),
            (v(8.5), v(8.50000001)),
            (v(8.5, None), v(8.5, "travail")),
        ],
    )
    def test_une_meme_valeur_ecrite_autrement_n_est_pas_une_correction(self, ecrit, en_base):
        # Mesuré sur la base de test : l'écran réécrit « weekend » en « repos »
        # et « conge » en « conges_payes » sans que personne ne corrige rien.
        assert (
            corrections_a_la_main(
                jours_du_fichier={cle(15): v(7.0)},
                ecrits_par_import={cle(15): ecrit},
                en_base={} if en_base is None else {cle(15): en_base},
            )
            == []
        )

    def test_un_jour_que_l_import_n_avait_pas_ecrit_mais_saisi_depuis_est_garde(self):
        # Salarié sauté par l'ancien lecteur, rattrapé à la main : 7 h au calendrier.
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15, E2): v(8.0)},
            ecrits_par_import={cle(15): v(8.5)},
            en_base={cle(15, E2): v(7.0)},
        )

        assert len(corrections) == 1
        c = corrections[0]
        assert c.employee_id == E2
        assert c.import_precedent is None
        assert c.calendrier == v(7.0)

    def test_un_jour_vide_que_l_import_n_avait_pas_ecrit_s_ecrit_sans_question(self):
        assert (
            corrections_a_la_main(
                jours_du_fichier={cle(15, E2): v(8.0), cle(16, E2): v(8.0)},
                ecrits_par_import={},
                en_base={cle(16, E2): v(None, "repos")},
            )
            == []
        )

    def test_les_corrections_sont_rangees_par_salarie_puis_par_date(self):
        corrections = corrections_a_la_main(
            jours_du_fichier={
                cle(16, E2): v(8.0),
                cle(30, E1, mois=8): v(8.0),
                cle(2, E1): v(8.0),
            },
            ecrits_par_import={
                cle(16, E2): v(8.0),
                cle(30, E1, mois=8): v(8.0),
                cle(2, E1): v(8.0),
            },
            en_base={
                cle(16, E2): v(6.0),
                cle(30, E1, mois=8): v(6.0),
                cle(2, E1): v(6.0),
            },
        )

        assert [(c.employee_id, c.mois, c.jour) for c in corrections] == [
            (E1, 8, 30),
            (E1, 9, 2),
            (E2, 9, 16),
        ]

    def test_une_correction_se_raconte_en_json(self):
        (c,) = corrections_a_la_main(
            jours_du_fichier={cle(15): v(8.0)},
            ecrits_par_import={cle(15): v(8.5)},
            en_base={cle(15): v(9.0)},
        )

        assert c.to_dict() == {
            "employee_id": E1,
            "annee": 2026,
            "mois": 9,
            "jour": 15,
            "import_precedent": {"heures": 8.5, "type": "travail"},
            "calendrier": {"heures": 9.0, "type": "travail"},
            "fichier": {"heures": 8.0, "type": "travail"},
        }


class TestJoursDuCalendrierReel:
    def test_lit_le_reel_stocke_d_un_salarie(self):
        jours = jours_du_calendrier_reel(
            E1,
            2026,
            9,
            [
                {"jour": 1, "type": "travail", "heures_faites": 7.5},
                {"jour": "2", "type": "repos", "heures_faites": None},
                {"type": "travail"},
                "illisible",
            ],
        )

        assert jours == {cle(1): v(7.5), cle(2): v(None, "repos")}


class TestLaComparaisonAuLotPrecedent:
    def test_une_heure_mal_lue_par_l_ancien_lecteur_est_corrigee_par_la_relecture(self):
        # Ancien lecteur : 17 h lu au lieu de 16 h ; personne n'y a touché.
        assert (
            corrections_a_la_main(
                jours_du_fichier={cle(15): v(8.0)},
                ecrits_par_import={cle(15): v(9.0)},
                en_base={cle(15): v(9.0)},
            )
            == []
        )

    def test_sans_lot_precedent_tout_jour_du_calendrier_que_le_fichier_contredit_est_garde(self):
        corrections = corrections_a_la_main(
            jours_du_fichier={cle(15): v(8.0), cle(16): v(8.0), cle(17): v(8.0)},
            ecrits_par_import={},
            en_base={cle(15): v(9.0), cle(17): v(8.0)},
        )

        assert [c.jour for c in corrections] == [15]
