"""
Un jour sans pointage n'est pas un jour d'absence.

Le moteur construisait le mois en comparant prévu et réel : tout jour prévu
travaillé sans entrée dans les heures réelles devenait une « absence
injustifiée », donc une retenue.

C'est l'inverse de la bonne règle. Une absence est un **fait constaté** —
quelqu'un a saisi zéro heure, ou une demande d'absence a été validée — pas un
trou dans les données.

Le repli existant (`planning_repli`) ne couvrait que les mois **entièrement**
sans pointage. Or les calendriers de Colorplast sont partiels : 322 heures
réelles pour 1 113 prévues en janvier. Chaque jour manquant était donc retenu.

Vécu le 27/08/2026 : remettre le 30/06 de DEMORY en « travail » l'a
immédiatement fait requalifier en absence injustifiée de 93,93 € — la même
retenue que celle, réelle, du 8 juin. Il était déduit deux fois.
"""

from __future__ import annotations

from app.modules.payroll.documents.payslip_run_heures import jour_du_calendrier_final


class TestJourSansPointage:
    def test_un_jour_prevu_sans_reel_est_travaille(self):
        """Le cas qui déduisait à tort : aucune heure saisie ce jour-là."""
        prevu = {"jour": 30, "type": "travail", "heures_prevues": 7.63}
        jour = jour_du_calendrier_final(prevu, None, 30)
        assert jour["type"] == "travail", (
            "Un jour prévu travaillé sans pointage doit être considéré comme "
            f"travaillé, pas retenu. Reçu : {jour['type']}"
        )
        assert jour.get("heures") == 7.63 or jour.get("heures_prevues") == 7.63

    def test_un_jour_pointe_a_zero_reste_une_absence(self):
        """L'absence constatée, elle, doit continuer d'être déduite."""
        prevu = {"jour": 12, "type": "travail", "heures_prevues": 7.0}
        reel = {"jour": 12, "type": "absence_injustifiee", "heures_faites": 0.0}
        jour = jour_du_calendrier_final(prevu, reel, 12)
        assert jour["type"] == "absence_injustifiee"

    def test_le_pointage_reel_prime_sur_le_prevu(self):
        prevu = {"jour": 5, "type": "travail", "heures_prevues": 7.0}
        reel = {"jour": 5, "type": "travail", "heures_faites": 9.5}
        jour = jour_du_calendrier_final(prevu, reel, 5)
        assert jour.get("heures_faites") == 9.5

    def test_un_jour_de_repos_reste_un_repos(self):
        prevu = {"jour": 7, "type": "repos", "heures_prevues": 0.0}
        jour = jour_du_calendrier_final(prevu, None, 7)
        assert jour["type"] == "repos"

    def test_une_absence_au_planning_reste_une_absence(self):
        """Une absence validée est posée sur le planning : elle doit tenir."""
        prevu = {"jour": 15, "type": "arret_maladie", "heures_prevues": 7.0}
        jour = jour_du_calendrier_final(prevu, None, 15)
        assert jour["type"] == "arret_maladie"
