"""Un jour d'absence non rémunérée rattrapé dans la même semaine (retour d'Elsa, 10/11/2026).

Colorplast, salariée A.B., CDD 39 h, semaine 42 (12 au 18/10/2026) : absence
non rémunérée de 8,5 h le lundi 12, puis 12 + 11,5 + 12 + 9,5 = 45 h faites du
mardi au vendredi. Martine retenait 8,5 h ET payait 14,5 h sup (option de
compensation : 45 − 30,5 prévues) ; sans l'option, elle retenait 8,5 h et ne
payait que 6 h sup, laissant 8,5 h faites sans paie.

Le légal : les heures sup se décomptent par semaine sur les heures accomplies
(C. trav. L3121-28, L3121-29) ; seules les heures perdues pour une cause
collective peuvent être récupérées sans être payées (L3121-50). Les 45 h faites
sont donc payées : 39 h par le salaire mensualisé, 6 h en heures sup (4 h à
25 %, 2 h à 50 %, L3121-36), et il ne reste rien à retenir.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.application.compensation_semaines import appliquer_aux_mois

pytestmark = pytest.mark.unit

CONTRAT_39H = 39.0
# Semaine 42 de 2026 : lundi 12 → vendredi 16 octobre.
HORAIRE = {12: 8.5, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5.0}


def _semaine(faits: dict[int, float], *, absence: dict[int, float] | None = None):
    absence = absence or {}
    prevu, reel = [], []
    for jour, heures in HORAIRE.items():
        if jour in absence:
            prevu.append({"annee": 2026, "mois": 10, "jour": jour, "type": "absence_non_remuneree",
                          "heures_prevues": absence[jour]})
        else:
            prevu.append({"annee": 2026, "mois": 10, "jour": jour, "type": "travail", "heures_prevues": heures})
        if jour in faits:
            type_reel = "absence_non_remuneree" if jour in absence else "travail"
            reel.append({"annee": 2026, "mois": 10, "jour": jour, "type": type_reel, "heures_faites": faits[jour]})
    return prevu, reel


def _par_type(evenements: list[dict]) -> dict[str, float]:
    totaux: dict[str, float] = {}
    for ev in evenements:
        totaux[ev["type"]] = round(totaux.get(ev["type"], 0.0) + float(ev.get("heures") or 0.0), 2)
    return totaux


class TestAnalyseLegale:
    def test_semaine_42_six_heures_sup_et_rien_a_retenir(self):
        prevu, reel = _semaine({12: 0, 13: 12, 14: 11.5, 15: 12, 16: 9.5}, absence={12: 8.5})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert not any(e["type"] == "absence_non_remuneree" for e in ev)
        assert _par_type(ev) == {"travail_hs25": 4.0, "travail_hs50": 2.0}

    def test_rattrapage_partiel_le_reste_est_retenu(self):
        # 36 h faites : 5,5 h au-delà des 30,5 h prévues, aucune heure sup.
        prevu, reel = _semaine({12: 0, 13: 10, 14: 10, 15: 10, 16: 6}, absence={12: 8.5})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert _par_type(ev) == {"absence_non_remuneree": 3.0}

    def test_sans_heure_en_plus_l_absence_est_retenue_entiere(self):
        prevu, reel = _semaine({12: 0, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5}, absence={12: 8.5})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert _par_type(ev) == {"absence_non_remuneree": 8.5}

    def test_un_samedi_travaille_rattrape_le_lundi(self):
        prevu, reel = _semaine({12: 0, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5}, absence={12: 8.5})
        reel.append({"annee": 2026, "mois": 10, "jour": 17, "type": "travail", "heures_faites": 8.5})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert _par_type(ev) == {}

    def test_un_sans_solde_pose_a_zero_heure_vaut_la_journee_du_contrat(self):
        # Validation d'une demande « sans solde » : 0 h au planning, le bulletin
        # retient 39 / 5 = 7,8 h. 3 h faites en plus le vendredi → 4,8 h retenues.
        prevu, reel = _semaine({12: 0, 13: 8.5, 14: 8.5, 15: 8.5, 16: 8}, absence={12: 0.0})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert _par_type(ev) == {"absence_non_remuneree": 4.8}

    def test_les_jours_manques_passent_avant_le_sans_solde(self):
        # Mardi 4,5 h faites (manque 4 h), vendredi 9 h (surplus 4 h) : le
        # surplus couvre le manque du mardi, rien ne reste pour le lundi.
        prevu, reel = _semaine({12: 0, 13: 4.5, 14: 8.5, 15: 8.5, 16: 9}, absence={12: 8.5})

        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert _par_type(ev) == {"absence_non_remuneree": 8.5}

    def test_le_planning_n_est_pas_modifie(self):
        prevu, reel = _semaine({12: 0, 13: 12, 14: 11.5, 15: 12, 16: 9.5}, absence={12: 8.5})

        analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        assert (prevu[0]["type"], prevu[0]["heures_prevues"]) == ("absence_non_remuneree", 8.5)
        assert "heures" not in prevu[0] or prevu[0]["heures"] == 8.5


class TestCompensationEntreSemaines:
    FENETRE = (date(2026, 10, 12), date(2026, 10, 18))

    def test_semaine_42_vaut_six_heures_et_rien_n_est_retenu(self):
        prevu, reel = _semaine({12: 0, 13: 12, 14: 11.5, 15: 12, 16: 9.5}, absence={12: 8.5})
        evenements = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        resultat, compensation = appliquer_aux_mois(
            {(2026, 10): evenements, (2026, 9): []}, prevu, reel, CONTRAT_39H, self.FENETRE
        )

        assert [(s.semaine, s.total) for s in compensation.semaines] == [(42, 6.0)]
        assert (compensation.net25, compensation.net50) == (4.0, 2.0)
        assert _par_type(resultat[(2026, 10)]) == {"travail_hs25": 4.0, "travail_hs50": 2.0}

    def test_une_absence_non_rattrapee_ne_change_pas(self):
        prevu, reel = _semaine({12: 0, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5}, absence={12: 8.5})
        evenements = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        resultat, compensation = appliquer_aux_mois(
            {(2026, 10): evenements, (2026, 9): []}, prevu, reel, CONTRAT_39H, self.FENETRE
        )

        assert [(s.semaine, s.total) for s in compensation.semaines] == [(42, 0.0)]
        assert _par_type(resultat[(2026, 10)]) == {"absence_non_remuneree": 8.5}

    def test_un_sans_solde_a_zero_heure_retenu_en_entier_ne_compte_pas(self):
        prevu, reel = _semaine({12: 0, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5}, absence={12: 0.0})
        evenements = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 10, "A.B.")

        _, compensation = appliquer_aux_mois(
            {(2026, 10): evenements, (2026, 9): []}, prevu, reel, CONTRAT_39H, self.FENETRE
        )

        assert [(s.semaine, s.total) for s in compensation.semaines] == [(42, 0.0)]
