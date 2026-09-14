"""Bilan par semaine des absences (retour Gaëlle, Colorplast, 14/09/2026).

Les semaines sont celles des feuilles de pointage de juillet 2026, importées
par Gaëlle : contrat 39 h, 8,5 h du lundi au jeudi, 5 h le vendredi. Quadra
retient le manque de la semaine entière ; les heures faites en plus un jour
compensent celles manquées un autre jour, quel que soit l'ordre.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois

CONTRAT_39H = 39.0
HORAIRE_39H = {0: 8.5, 1: 8.5, 2: 8.5, 3: 8.5, 4: 5.0}  # lundi → vendredi


def _semaine(lundi: int, faits: list[float | None], *, mois: int = 7, feries: set[int] = frozenset()):
    """Prévu et réel d'une semaine de juillet 2026 commençant le `lundi`.

    `faits[i]` : heures pointées le jour i (None = pas de pointage ce jour-là).
    """
    prevu, reel = [], []
    for i, heures_prevues in HORAIRE_39H.items():
        jour = lundi + i
        if jour in feries:
            prevu.append({"annee": 2026, "mois": mois, "jour": jour, "type": "ferie", "heures_prevues": 0.0})
            reel.append({"annee": 2026, "mois": mois, "jour": jour, "type": "ferie", "heures_faites": None})
            continue
        prevu.append({"annee": 2026, "mois": mois, "jour": jour, "type": "travail", "heures_prevues": heures_prevues})
        if faits[i] is not None:
            reel.append({"annee": 2026, "mois": mois, "jour": jour, "type": "travail", "heures_faites": faits[i]})
    return prevu, reel


def _absences(evenements: list[dict]) -> dict[int, float]:
    """Heures d'absence injustifiée par jour, tous typages confondus."""
    par_jour: dict[int, float] = {}
    for ev in evenements:
        if "absence_injustifiee" in ev["type"]:
            par_jour[ev["jour"]] = round(par_jour.get(ev["jour"], 0.0) + ev["heures"], 2)
    return par_jour


def _heures_sup(evenements: list[dict]) -> float:
    return round(sum(ev["heures"] for ev in evenements if ev["type"] in ("travail_hs25", "travail_hs50")), 2)


class TestFuckarJuillet2026:
    def test_semaine_28_le_surplus_de_fin_de_semaine_compense_les_manques(self):
        # −1,5 mardi, −4 mercredi, +1 jeudi, +2 vendredi : 36,5 h sur 39.
        prevu, reel = _semaine(6, [8.5, 7.0, 4.5, 9.5, 7.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "FUCKAR")
        assert _absences(ev) == {8: 2.5}
        assert _heures_sup(ev) == 0

    def test_semaine_29_avec_ferie_le_vendredi_compense_le_mercredi(self):
        # Mardi 14 férié (0 h prévue). Mercredi 0 h, vendredi 6,5 h pour 5.
        prevu, reel = _semaine(13, [8.5, None, 0.0, 8.5, 6.5], feries={14})
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "FUCKAR")
        assert _absences(ev) == {15: 7.0}
        assert _heures_sup(ev) == 0

    def test_semaine_30_une_journee_entiere_sans_compensation(self):
        prevu, reel = _semaine(20, [0.0, 8.5, 8.5, 8.5, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "FUCKAR")
        assert _absences(ev) == {20: 8.5}

    def test_semaine_31_le_surplus_efface_le_manque_et_le_reste_est_heures_sup(self):
        # −1,5 mercredi, +3,5 jeudi : 41 h. Jamais absence ET heures sup.
        prevu, reel = _semaine(27, [8.5, 8.5, 7.0, 12.0, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "FUCKAR")
        assert _absences(ev) == {}
        assert _heures_sup(ev) == pytest.approx(2.0)


class TestEspinosaJuillet2026:
    def test_le_surplus_d_avant_l_absence_compense_aussi(self):
        # +1 lundi à mercredi, 0 h vendredi pour 5 : 37 h sur 39.
        prevu, reel = _semaine(27, [9.5, 9.5, 9.5, 8.5, 0.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "ESPINOSA")
        assert _absences(ev) == {31: 2.0}
        assert _heures_sup(ev) == 0


class TestRepartitionSurLesJours:
    def test_le_surplus_compense_d_abord_les_premiers_jours_manques(self):
        # −1,5 mardi, −4 mercredi, +3 jeudi : il reste 2,5 h, sur le mercredi.
        prevu, reel = _semaine(6, [8.5, 7.0, 4.5, 11.5, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        assert _absences(ev) == {8: 2.5}

    def test_un_surplus_insuffisant_laisse_deux_jours(self):
        # −1,5 mardi, −4 mercredi, +1 jeudi : mardi effacé de 1, il reste 0,5 + 4.
        prevu, reel = _semaine(6, [8.5, 7.0, 4.5, 9.5, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        assert _absences(ev) == {7: 0.5, 8: 4.0}

    def test_une_semaine_exactement_compensee_ne_porte_rien(self):
        prevu, reel = _semaine(6, [8.5, 6.5, 8.5, 10.5, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        assert _absences(ev) == {}
        assert _heures_sup(ev) == 0

    def test_un_jour_sans_pointage_reste_neutre(self):
        # Jeudi sans pointage : ni manque ni surplus. Mardi −1,5 reste.
        prevu, reel = _semaine(6, [8.5, 7.0, 8.5, None, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        assert _absences(ev) == {7: 1.5}

    def test_une_semaine_sans_aucun_ecart_ne_porte_rien(self):
        prevu, reel = _semaine(6, [8.5, 8.5, 8.5, 8.5, 5.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        assert _absences(ev) == {}
        assert _heures_sup(ev) == 0


class TestTypageEtContrat35h:
    def test_le_typage_base_puis_hs25_suit_la_position_dans_la_semaine(self):
        # Semaine à 37 h, manque de 2 h le vendredi : la 36ᵉ et la 37ᵉ heure
        # prévues sont au-delà de 35 h, donc typées hs25 (sans effet sur un
        # contrat > 35 h, la répartition 35/39 s'applique après).
        prevu, reel = _semaine(27, [9.5, 9.5, 9.5, 8.5, 0.0])
        ev = analyser_horaires_du_mois(prevu, reel, CONTRAT_39H, 2026, 7, "x")
        types = {ev_["type"] for ev_ in ev if "absence_injustifiee" in ev_["type"]}
        assert types == {"absence_injustifiee_hs25"}

    def test_contrat_35h_meme_regle(self):
        prevu = [
            {"annee": 2026, "mois": 7, "jour": j, "type": "travail", "heures_prevues": 7.0}
            for j in (6, 7, 8, 9, 10)
        ]
        reel = [
            {"annee": 2026, "mois": 7, "jour": j, "type": "travail", "heures_faites": h}
            for j, h in ((6, 7.0), (7, 5.0), (8, 7.0), (9, 8.0), (10, 7.0))
        ]
        ev = analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 7, "x")
        assert _absences(ev) == {7: 1.0}
        assert _heures_sup(ev) == 0
