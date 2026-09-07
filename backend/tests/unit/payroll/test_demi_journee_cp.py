"""Demi-journée de congé payé — traversée du moteur de paie.

Contrat de données : le jour de planning converti par la validation d'absence
porte `type="conges_payes"`, `heures_prevues=0`, `quotite_absence=0.5` et
`demi_journee="matin"|"apres_midi"` (clés serveur). Le moteur doit :
- émettre l'événement CP même si des heures sont pointées ce jour-là
  (l'autre demi-journée est travaillée) ;
- conserver une DEMI-journée de CP à 0 h (quotité < 1) — un CP PLEIN à 0 h
  reste supprimé : comportement historique conservé tant que la récupération
  modulation (même type calendrier) n'est pas distinguable, cf. NOTE sur
  TYPES_SIGNIFICATIFS_A_ZERO_HEURE ;
- compter 0,5 jour dans la retenue/indemnité CP.
"""

import pytest

from app.modules.payroll.application.analyzer import (
    TYPES_SIGNIFICATIFS_A_ZERO_HEURE,
    analyser_horaires_du_mois,
)
from app.modules.payroll.engine.calcul_brut import (
    _format_jours_conges,
    _jours_evenement_conges,
)

pytestmark = pytest.mark.unit


def _jour(annee, mois, jour, type_, heures_prevues, **extra):
    entry = {
        "annee": annee,
        "mois": mois,
        "jour": jour,
        "type": type_,
        "heures_prevues": heures_prevues,
    }
    entry.update(extra)
    return entry


class TestAnalyzerDemiJourneeCp:
    def test_demi_cp_a_zero_heure_atteint_le_bulletin(self):
        """Une demi-journée de CP (heures_prevues=0, quotite_absence=0.5)
        survit à l'agrégation — calcul_brut la compte 0,5 jour."""
        planned = [
            _jour(
                2026, 9, 14, "conges_payes", 0,
                origine="absence", quotite_absence=0.5, demi_journee="matin",
            ),
        ]
        events = analyser_horaires_du_mois(planned, [], 35.0, 2026, 9, "TEST")
        cp = [e for e in events if e["type"] == "conges_payes"]
        assert len(cp) == 1
        assert cp[0]["jour"] == 14
        assert cp[0]["quotite_absence"] == 0.5

    def test_cp_plein_marque_conge_paye_atteint_le_bulletin(self):
        """Un jour CP à 0 h dont la demande d'origine est un VRAI congé payé
        (marqueur source_absence posé à la génération) est conservé : la
        retenue, l'indemnité et l'arbitrage 1/10e apparaissent au bulletin."""
        planned = [
            _jour(
                2026, 9, 14, "conges_payes", 0,
                origine="absence", source_absence="conge_paye",
            ),
        ]
        events = analyser_horaires_du_mois(planned, [], 35.0, 2026, 9, "TEST")
        cp = [e for e in events if e["type"] == "conges_payes"]
        assert len(cp) == 1
        assert cp[0]["source_absence"] == "conge_paye"

    def test_recuperation_modulation_reste_invisible(self):
        """Une récup modulation (même type calendrier que les CP) ne produit
        JAMAIS de ligne CP."""
        planned = [
            _jour(
                2026, 9, 14, "conges_payes", 0,
                origine="absence", source_absence="recuperation_modulation",
            ),
        ]
        events = analyser_horaires_du_mois(planned, [], 35.0, 2026, 9, "TEST")
        assert [e for e in events if e["type"] == "conges_payes"] == []

    def test_cp_plein_sans_marqueur_reste_supprime(self):
        """Comportement historique conservé pour un jour sans marqueur
        (planning pur, reprise DSN) : ignoré à 0 h."""
        assert "conges_payes" not in TYPES_SIGNIFICATIFS_A_ZERO_HEURE
        planned = [
            _jour(2026, 9, 14, "conges_payes", 0, origine="absence"),
        ]
        events = analyser_horaires_du_mois(planned, [], 35.0, 2026, 9, "TEST")
        assert [e for e in events if e["type"] == "conges_payes"] == []

    def test_demi_cp_survit_aux_heures_pointees_le_meme_jour(self):
        """3,5 h pointées le matin + 0,5 CP l'après-midi : l'événement CP est
        émis avec sa quotité (le pass-through refusait tout jour d'absence
        ayant des heures réelles)."""
        planned = [
            _jour(
                2026, 9, 14, "conges_payes", 0,
                origine="absence", quotite_absence=0.5, demi_journee="apres_midi",
            ),
        ]
        actual = [
            {"annee": 2026, "mois": 9, "jour": 14, "heures_faites": 3.5},
        ]
        events = analyser_horaires_du_mois(planned, actual, 35.0, 2026, 9, "TEST")
        cp = [e for e in events if e["type"] == "conges_payes"]
        assert len(cp) == 1
        assert cp[0]["quotite_absence"] == 0.5
        assert cp[0]["demi_journee"] == "apres_midi"

    def test_cp_plein_avec_heures_pointees_reste_ignore(self):
        """Comportement historique conservé : un jour de CP PLEIN portant des
        heures réelles > 0 n'émet pas l'événement (le réel prime)."""
        planned = [
            _jour(2026, 9, 14, "conges_payes", 0, origine="absence"),
        ]
        actual = [
            {"annee": 2026, "mois": 9, "jour": 14, "heures_faites": 7.0},
        ]
        events = analyser_horaires_du_mois(planned, actual, 35.0, 2026, 9, "TEST")
        assert [e for e in events if e["type"] == "conges_payes"] == []


class TestQuotiteEvenementConges:
    def test_defaut_jour_plein(self):
        assert _jours_evenement_conges({"jour": 14, "type": "conges_payes"}) == 1.0

    def test_demi_journee(self):
        assert (
            _jours_evenement_conges(
                {"jour": 14, "type": "conges_payes", "quotite_absence": 0.5}
            )
            == 0.5
        )

    def test_quotite_invalide_ou_hors_bornes(self):
        assert _jours_evenement_conges({"quotite_absence": "n/a"}) == 1.0
        assert _jours_evenement_conges({"quotite_absence": 0}) == 1.0
        assert _jours_evenement_conges({"quotite_absence": 3}) == 1.0


class TestFormatJoursConges:
    def test_libelles(self):
        assert _format_jours_conges(1.0) == "1 jour"
        assert _format_jours_conges(5.0) == "5 jours"
        assert _format_jours_conges(0.5) == "0,5 jour"
        assert _format_jours_conges(2.5) == "2,5 jours"
