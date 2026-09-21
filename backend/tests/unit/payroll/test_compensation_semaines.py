"""Compensation des heures entre semaines — la règle de Gaëlle, en pur.

Classeur `detail-heures-sup-06-2026-colorplast.xlsx` : écart journalier faites −
prévues ; par semaine `Majo 25 % = min(total, 4)` (négatif compris), le reste à
50 % ; somme sur la fenêtre, semaines négatives comprises ; jamais de retenue.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.compensation_semaines import (
    avec_saisie_manuelle,
    option_active,
    appliquer,
    compenser,
    ecarts_par_semaine,
    majorations,
    mention,
)

pytestmark = pytest.mark.unit

FENETRE_JUIN = (date(2026, 5, 25), date(2026, 6, 21))  # S22 → S25


class TestMajorations:
    @pytest.mark.parametrize(
        ("total", "attendu"),
        [(7.5, (4.0, 3.5)), (2.0, (2.0, 0.0)), (4.0, (4.0, 0.0)), (-5.0, (-5.0, 0.0)), (0.0, (0.0, 0.0))],
    )
    def test_contrat_39h_quatre_heures_a_25_puis_50(self, total, attendu):
        assert majorations(total, 39.0) == attendu

    def test_contrat_35h_huit_heures_a_25(self):
        assert majorations(10.0, 35.0) == (8.0, 2.0)


class TestCompensationJuin2026:
    def test_bugny_retrouve_14_et_7(self):
        ecarts = {(2026, 22): 2.0, (2026, 23): 4.0, (2026, 24): 7.5, (2026, 25): 7.5}

        c = compenser(ecarts, 39.0)

        assert (c.net25, c.net50, c.solde_negatif) == (14.0, 7.0, 0.0)

    def test_fuckar_retrouve_4_et_3_avec_une_semaine_negative(self):
        ecarts = {(2026, 22): -5.0, (2026, 23): 7.0, (2026, 24): 1.0, (2026, 25): 4.0}

        c = compenser(ecarts, 39.0)

        assert (c.net25, c.net50, c.solde_negatif) == (4.0, 3.0, 0.0)
        assert [(s.semaine, s.total, s.majo25, s.majo50) for s in c.semaines][0] == (22, -5.0, -5.0, 0.0)

    def test_un_net_negatif_a_25_mange_le_50(self):
        assert compenser({(2026, 22): -6.0, (2026, 23): 10.0}, 39.0).net25 == 0.0
        assert compenser({(2026, 22): -6.0, (2026, 23): 10.0}, 39.0).net50 == 4.0

    def test_ce_qui_reste_de_negatif_n_est_ni_retenu_ni_reporte_seulement_dit(self):
        c = compenser({(2026, 22): -8.0, (2026, 23): 2.0}, 39.0)

        assert (c.net25, c.net50, c.solde_negatif) == (0.0, 0.0, -6.0)


def _jour(mois: int, jour: int, prevu: float | None, fait: float | None, *, type_="travail"):
    p = {"annee": 2026, "mois": mois, "jour": jour, "type": type_, "heures_prevues": prevu}
    r = None if fait is None else {"annee": 2026, "mois": mois, "jour": jour, "type": "travail", "heures_faites": fait}
    return p, r


def _semaine(lundi: int, prevus: list[float], faits: list[float | None], *, mois: int = 7):
    planned, actual = [], []
    for i, (p, f) in enumerate(zip(prevus, faits)):
        pj, rj = _jour(mois, lundi + i, p, f)
        planned.append(pj)
        if rj is not None:
            actual.append(rj)
    return planned, actual


class TestEcartsParSemaine:
    HORAIRE = [8.5, 8.5, 8.5, 8.5, 5.0]

    def test_fuckar_semaine_28_vaut_moins_2_5(self):
        planned, actual = _semaine(6, self.HORAIRE, [8.5, 7.0, 4.5, 9.5, 7.0])

        assert ecarts_par_semaine(planned, actual, (date(2026, 6, 22), date(2026, 7, 26))) == {(2026, 28): -2.5}

    def test_un_jour_prevu_sans_pointage_est_neutre(self):
        planned, actual = _semaine(6, self.HORAIRE, [8.5, None, 8.5, 8.5, 5.0])

        assert ecarts_par_semaine(planned, actual, (date(2026, 6, 22), date(2026, 7, 26))) == {(2026, 28): 0.0}

    def test_un_jour_non_prevu_compte_pour_ses_heures(self):
        planned, actual = _semaine(6, self.HORAIRE, [8.5, 8.5, 8.5, 8.5, 5.0])
        actual.append({"annee": 2026, "mois": 7, "jour": 11, "type": "travail", "heures_faites": 4.0})  # samedi

        assert ecarts_par_semaine(planned, actual, (date(2026, 6, 22), date(2026, 7, 26))) == {(2026, 28): 4.0}

    def test_un_mois_sans_aucun_pointage_est_neutre(self):
        planned, _ = _semaine(6, self.HORAIRE, [None] * 5)

        assert ecarts_par_semaine(planned, [], (date(2026, 6, 22), date(2026, 7, 26))) == {}

    def test_seules_les_semaines_de_la_fenetre_comptent(self):
        planned, actual = _semaine(27, self.HORAIRE, [9.5, 9.5, 9.5, 9.5, 5.0])  # S31, hors fenêtre de juillet

        assert ecarts_par_semaine(planned, actual, (date(2026, 6, 22), date(2026, 7, 26))) == {}


class TestApplicationAuCalendrier:
    FENETRE = (date(2026, 6, 22), date(2026, 7, 26))

    def _evenements_juillet(self):
        return [
            {"annee": 2026, "mois": 7, "jour": 2, "type": "travail_hs25", "heures": 1.5},
            {"annee": 2026, "mois": 7, "jour": 13, "type": "conges_payes", "heures_prevues": 8.5},
            {"annee": 2026, "mois": 7, "jour": 24, "type": "absence_injustifiee_base", "heures": 0.9},
            {"annee": 2026, "mois": 7, "jour": 24, "type": "absence_injustifiee_hs25", "heures": 0.1},
            {"annee": 2026, "mois": 7, "jour": 30, "type": "travail_hs25", "heures": 2.0},  # S31 : hors fenêtre
        ]

    def test_les_hs_et_absences_de_la_fenetre_font_place_aux_nets(self):
        c = compenser({(2026, 27): 1.5, (2026, 30): -1.0}, 39.0)

        resultat = appliquer(self._evenements_juillet(), self.FENETRE, c, annee=2026, mois=7)

        assert [(e["jour"], e["type"], e.get("heures")) for e in resultat] == [
            (13, "conges_payes", None),
            (26, "travail_hs25", 0.5),
            (30, "travail_hs25", 2.0),
        ]
        assert resultat[1]["compensation_semaines"] is True

    def test_sans_net_positif_aucune_ligne_ajoutee(self):
        c = compenser({(2026, 30): -1.0}, 39.0)

        resultat = appliquer(self._evenements_juillet(), self.FENETRE, c, annee=2026, mois=7)

        assert [e["type"] for e in resultat] == ["conges_payes", "travail_hs25"]

    def test_les_nets_tombent_dans_le_mois_du_dernier_jour_de_la_fenetre(self):
        """Événements de juin : la fenêtre finit en juillet, les nets n'y sont pas."""
        c = compenser({(2026, 26): 3.0}, 39.0)
        juin = [{"annee": 2026, "mois": 6, "jour": 26, "type": "travail_hs25", "heures": 3.0}]

        assert appliquer(juin, self.FENETRE, c, annee=2026, mois=6) == []


