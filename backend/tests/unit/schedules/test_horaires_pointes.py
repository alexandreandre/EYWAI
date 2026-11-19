"""Heure de début et de fin pointées, du relevé au calendrier réel (17/11).

Les primes des usines dépendent de l'heure de prise de poste : le relevé
porte les badgeages, le calendrier doit en garder la première entrée et la
dernière sortie, sans rien changer aux heures faites.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.modules.schedules.application import commands
from app.modules.schedules.application.parsers.banque_heures import try_parse_banque_heures
from app.modules.schedules.application.parsers.cegid_weekly import try_parse_cegid_weekly
from app.modules.schedules.application.persist_timesheet import _merge_days
from app.modules.schedules.domain.horaires_pointes import (
    debut_dans_les_plages,
    en_hhmm,
    garder_les_horaires,
    horaires_de_l_entree,
    minutes_dans_la_nuit,
)
from app.modules.schedules.schemas.ai import AiDayEntry
from app.modules.schedules.schemas.requests import ActualHoursEntry, ActualHoursRequest


class TestLectures:
    def test_formats_d_heure(self):
        assert en_hhmm(800) == "08:00"
        assert en_hhmm("5:43") == "05:43"
        assert en_hhmm("1546") == "15:46"
        assert en_hhmm(None) is None
        assert en_hhmm("__:__") is None

    def test_horaires_d_un_jour_travaille(self):
        assert horaires_de_l_entree({"type": "travail", "punch_entry_raw": "800", "punch_exit_raw": "1546"}) == {
            "debut": "08:00",
            "fin": "15:46",
        }
        assert horaires_de_l_entree({"type": "travail", "heure_debut": "03:50", "heure_fin": None}) == {"debut": "03:50"}

    def test_un_jour_non_travaille_n_a_pas_d_horaire(self):
        assert horaires_de_l_entree({"type": "conges_payes", "heure_debut": "08:00"}) == {}


class TestPlages:
    def test_poste_de_4_h_badge_a_3_h_50(self):
        plages = [{"de": "03:30", "a": "04:30"}, {"de": "11:30", "a": "12:30"}]
        assert debut_dans_les_plages("03:50", plages)
        assert debut_dans_les_plages("11:52", plages)
        assert not debut_dans_les_plages("05:43", plages)
        assert not debut_dans_les_plages(None, plages)

    def test_plage_qui_passe_minuit(self):
        plages = [{"de": "21:30", "a": "00:30"}]
        assert debut_dans_les_plages("21:45", plages)
        assert debut_dans_les_plages("00:10", plages)
        assert not debut_dans_les_plages("05:00", plages)


class TestNuit:
    def test_poste_de_5_h_une_heure_de_nuit(self):
        assert minutes_dans_la_nuit("05:00", "13:15") == 60

    def test_poste_de_4_h_deux_heures(self):
        assert minutes_dans_la_nuit("04:00", "12:00") == 120

    def test_poste_de_nuit_sur_deux_jours(self):
        assert minutes_dans_la_nuit("21:00", "05:00") == 7 * 60

    def test_poste_de_jour(self):
        assert minutes_dans_la_nuit("07:00", "17:00") == 0

    def test_sans_fin(self):
        assert minutes_dans_la_nuit("05:00", None) == 0


class TestRelevesPdf:
    def test_cegid_mont_blanc(self):
        texte = (
            'Pointages "retenu" + commentaires, semaine à semaine Du 19/10/2026 au 25/10/2026 26/10/2026\n'
            "272 SALARIE Test\n"
            "Lundi 3:50 8:32 9:01 10:26 10:36 12:00 7:31\n19/10/26\n"
            "Mardi 5:44 8:27 8:39 12:04 12:38 14:00 7:30\nPRESENCE 5\n20/10/26\n"
            "Mercredi 5:45 12:11 12:39 7:47\n21/10/26\n"
            "Jeudi\n22/10/26\nVendredi\n23/10/26\nSamedi\n24/10/26\nDimanche\n25/10/26\n"
            "Total pour la semaine 43/2026: 22:48\n" + " " * 200
        )
        res = try_parse_cegid_weekly(texte, target_year=2026, target_month=10)
        jours = {d.jour: d for d in res.employees[0].days}
        assert (jours[19].debut, jours[19].fin) == ("03:50", "12:00")
        assert (jours[20].debut, jours[20].fin) == ("05:44", "14:00")
        # Trois badgeages : la sortie manque, la fin reste inconnue.
        assert (jours[21].debut, jours[21].fin) == ("05:45", None)
        # Les heures lues ne changent pas.
        assert jours[19].heures == 7.52

    def test_banque_heures_cartol(self):
        lignes = "\n".join(
            [
                "BANQUE HEURES V1",
                "000022 SALARIE Test Solde HS avant période : 14,00",
                "01/10/2026 05:00 08:00 08:20 12:00 12:30 13:15 __:__ __:__ 7,75 00:00 00:00",
                "02/10/2026 07:00 10:00 10:10 11:45 __:__ __:__ __:__ __:__ 4,75 00:00 00:00",
                "05/10/2026 07:00 10:00 10:20 12:00 13:00 __:__ __:__ __:__ 4,67 00:00 00:00",
            ]
        ) + "\n" + " " * 300
        res = try_parse_banque_heures(lignes, target_year=2026, target_month=10)
        jours = {d.jour: d for d in res.employees[0].days}
        assert (jours[1].debut, jours[1].fin) == ("05:00", "13:15")
        assert (jours[2].debut, jours[2].fin) == ("07:00", "11:45")
        assert (jours[5].debut, jours[5].fin) == ("07:00", None)


class TestEcritureAuCalendrier:
    def test_l_import_garde_debut_et_fin(self):
        jours = _merge_days(
            [],
            [
                AiDayEntry(jour=19, heures=7.5, type="travail", heure_debut="03:50", heure_fin="12:00"),
                AiDayEntry(jour=20, heures=7.0, type="travail", punch_entry_raw="800", punch_exit_raw="1546"),
                AiDayEntry(jour=21, heures=7.0, type="travail"),
            ],
            "reel",
        )
        par_jour = {j["jour"]: j for j in jours}
        assert par_jour[19] == {"jour": 19, "type": "travail", "heures_faites": 7.5, "debut": "03:50", "fin": "12:00"}
        assert par_jour[20]["debut"] == "08:00" and par_jour[20]["fin"] == "15:46"
        assert "debut" not in par_jour[21]

    def test_un_enregistrement_de_l_ecran_les_garde_si_le_jour_n_a_pas_change(self):
        stocke = [
            {"jour": 19, "type": "travail", "heures_faites": 7.5, "debut": "03:50", "fin": "12:00"},
            {"jour": 20, "type": "travail", "heures_faites": 7.0, "debut": "05:44", "fin": "14:00"},
            {"jour": 21, "type": "travail", "heures_faites": 7.0, "debut": "05:45"},
        ]
        ecran = [
            {"jour": 19, "type": "travail", "heures_faites": 7.5},
            {"jour": 20, "type": "travail", "heures_faites": 6.0},
            {"jour": 21, "type": "conges_payes", "heures_faites": 0},
        ]
        jours = {j["jour"]: j for j in garder_les_horaires(ecran, stocke)}
        assert jours[19]["debut"] == "03:50" and jours[19]["fin"] == "12:00"
        # Heures changées à la main, ou jour retypé : l'horaire ne décrit plus le jour.
        assert "debut" not in jours[20]
        assert "debut" not in jours[21]

    def test_update_actual_hours_ne_perd_pas_les_horaires(self):
        stocke = {"calendrier_reel": [{"jour": 19, "type": "travail", "heures_faites": 7.5, "debut": "03:50", "fin": "12:00"}]}
        ecrit = {}

        def _upsert(employee_id, company_id, year, month, actual_hours=None, **_):
            ecrit["actual"] = actual_hours

        repo = SimpleNamespace(
            get_actual_hours=lambda *a: stocke,
            get_planned_calendar=lambda *a: {"calendrier_prevu": []},
            upsert_schedule=_upsert,
        )
        with patch.object(commands, "schedule_repository", repo), patch.object(
            commands, "get_employee_company_and_statut", return_value=("societe", "Non-Cadre")
        ):
            commands.update_actual_hours(
                "salarie",
                ActualHoursRequest(
                    year=2026,
                    month=10,
                    calendrier_reel=[
                        ActualHoursEntry(jour=19, type="travail", heures_faites=7.5),
                        ActualHoursEntry(jour=20, type="travail", heures_faites=7.0),
                    ],
                ),
            )
        jours = {j["jour"]: j for j in ecrit["actual"]["calendrier_reel"]}
        assert jours[19]["debut"] == "03:50"
        assert "debut" not in jours[20] and "fin" not in jours[20]
