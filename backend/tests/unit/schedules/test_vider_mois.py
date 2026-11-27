"""Vider le calendrier d'un mois (retour d'Elsa, 27/11) : « un gros bouton rouge
pour annuler un modèle appliqué par erreur ».

Vider remet les jours à vide (prévu et réel) sans toucher aux arrêts, congés
et absences posés ni aux jours lus par un bulletin validé ; il les compte.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.schedules.application import vider_mois as service
from app.modules.schedules.domain.vider_mois import jours_lus_par_les_bulletins, plan_de_vidage


def _octobre_modele():
    """Octobre 2026 avec un modèle appliqué : 7 h prévues et faites chaque jour ouvré,
    un CP le 5, un arrêt du 12 au 14, un week-end d'arrêt non retypé le 10."""
    prevu, reel = [], []
    for j in range(1, 32):
        dow = date(2026, 10, j).weekday()
        if dow >= 5:
            prevu.append({"jour": j, "type": "weekend", "heures_prevues": 0})
            reel.append({"jour": j, "type": "weekend", "heures_faites": 0})
            continue
        prevu.append({"jour": j, "type": "travail", "heures_prevues": 7})
        reel.append({"jour": j, "type": "travail", "heures_faites": 7, "debut": "07:00"})
    prevu[4] = {"jour": 5, "type": "conges_payes", "heures_prevues": 0, "origine": "absence"}
    reel[4] = {"jour": 5, "type": "conges_payes", "heures_faites": 0}
    for j in (12, 13, 14):
        prevu[j - 1] = {"jour": j, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"}
        reel[j - 1] = {"jour": j, "type": "arret_maladie", "heures_faites": 0}
    return prevu, reel


class TestPlanDeVidage:
    def test_vide_les_jours_saisis_et_garde_les_absences(self):
        prevu, reel = _octobre_modele()
        plan = plan_de_vidage(2026, 10, prevu, reel, jours_absence_validee={10}, jours_bulletin=set())
        assert set(plan.jours_gardes_absence) == {5, 10, 12, 13, 14}
        assert 5 not in plan.jours_vides and 12 not in plan.jours_vides and 10 not in plan.jours_vides
        assert 1 in plan.jours_vides  # jeudi
        # Un samedi à 0 h est l'état par défaut : ni vidé ni compté.
        assert 3 not in plan.jours_vides
        prevu_envoye = {e["jour"]: e for e in plan.calendrier_prevu}
        assert prevu_envoye[1] == {"jour": 1, "type": "travail", "heures_prevues": None}
        assert 5 not in prevu_envoye
        reel_envoye = {e["jour"]: e for e in plan.calendrier_reel}
        assert reel_envoye[1] == {"jour": 1, "type": "travail", "heures_faites": None}
        # Les absences restent telles quelles au réel.
        assert reel_envoye[12] == {"jour": 12, "type": "arret_maladie", "heures_faites": 0}

    def test_garde_les_jours_lus_par_un_bulletin_valide(self):
        prevu, reel = _octobre_modele()
        plan = plan_de_vidage(2026, 10, prevu, reel, jours_absence_validee=set(), jours_bulletin={1, 2, 5})
        assert set(plan.jours_gardes_bulletin) == {1, 2}
        assert 1 not in plan.jours_vides
        reel_envoye = {e["jour"]: e for e in plan.calendrier_reel}
        assert reel_envoye[1]["heures_faites"] == 7

    def test_un_samedi_travaille_est_vide_en_week_end(self):
        plan = plan_de_vidage(
            2026, 10,
            [{"jour": 3, "type": "travail", "heures_prevues": 6}],
            [{"jour": 3, "type": "travail", "heures_faites": 6}],
            jours_absence_validee=set(), jours_bulletin=set(),
        )
        assert plan.calendrier_prevu == [{"jour": 3, "type": "weekend", "heures_prevues": None}]
        assert plan.calendrier_reel == [{"jour": 3, "type": "weekend", "heures_faites": None}]

    def test_un_ferie_reste_ferie_et_un_mois_vide_ne_change_rien(self):
        plan = plan_de_vidage(
            2026, 11,
            [{"jour": 11, "type": "ferie", "heures_prevues": 7}],
            [], jours_absence_validee=set(), jours_bulletin=set(),
        )
        assert plan.calendrier_prevu == [{"jour": 11, "type": "ferie", "heures_prevues": None}]
        vide = plan_de_vidage(2026, 11, [], [], jours_absence_validee=set(), jours_bulletin=set())
        assert vide.jours_vides == () and vide.calendrier_prevu == [] and vide.calendrier_reel == []

    def test_jours_lus_par_les_bulletins(self):
        # Bulletin d'octobre validé : il lit le mois civil d'octobre et sa fenêtre (21/09 → 25/10).
        fenetres = {(2026, 10): (date(2026, 9, 21), date(2026, 10, 25))}
        assert jours_lus_par_les_bulletins(2026, 9, fenetres) == set(range(21, 31))
        assert jours_lus_par_les_bulletins(2026, 10, fenetres) == set(range(1, 32))
        assert jours_lus_par_les_bulletins(2026, 11, fenetres) == set()


class TestService:
    def _snapshot(self):
        prevu, reel = _octobre_modele()
        return {"year": 2026, "month": 10, "revision": "11111111-1111-1111-1111-111111111111",
                "busy": False, "calendrier_prevu": prevu, "calendrier_reel": reel}

    def test_apercu_n_ecrit_rien(self):
        with patch.object(service.calendar_edit, "get_snapshot", return_value=self._snapshot()), \
             patch.object(service, "jours_d_absence_validee", return_value=set()), \
             patch.object(service, "jours_des_bulletins_valides", return_value=set()), \
             patch.object(service.calendar_edit, "save_calendar") as save:
            resume = service.vider_mois("sal", "soc", 2026, 10, expected_revision=None, apercu=True)
        save.assert_not_called()
        assert resume["apercu"] is True
        assert resume["jours_gardes_absence"] == [5, 12, 13, 14]
        # 22 jours ouvrés, moins 4 jours d'absence ; les week-ends à 0 h sont
        # l'état par défaut, ni vidés ni comptés.
        assert len(resume["jours_vides"]) == 18

    def test_execution_ecrit_sur_la_revision_lue(self):
        saved = {"revision": "22222222-2222-2222-2222-222222222222", "calendrier_prevu": [], "calendrier_reel": []}
        with patch.object(service.calendar_edit, "get_snapshot", return_value=self._snapshot()), \
             patch.object(service, "jours_d_absence_validee", return_value=set()), \
             patch.object(service, "jours_des_bulletins_valides", return_value={1}), \
             patch.object(service.calendar_edit, "save_calendar", return_value=saved) as save:
            resume = service.vider_mois(
                "sal", "soc", 2026, 10,
                expected_revision="11111111-1111-1111-1111-111111111111", apercu=False,
            )
        requete = save.call_args.args[2]
        assert str(requete.expected_revision) == "11111111-1111-1111-1111-111111111111"
        assert {e.jour for e in requete.calendrier_prevu} == set(resume["jours_vides"])
        assert resume["revision"] == "22222222-2222-2222-2222-222222222222"
        assert resume["jours_gardes_bulletin"] == [1]
        assert "vidés" in resume["message"]

    def test_rien_a_vider_ne_touche_pas_au_mois(self):
        snapshot = {"year": 2026, "month": 10, "revision": None, "busy": False,
                    "calendrier_prevu": [], "calendrier_reel": []}
        with patch.object(service.calendar_edit, "get_snapshot", return_value=snapshot), \
             patch.object(service, "jours_d_absence_validee", return_value=set()), \
             patch.object(service, "jours_des_bulletins_valides", return_value=set()), \
             patch.object(service.calendar_edit, "save_calendar") as save:
            resume = service.vider_mois("sal", "soc", 2026, 10, expected_revision=None, apercu=False)
        save.assert_not_called()
        assert resume["jours_vides"] == []
        assert resume["message"].startswith("Rien à vider")


class TestLectures:
    def test_jours_des_bulletins_valides_lit_les_trois_mois_voisins(self):
        lignes = [
            {"year": 2026, "month": 10, "status": "valide", "origine": "calcule"},
            {"year": 2026, "month": 9, "status": "brouillon", "origine": "calcule"},
            {"year": 2026, "month": 8, "status": "brouillon", "origine": "importe"},
        ]
        fenetres = {
            (2026, 10): SimpleNamespace(debut=date(2026, 9, 21), fin=date(2026, 10, 25)),
            # Août repris de l'ancien logiciel : figé, mais sa fenêtre ne touche pas septembre.
            (2026, 8): SimpleNamespace(debut=date(2026, 7, 21), fin=date(2026, 8, 20)),
        }
        with patch.object(service, "bulletins_du_salarie", return_value=lignes), \
             patch.object(service, "resoudre_fenetre_variables", side_effect=lambda c, a, m: fenetres[(a, m)]):
            assert service.jours_des_bulletins_valides("sal", "soc", 2026, 9) == set(range(21, 31))


class TestRoute:
    def test_la_route_existe_et_exige_le_droit_de_modifier(self):
        from app.modules.schedules.api import router as module

        routes = {r.path: r for r in module.router.routes}
        assert "/api/employees/{employee_id}/calendar/vider-mois" in routes
        appels = []
        with patch.object(module, "_require_employee_schedule_access", side_effect=lambda u, e, p: appels.append(p)), \
             patch("app.modules.schedules.application.vider_mois.vider_mois", return_value={"ok": True}) as vider:
            from app.modules.schedules.schemas.requests import ViderMoisRequest

            user = SimpleNamespace(active_company_id="soc")
            assert module.vider_mois_du_calendrier("sal", ViderMoisRequest(year=2026, month=10, apercu=True), user) == {"ok": True}
        assert appels == ["schedules.update"]
        assert vider.call_args.kwargs["apercu"] is True


class TestErreurs:
    """Relecture de L17 : une erreur de vidage est dite, jamais un 500 muet."""

    def test_lecture_impossible_donne_un_refus_lisible(self):
        import pytest

        from app.modules.schedules.application.exceptions import ScheduleAppError

        with patch.object(service.calendar_edit, "get_snapshot", return_value={"revision": None, "calendrier_prevu": [], "calendrier_reel": []}), \
             patch.object(service, "jours_d_absence_validee", side_effect=RuntimeError("base injoignable")), \
             patch.object(service.calendar_edit, "save_calendar") as save:
            with pytest.raises(ScheduleAppError) as refus:
                service.vider_mois("sal", "soc", 2026, 10, expected_revision=None, apercu=True)
        save.assert_not_called()
        assert refus.value.status_code == 503
        assert "rien n'a été vidé" in str(refus.value)

    def test_un_refus_de_l_enregistrement_passe_tel_quel(self):
        import pytest

        from app.modules.schedules.application.exceptions import ScheduleAppError

        snapshot = {"revision": "11111111-1111-1111-1111-111111111111", "calendrier_prevu": [{"jour": 1, "type": "travail", "heures_prevues": 7}], "calendrier_reel": []}
        refus_save = ScheduleAppError("calendar_busy", "Une saisie est en cours.", 409)
        with patch.object(service.calendar_edit, "get_snapshot", return_value=snapshot), \
             patch.object(service, "jours_d_absence_validee", return_value=set()), \
             patch.object(service, "jours_des_bulletins_valides", return_value=set()), \
             patch.object(service.calendar_edit, "save_calendar", side_effect=refus_save):
            with pytest.raises(ScheduleAppError) as refus:
                service.vider_mois("sal", "soc", 2026, 10, expected_revision=None, apercu=False)
        assert refus.value.status_code == 409

    def test_une_erreur_inattendue_a_l_ecriture_est_dite(self):
        import pytest

        from app.modules.schedules.application.exceptions import ScheduleAppError

        snapshot = {"revision": "11111111-1111-1111-1111-111111111111", "calendrier_prevu": [{"jour": 1, "type": "travail", "heures_prevues": 7}], "calendrier_reel": []}
        with patch.object(service.calendar_edit, "get_snapshot", return_value=snapshot), \
             patch.object(service, "jours_d_absence_validee", return_value=set()), \
             patch.object(service, "jours_des_bulletins_valides", return_value=set()), \
             patch.object(service.calendar_edit, "save_calendar", side_effect=ValueError("révision")):
            with pytest.raises(ScheduleAppError) as refus:
                service.vider_mois("sal", "soc", 2026, 10, expected_revision=None, apercu=False)
        assert refus.value.status_code == 503