def test_la_mention_nomme_les_semaines_et_les_nets():
    c = compenser({(2026, 27): 1.5, (2026, 30): -1.0}, 39.0)

    assert mention(c) == (
        "Heures compensées entre semaines (option société) : S27 +1,5 · S30 −1,0 "
        "→ 0,5 h à 25 %, 0 h à 50 %."
    )


def test_une_regularisation_anterieure_n_est_jamais_remplacee():
    """Une absence d'un mois antérieur rattachée au bulletin courant porte une date
    dans la fenêtre : elle n'est pas une semaine à compenser."""
    fenetre = (date(2026, 6, 22), date(2026, 7, 26))
    c = compenser({(2026, 27): 1.0}, 39.0)
    evenements = [
        {"annee": 2026, "mois": 6, "jour": 25, "type": "absence_injustifiee_base", "heures": 7.0,
         "is_regularisation_anterieure": True},
    ]

    resultat = appliquer(evenements, fenetre, c, annee=2026, mois=7)

    assert resultat[0]["is_regularisation_anterieure"] is True


class TestOptionActive:
    """Le générateur lit l'option dans les réglages de la société, et rien d'autre."""

    def test_vraie_quand_la_societe_l_a_cochee(self):
        assert option_active({"settings": {"compensation_heures_entre_semaines": True}}) is True

    def test_fausse_par_defaut(self):
        assert option_active({}) is False
        assert option_active({"settings": None}) is False
        assert option_active({"settings": {}}) is False
        assert option_active({"settings": {"compensation_heures_entre_semaines": False}}) is False

    def test_une_chaine_ne_vaut_pas_oui(self):
        assert option_active({"settings": {"compensation_heures_entre_semaines": "true"}}) is False


class TestAvecSaisieManuelle:
    """Les heures sup saisies à la main priment sur le calendrier dans le moteur :
    quand elles diffèrent des nets compensés, le bulletin doit le dire."""

    def _resume(self):
        return compenser({(2026, 27): 1.5, (2026, 30): -1.0}, 39.0).resume()

    def test_sans_saisie_le_resume_est_inchange(self):
        resume = self._resume()
        assert avec_saisie_manuelle(resume, 0.0, 0.0) == resume

    def test_une_saisie_differente_des_nets_est_dite(self):
        resume = avec_saisie_manuelle(self._resume(), 8.0, 0.0)
        assert resume["heures_saisies"] == {"hs25": 8.0, "hs50": 0.0}
        assert resume["mention"].endswith(
            "Heures supplémentaires saisies à la main retenues sur le bulletin : "
            "8 h à 25 %, 0 h à 50 %."
        )

    def test_une_saisie_egale_aux_nets_ne_rajoute_rien(self):
        resume = self._resume()  # net25 = 0.5, net50 = 0
        assert avec_saisie_manuelle(resume, 0.5, 0.0)["mention"] == resume["mention"]
        assert "heures_saisies" not in avec_saisie_manuelle(resume, 0.5, 0.0)

    def test_le_resume_d_origine_n_est_pas_modifie(self):
        resume = self._resume()
        avec_saisie_manuelle(resume, 8.0, 0.0)
        assert "heures_saisies" not in resume


class TestAbsencePartielleDeclaree:
    """Un jour prévu en absence déclarée de X h, où le salarié a quand même
    travaillé : il devait faire la journée moins X. Marion Gautheron, juillet
    2026 : jeudi 09/07 absence de 7,5 h sur une journée de 8,5, 1 h faite →
    écart 0, pas 1 h de surplus."""

    def _planning(self):
        # juillet 2026 : jeudis 02, 09, 16, 23, 30 ; lundis 06, 13, 20, 27 ; vendredis 03, 10, 17, 24
        jours = []
        for j in (1, 2, 6, 7, 8, 13, 15, 16, 21, 22, 23, 27, 28, 29, 30):
            jours.append({"annee": 2026, "mois": 7, "jour": j, "type": "travail", "heures_prevues": 8.5})
        for j in (3, 17, 24, 31):
            jours.append({"annee": 2026, "mois": 7, "jour": j, "type": "travail", "heures_prevues": 5.0})
        jours.append({"annee": 2026, "mois": 7, "jour": 9, "type": "absence_non_remuneree", "heures_prevues": 7.5})
        jours.append({"annee": 2026, "mois": 7, "jour": 20, "type": "absence_non_remuneree", "heures_prevues": 0.26})
        jours.append({"annee": 2026, "mois": 7, "jour": 10, "type": "absence_non_remuneree", "heures_prevues": 2.5})
        jours.append({"annee": 2026, "mois": 7, "jour": 14, "type": "ferie", "heures_prevues": 0})
        return jours

    def _reel(self, **faites):
        return [{"annee": 2026, "mois": 7, "jour": int(j), "type": "travail", "heures_faites": h} for j, h in faites.items()]

    def test_une_heure_faite_sur_une_absence_de_sept_heures_et_demie_est_neutre(self):
        ecarts = ecarts_par_semaine(self._planning(), self._reel(**{"6": 8.5, "7": 0, "8": 0, "9": 1.0, "10": 2.5}), (date(2026, 6, 22), date(2026, 7, 26)))
        # 07 et 08 : 0 h faite sur un jour prévu 8,5 → −8,5 chacun ; 09 : 1 − (8,5 − 7,5) = 0 ; 10 : 2,5 − (5 − 2,5) = 0
        assert ecarts[(2026, 28)] == pytest.approx(-17.0)

    def test_un_quart_d_heure_d_absence_declaree_et_la_journee_faite(self):
        ecarts = ecarts_par_semaine(self._planning(), self._reel(**{"20": 8.25, "21": 8.5, "22": 8.5, "23": 8.5, "24": 5.0}), (date(2026, 6, 22), date(2026, 7, 26)))
        # 20/07 : 8,25 − (8,5 − 0,26) = +0,01
        assert ecarts[(2026, 30)] == pytest.approx(0.01)

    def test_travailler_plus_que_le_reste_attendu_est_du_surplus(self):
        """Hugo Fuckar, 10/07 : absence de 2,5 h sur un vendredi de 5 h, 7 h faites → +4,5."""
        ecarts = ecarts_par_semaine(self._planning(), self._reel(**{"6": 8.5, "7": 8.5, "8": 8.5, "9": 1.0, "10": 7.0}), (date(2026, 6, 22), date(2026, 7, 26)))
        assert ecarts[(2026, 28)] == pytest.approx(4.5)

    def test_absence_complete_sans_pointage_reste_neutre(self):
        planning = [{"annee": 2026, "mois": 7, "jour": 20, "type": "absence_non_remuneree", "heures_prevues": 8.5},
                    {"annee": 2026, "mois": 7, "jour": 21, "type": "travail", "heures_prevues": 8.5}]
        ecarts = ecarts_par_semaine(planning, self._reel(**{"21": 8.5}), (date(2026, 6, 22), date(2026, 7, 26)))
        assert ecarts.get((2026, 30), 0.0) == pytest.approx(0.0)
