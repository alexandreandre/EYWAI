"""Arrêt arrivé après la validation du bulletin de son mois : repris par le bulletin suivant.

Retour d'Elsa du 26/11/2026 (LEWIS, salarié A : arrêt du 29/09 saisi le 26/11,
septembre déjà validé). Quadra et le cabinet de Colorplast comptent l'arrêt au
bulletin de sa période ; connu après, il passe sur le bulletin suivant à ses
vraies dates (Cartol, « Absence maladie 230726-240726 » sur août). Les deux
générateurs : heures et forfait jours.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.dsn_export.domain.evenements import _bornes_ligne_d_arret, blocs_arret
from app.modules.ijss_tracking.application import arrets as ecran
from app.modules.ijss_tracking.domain.arrets_du_mois import (
    ETAT_COMPTE_PAR_LE_BULLETIN,
    ETAT_DANS_LA_PERIODE_SUIVANTE,
    ETAT_PORTE_A_LA_MAIN,
    ETAT_PORTE_A_LA_MAIN_APRES,
    ETAT_REMIS_SANS_REPORT,
    ETAT_REPORT_A_RECALCULER,
    ETAT_REPORT_AU_PROCHAIN_CALCUL,
    ETAT_REPORTE,
    etat_du_report,
)
from app.modules.payroll.application import arrets_reportes as ar
from app.modules.payroll.application.arrets_reportes import (
    JourReporte,
    Report,
    analyser_le_report,
    appliquer_le_report_aux_evenements,
    evenements_du_report,
    heures_reprises_a_la_main,
    jours_a_reporter,
    jours_des_libelles,
    periode_precedente,
    preparer_le_report,
    sans_les_jours_deja_reportes,
)
from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.documents.arrets_reportes_bulletin import (
    appliquer_les_arrets_reportes,
    maintien_des_arrets_reportes,
    poser_la_trace,
    trace_des_arrets,
)
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import (
    _diviseur_jour_absence,
    calculer_salaire_brut_forfait,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
ARRET_ID = "arret-29-09"


def _arret(jours: list[str], cree_le: str = "2026-11-26T19:37:01+00:00", **kw) -> dict:
    return {
        "id": ARRET_ID,
        "type": "arret_maladie",
        "status": "validated",
        "selected_days": jours,
        "created_at": cree_le,
        **kw,
    }


def _reprise(lignes: list[dict], status: str = "valide") -> dict:
    """Un bulletin de septembre repris de Quadra, copié ligne à ligne."""
    return {
        "status": status,
        "year": 2026,
        "month": 9,
        "generated_at": "2026-11-08T03:09:44+00:00",
        "payslip_data": {"reprise": {"logiciel_precedent": "Quadra"}, "calcul_du_brut": lignes},
    }


def _martine(trace: dict | None, lignes: list[dict] | None = None, **kw) -> dict:
    donnees: dict = {"calcul_du_brut": lignes or []}
    if trace is not None:
        donnees["arrets_du_bulletin"] = trace
    return {"status": "valide", "generated_at": "2026-12-01T00:00:00+00:00", "payslip_data": donnees, **kw}


def _reporter(arrets, bulletins, **kw):
    return jours_a_reporter(arrets, bulletins, SEPTEMBRE, annee_origine=2026, mois_origine=9, **kw)


def _jours(liste) -> list[date]:
    return [j.jour for j in liste]


# --- Ce qu'un bulletin a compté --------------------------------------------------


def test_les_retenues_datees_de_quadra_et_de_martine_se_lisent():
    lignes = [
        {"libelle": "Absence maladie 220926-230926", "perte": 348.31},
        {"libelle": "Absence A.T. 310826", "perte": 102.41},
        {"libelle": "Absence arrêt maladie du 28/09 au 30/09", "perte": 300.0},
        {"libelle": "Absence arrêt maladie du 03/08/26 au 04/08/26 (arrêt reporté)", "perte": 1.0},
        # Un gain daté ne retient rien : il ne couvre aucun jour.
        {"libelle": "Rappel 250926", "gain": 10.0, "perte": None},
    ]
    assert jours_des_libelles(lignes, 2026, 9) == {
        date(2026, 9, 22),
        date(2026, 9, 23),
        date(2026, 8, 31),
        date(2026, 9, 28),
        date(2026, 9, 29),
        date(2026, 9, 30),
        date(2026, 8, 3),
        date(2026, 8, 4),
    }


def test_decembre_sur_un_bulletin_de_janvier_est_de_l_annee_d_avant():
    jours = jours_des_libelles([{"libelle": "Absence arrêt maladie du 31/12", "perte": 1}], 2027, 1)
    assert jours == {date(2026, 12, 31)}


# --- Le choix des jours ------------------------------------------------------------


def test_le_29_09_saisi_apres_la_validation_de_septembre_est_reporte():
    # LEWIS, salarié A : septembre repris de Quadra ne porte que de l'activité partielle.
    septembre = _reprise([{"libelle": "Act. partiel. 250926", "perte": 105.0}])
    assert _reporter([_arret(["2026-09-29"])], [septembre]) == [
        JourReporte(date(2026, 9, 29), ARRET_ID)
    ]


def test_un_jour_que_quadra_a_deja_retenu_n_est_pas_reporte():
    # Arrêt saisi tard sur une société reprise ; Quadra en avait retenu le 1 au 7.
    septembre = _reprise([{"libelle": "Absence maladie 010926-070926", "perte": 674.99}])
    jours_arret = [f"2026-09-{j:02d}" for j in range(1, 10)]
    analyse = analyser_le_report(
        [_arret(jours_arret)], [septembre], SEPTEMBRE, annee_origine=2026, mois_origine=9
    )
    assert _jours(analyse.jours) == [date(2026, 9, 8), date(2026, 9, 9)]
    assert date(2026, 9, 7) in analyse.comptes


def test_rien_tant_que_le_bulletin_d_origine_n_est_pas_valide():
    assert _reporter([_arret(["2026-09-29"])], [_reprise([], status="brouillon")]) == []
    assert _reporter([_arret(["2026-09-29"])], []) == []


def test_trace_absente_et_trace_vide_ne_disent_pas_la_meme_chose():
    # Trace vide : le bulletin a été calculé par Martine sans arrêt ce jour-là.
    assert _jours(_reporter([_arret(["2026-09-29"])], [_martine({"jours_comptes": [], "reportes": []})])) == [
        date(2026, 9, 29)
    ]
    # Trace qui porte le jour : compté.
    compte = _martine({"jours_comptes": ["2026-09-29"], "reportes": []})
    assert _reporter([_arret(["2026-09-29"])], [compte]) == []
    # Pas de trace (bulletin d'avant ce lot) : ses retenues datées font foi.
    ancien = _martine(None, [{"libelle": "Absence arrêt maladie du 29/09", "perte": 100.0}])
    assert _reporter([_arret(["2026-09-29"])], [ancien]) == []


def test_prolongation_saisie_apres_la_validation_d_un_bulletin_sans_trace():
    # Septembre calculé par Martine avant ce lot, après la création de la demande
    # (25/09, un vendredi) ; la même demande est prolongée jusqu'au 30/09 ensuite.
    ancien = _martine(
        None,
        [{"libelle": "Absence arrêt maladie du 25/09", "perte": 100.0}],
        generated_at="2026-11-30T00:00:00+00:00",
    )
    prolonge = _arret([f"2026-09-{j:02d}" for j in range(25, 31)], cree_le="2026-11-26T00:00:00+00:00")
    # Le week-end des 26-27 a eu ses IJ avec le 25 : il n'est pas repris.
    assert _jours(_reporter([prolonge], [ancien])) == [
        date(2026, 9, 28),
        date(2026, 9, 29),
        date(2026, 9, 30),
    ]


def test_pas_de_double_compte_avec_une_saisie_a_la_main():
    septembre = _reprise([])
    # Régularisation antérieure du même jour posée au planning d'octobre.
    analyse = analyser_le_report(
        [_arret(["2026-09-29"])], [septembre], SEPTEMBRE,
        annee_origine=2026, mois_origine=9, deja_portes={date(2026, 9, 29)},
    )
    assert analyse.jours == () and analyse.portes_a_la_main == {date(2026, 9, 29)}


def test_une_reprise_d_heures_a_la_main_ne_couvre_que_ses_journees():
    regul = [{"nature": "normales", "mois_origine": "2026-09", "quantite": -7.0}]
    assert heures_reprises_a_la_main(regul, 2026, 9) == 7.0
    assert heures_reprises_a_la_main([{**regul[0], "quantite": 7.0}], 2026, 9) == 0.0
    analyse = analyser_le_report(
        [_arret(["2026-09-28", "2026-09-29", "2026-09-30"])], [_reprise([])], SEPTEMBRE,
        annee_origine=2026, mois_origine=9, heures_a_la_main=7.0, heures_par_jour=7.0,
    )
    # 7 h couvrent le 28 ; les 29 et 30 sont repris, et le bulletin le dit.
    assert _jours(analyse.jours) == [date(2026, 9, 29), date(2026, 9, 30)]
    assert analyse.portes_a_la_main == {date(2026, 9, 28)}
    assert "7 h de septembre 2026 déjà reprises à la main" in analyse.alertes[0]


def test_un_arret_annule_ne_se_reporte_plus():
    assert _reporter([_arret(["2026-09-29"], status="cancelled")], [_reprise([])]) == []


def test_un_week_end_seul_ne_se_reporte_pas():
    septembre = _reprise([{"libelle": "Absence maladie 240926-250926", "perte": 200.0}])
    jours = ["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"]
    assert _reporter([_arret(jours)], [septembre]) == []


def test_la_periode_precedente_est_le_mois_civil_aux_heures_et_la_periode_au_forfait():
    assert periode_precedente(2026, 10, forfait_jours=False) == (2026, 9, SEPTEMBRE)
    assert periode_precedente(2026, 1, forfait_jours=False)[:2] == (2025, 12)
    # Avant-dernier vendredi : septembre 2026 va du 24/08 au 20/09.
    regle = {"paie_jour_de_fin": 4, "paie_occurrence": -2}
    assert periode_precedente(2026, 10, forfait_jours=True, company_data=regle) == (
        2026,
        9,
        (date(2026, 8, 24), date(2026, 9, 20)),
    )


def test_une_regle_de_periode_vide_vaut_le_mois_civil_comme_au_moteur():
    # Même résolution que le générateur du forfait (`_periode_de_paie_company`).
    vide = {"paie_jour_de_fin": None, "paie_occurrence": None}
    assert periode_precedente(2026, 10, forfait_jours=True, company_data=vide)[2] == SEPTEMBRE


def test_avec_une_trace_un_week_end_de_prolongation_se_reprend():
    # Septembre calculé quand l'arrêt allait du 21 au 25/09 (vendredi) ; prolongé
    # ensuite jusqu'au 27 : le week-end n'a rien eu, il se reprend (IJ, sans retenue).
    cal = [{"date_complete": f"2026-09-{d}", "type": "arret_maladie",
            "date_debut_arret_reel": "2026-09-21", "date_fin_arret_reel": "2026-09-25"}
           for d in (21, 22, 23, 24, 25)]
    septembre = _martine(trace_des_arrets(cal, *SEPTEMBRE))
    prolonge = _arret([f"2026-09-{d:02d}" for d in range(21, 28)])
    assert _jours(_reporter([prolonge], [septembre])) == [date(2026, 9, 26), date(2026, 9, 27)]


def test_une_absence_non_remuneree_requalifiee_n_est_pas_retenue_deux_fois():
    # Le 29/09, retenu en septembre comme absence non rémunérée, devient un arrêt.
    cal = [{"date_complete": "2026-09-29", "type": "absence_non_remuneree", "heures": 7.0}]
    septembre = _martine(trace_des_arrets(cal, *SEPTEMBRE))
    analyse = analyser_le_report([_arret(["2026-09-29"])], [septembre], SEPTEMBRE,
                                 annee_origine=2026, mois_origine=9)
    assert analyse.jours == (JourReporte(date(2026, 9, 29), ARRET_ID, sans_retenue=True),)
    assert "Absence requalifiée en arrêt le 29/09" in analyse.alertes[0]
    # Même règle sur un bulletin repris de Quadra (« Abs. Abs injustifiée 290926 »).
    repris = _reprise([{"libelle": "Abs. Abs injustifiée 290926", "perte": 105.0}])
    assert _reporter([_arret(["2026-09-29"])], [repris])[0].sans_retenue


def test_un_jour_paye_en_conge_devenu_arret_se_regularise_a_la_main():
    cal = [{"date_complete": "2026-09-29", "type": "conges_payes", "heures": 7.0}]
    septembre = _martine(trace_des_arrets(cal, *SEPTEMBRE))
    analyse = analyser_le_report([_arret(["2026-09-29"])], [septembre], SEPTEMBRE,
                                 annee_origine=2026, mois_origine=9)
    assert analyse.jours == () and analyse.a_reprendre_a_la_main == {date(2026, 9, 29)}
    assert "congé payé" in analyse.alertes[0] and "à la main" in analyse.alertes[0]


def test_une_ligne_d_arret_sans_date_lisible_ne_reporte_rien_et_le_dit():
    ancien = _martine(None, [{"libelle": "Absence arrêt maladie", "perte": 300.0, "is_arret_maladie": True}])
    analyse = analyser_le_report([_arret(["2026-09-29"])], [ancien], SEPTEMBRE,
                                 annee_origine=2026, mois_origine=9)
    assert analyse.jours == ()
    assert "sans date lisible" in analyse.alertes[0]


def test_origine_regeneree_en_brouillon_le_jour_repris_reste_reporte():
    # Septembre régénéré (forcé, en brouillon) après qu'octobre a repris le 29/09 :
    # sa trace note le jour écarté ; octobre recalculé le garde.
    cal = [{**_ARRET_29, "date_complete": "2026-09-29"}]
    trace = trace_des_arrets(cal, *SEPTEMBRE, frozenset({date(2026, 9, 29)}))
    assert trace["jours_repris_par_le_suivant"] == ["2026-09-29"]
    brouillon = {"status": "brouillon", "payslip_data": {"arrets_du_bulletin": trace}}
    assert _jours(_reporter([_arret(["2026-09-29", "2026-09-30"])], [brouillon])) == [date(2026, 9, 29)]


# --- Les événements -------------------------------------------------------------------

_ARRET_29 = {
    "jour": 29, "type": "arret_maladie", "heures": 0.0, "arret_type": "maladie_simple",
    "subrogation_active": True,
    "date_debut_arret_reel": "2026-09-28", "date_fin_arret_reel": "2026-09-30",
}


def test_les_evenements_reportes_gardent_leur_date_et_le_disent():
    analyse_septembre = [{"jour": 25, "type": "travail_base", "heures": 7.0}, _ARRET_29]
    evs = evenements_du_report(analyse_septembre, [JourReporte(date(2026, 9, 29), ARRET_ID)], 2026, 9)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["date_complete"] == "2026-09-29"
    assert ev["is_regularisation_anterieure"] and ev["arret_reporte"]
    assert ev["absence_id"] == ARRET_ID
    assert (ev["annee"], ev["mois"], ev["jour"]) == (2026, 9, 29)


def test_un_ferie_compris_dans_l_arret_reporte_le_suit():
    # Arrêt du 10 au 12/11 saisi tard, le 11 novembre férié au milieu.
    analyse = [
        {**_ARRET_29, "jour": 10, "date_debut_arret_reel": "2026-11-10", "date_fin_arret_reel": "2026-11-12"},
        {"jour": 11, "type": "ferie", "heures": 7.0},
        {**_ARRET_29, "jour": 12, "date_debut_arret_reel": "2026-11-10", "date_fin_arret_reel": "2026-11-12"},
    ]
    jours = [JourReporte(date(2026, 11, j), ARRET_ID) for j in (10, 11, 12)]
    evs = evenements_du_report(analyse, jours, 2026, 11)
    assert [e["date_complete"] for e in evs] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    ferie = evs[1]
    assert ferie["type"] == "arret_maladie" and ferie["heures"] == 0.0
    assert ferie["arret_type"] == "maladie_simple" and ferie["ferie_dans_l_arret"]


def test_le_bulletin_d_origine_regenere_ne_recompte_pas_le_jour_repris():
    evs = [
        {"jour": 29, "type": "arret_maladie", "heures": 0.0},
        {"jour": 30, "type": "travail_base", "heures": 7.0},
    ]
    restants = sans_les_jours_deja_reportes(evs, {date(2026, 9, 29)}, 2026, 9)
    assert [e["jour"] for e in restants] == [30]


def test_regeneration_de_l_origine_l_arret_reste_sur_le_bulletin_suivant():
    # Octobre a repris le 29/09 ; septembre est ensuite régénéré (forcé).
    repris = Report(repris=frozenset({date(2026, 9, 29)}))
    cal = appliquer_le_report_aux_evenements(
        [{**_ARRET_29, "date_complete": "2026-09-29"}], [], repris, 2026, 9
    )
    assert cal == []  # septembre ne recompte pas le jour repris
    bulletin: dict = {}
    poser_la_trace(bulletin, [{**_ARRET_29, "date_complete": "2026-09-29"}], *SEPTEMBRE, repris.vers_les_saisies())
    assert "2026-09-29" not in bulletin["arrets_du_bulletin"]["jours_comptes"]
    # Octobre recalculé ensuite : la trace de septembre ne porte pas le 29, il reste reporté.
    septembre = {"status": "valide", "payslip_data": bulletin}
    assert _jours(_reporter([_arret(["2026-09-29"])], [septembre])) == [date(2026, 9, 29)]


def test_la_trace_dit_les_jours_traites_et_les_jours_repris():
    cal = [
        {"date_complete": "2026-10-15", "type": "arret_maladie",
         "date_debut_arret_reel": "2026-10-15", "date_fin_arret_reel": "2026-10-18"},
        _evenement_reporte(7.0),
    ]
    trace = trace_des_arrets(cal, date(2026, 10, 1), date(2026, 10, 31))
    assert trace["jours_comptes"] == ["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
    assert trace["reportes"] == [{"date": "2026-09-29", "absence_id": ARRET_ID, "sans_retenue": False}]
    # Les jours repris sont ceux que le contrat du bulletin couvre (D3).
    nouveau = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0, date_entree="2026-10-01")
    assert trace_des_arrets(cal, date(2026, 10, 1), date(2026, 10, 31), contexte=nouveau)["reportes"] == []
    # Sans arrêt, la trace est posée vide : « rien compté ».
    vide: dict = {}
    poser_la_trace(vide, [], date(2026, 10, 1), date(2026, 10, 31))
    assert vide["arrets_du_bulletin"] == {
        "jours_comptes": [], "jours_retenus": {}, "jours_repris_par_le_suivant": [], "reportes": []}


# --- La préparation, lue en base -----------------------------------------------------


class _Requete:
    def __init__(self, donnees, table):
        self._donnees, self._table, self._filtres, self._un = donnees, table, {}, False

    def select(self, *_):
        return self

    def eq(self, cle, valeur):
        self._filtres[cle] = valeur
        return self

    def maybe_single(self):
        self._un = True
        return self

    def execute(self):
        if self._table == "boom":
            raise RuntimeError("base indisponible")
        lignes = [
            l for l in self._donnees.get(self._table, [])
            if all(l.get(k, v) == v for k, v in self._filtres.items())
        ]

        class R:
            data = (lignes[0] if lignes else None) if self._un else lignes

        return R()


class _Client:
    def __init__(self, donnees, casse=False):
        self.donnees, self.casse = donnees, casse

    def table(self, nom):
        return _Requete(self.donnees, "boom" if self.casse else nom)


def test_preparer_le_report_aux_heures_lit_l_arret_et_le_bulletin_d_origine():
    client = _Client({
        "absence_requests": [{**_arret(["2026-09-29"]), "employee_id": "A"}],
        "payslips": [{**_reprise([]), "employee_id": "A"}],
    })
    report = preparer_le_report(client, "A", 2026, 10, forfait_jours=False, company_data={})
    assert _jours(report.jours) == [date(2026, 9, 29)] and report.planning == {}
    assert Report.depuis_les_saisies(report.vers_les_saisies()) == report


def test_preparer_le_report_au_forfait_lit_le_planning_du_mois_d_avant_la_periode():
    # Période de septembre au forfait : du 24/08 au 20/09. Arrêt du 25/08 saisi tard.
    client = _Client({
        "absence_requests": [{**_arret(["2026-08-25"]), "employee_id": "A"}],
        "payslips": [{**_reprise([]), "employee_id": "A"}],
        "employee_schedules": [{
            "employee_id": "A", "year": 2026, "month": 8,
            "planned_calendar": {
                "calendrier_prevu": [{"jour": 25, "type": "arret_maladie", "arret_type": "maladie_simple"}],
                # Le forfait n'applique pas les régularisations antérieures : non lues.
                "regularisations_anterieures": [{"type": "arret_maladie", "date_complete": "2026-08-25"}],
            },
        }],
    })
    report = preparer_le_report(
        client, "A", 2026, 10, forfait_jours=True,
        company_data={"paie_jour_de_fin": 4, "paie_occurrence": -2},
        planned_calendar_du_mois={"regularisations_anterieures": [
            {"type": "arret_maladie", "date_complete": "2026-08-25"}]},
    )
    assert _jours(report.jours) == [date(2026, 8, 25)]
    assert report.planning["2026-08-25"]["arret_type"] == "maladie_simple"
    evs = appliquer_le_report_aux_evenements([], [], report, 2026, 10)
    assert [e["date_complete"] for e in evs] == ["2026-08-25"]


def test_une_lecture_en_echec_ne_bloque_pas_le_bulletin_et_le_dit():
    report = preparer_le_report(_Client({}, casse=True), "A", 2026, 10, forfait_jours=False, company_data={})
    assert report.jours == () and report.alertes == (ar.MESSAGE_REPORT_ILLISIBLE,)


# --- Le bulletin d'octobre : retenue aux deux générateurs ------------------------------


def _evenement_reporte(heures: float, jour: int = 29, arret_type: str = "maladie_simple") -> dict:
    return {
        "date_complete": f"2026-09-{jour:02d}",
        "annee": 2026,
        "mois": 9,
        "jour": jour,
        "type": "arret_maladie",
        "heures": heures,
        "arret_type": arret_type,
        "subrogation_active": True,
        "date_debut_arret_reel": f"2026-09-{jour:02d}",
        "date_fin_arret_reel": f"2026-09-{jour:02d}",
        "is_regularisation_anterieure": True,
        "arret_reporte": True,
        "absence_id": ARRET_ID,
    }


def _octobre_travaille(heures: float) -> list[dict]:
    return [
        {"date_complete": f"2026-10-{j:02d}", "type": "travail_base", "heures": heures}
        for j in range(1, 32)
        if date(2026, 10, j).weekday() < 5
    ]


def test_heures_la_retenue_du_29_09_est_sur_octobre_a_sa_date():
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    cal = _octobre_travaille(7.0) + [_evenement_reporte(7.0)]
    res = calculer_salaire_brut(ctx, cal, date(2026, 10, 1), date(2026, 10, 31))
    lignes = [l for l in res["lignes_composants_brut"] if "arrêt reporté" in str(l.get("libelle"))]
    assert [l["libelle"] for l in lignes] == ["Absence arrêt maladie du 29/09/26 (arrêt reporté)"]
    sans = calculer_salaire_brut(ctx, _octobre_travaille(7.0), date(2026, 10, 1), date(2026, 10, 31))
    assert res["salaire_brut_total"] == pytest.approx(sans["salaire_brut_total"] - lignes[0]["perte"], abs=0.01)


def test_heures_39h_le_jour_reporte_retire_sa_part_d_heures_sup_structurelles():
    # Comme Quadra chez Comitech (juillet 2026, 29-30/06 sur juillet) : la
    # journée reportée vaut la même retenue qu'un jour d'arrêt du mois.
    ctx = build_test_contexte(salaire_base=2275.0 * 39 / 35, duree_hebdo=39.0)
    base = calculer_salaire_brut(ctx, _octobre_travaille(7.8), date(2026, 10, 1), date(2026, 10, 31))
    reporte = calculer_salaire_brut(
        ctx, _octobre_travaille(7.8) + [_evenement_reporte(0.0)], date(2026, 10, 1), date(2026, 10, 31)
    )
    du_mois = [e for e in _octobre_travaille(7.8) if e["date_complete"] != "2026-10-29"] + [
        {"date_complete": "2026-10-29", "type": "arret_maladie", "heures": 0.0, "arret_type": "maladie_simple"}
    ]
    mois = calculer_salaire_brut(ctx, du_mois, date(2026, 10, 1), date(2026, 10, 31))
    assert base["salaire_brut_total"] - reporte["salaire_brut_total"] == pytest.approx(
        base["salaire_brut_total"] - mois["salaire_brut_total"], abs=0.01
    )
    assert any(l.get("is_reduction_hs") for l in reporte["lignes_composants_brut"])


def test_heures_un_ferie_dans_l_arret_reporte_est_retenu():
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    analyse = [{**_ARRET_29, "jour": d, "date_debut_arret_reel": "2026-11-10",
                "date_fin_arret_reel": "2026-11-12"} for d in (10, 12)] + [
        {"jour": 11, "type": "ferie", "heures": 7.0}]
    evs = evenements_du_report(analyse, [JourReporte(date(2026, 11, d), ARRET_ID) for d in (10, 11, 12)], 2026, 11)
    decembre = [
        {"date_complete": f"2026-12-{j:02d}", "type": "travail_base", "heures": 7.0}
        for j in range(1, 32) if date(2026, 12, j).weekday() < 5
    ]
    res = calculer_salaire_brut(ctx, decembre + evs, date(2026, 12, 1), date(2026, 12, 31))
    ligne = next(l for l in res["lignes_composants_brut"] if "arrêt reporté" in str(l.get("libelle")))
    assert ligne["libelle"] == "Absence arrêt maladie du 10/11/26 au 12/11/26 (arrêt reporté)"
    assert ligne["quantite"] == 21.0


def test_un_jour_reporte_d_avant_le_contrat_n_est_ni_retenu_ni_maintenu():
    # Deux contrats : le 29/09 appartient au contrat d'avant, le nouveau commence le 01/10.
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0, date_entree="2026-10-01")
    res = calculer_salaire_brut(
        ctx, _octobre_travaille(7.0) + [_evenement_reporte(7.0)], date(2026, 10, 1), date(2026, 10, 31)
    )
    assert not any("arrêt reporté" in str(l.get("libelle")) for l in res["lignes_composants_brut"])
    assert maintien_des_arrets_reportes(
        [_evenement_reporte(7.0)], ctx, company_id="societe", employee_id=None,
        year=2026, month=10, saisie_du_mois={}, avec_arret_du_mois=False,
    ) == []
    forfait = build_test_contexte(statut="Cadre", salaire_base=3831.39, date_entree="2026-09-21",
                                  specificites_extra={"is_forfait_jour": True})
    res_f = calculer_salaire_brut_forfait(forfait, [_evenement_reporte(0.0, jour=18)],
                                          date(2026, 9, 21), date(2026, 10, 25), [])
    assert not any(l.get("arret_reporte") for l in res_f["lignes_composants_brut"])


def test_forfait_jours_la_retenue_du_jour_reporte_est_sur_octobre_a_sa_date():
    # Au forfait, la période d'octobre va du 21/09 au 25/10 : le jour reporté
    # vient de celle de septembre (24/08 au 20/09), ici le vendredi 18/09.
    ctx = build_test_contexte(statut="Cadre", salaire_base=3831.39,
                              specificites_extra={"is_forfait_jour": True})
    res = calculer_salaire_brut_forfait(ctx, [_evenement_reporte(0.0, jour=18)],
                                        date(2026, 9, 21), date(2026, 10, 25), [])
    lignes = [l for l in res["lignes_composants_brut"] if l.get("arret_reporte")]
    assert [l["libelle"] for l in lignes] == ["Absence arrêt maladie du 18/09/26 (arrêt reporté)"]
    journee = round(3831.39 / _diviseur_jour_absence(ctx), 2)
    assert lignes[0]["perte"] == pytest.approx(journee, abs=0.01)
    assert res["salaire_brut_total"] == pytest.approx(3831.39 - journee, abs=0.02)
    assert res["retenues_absence_mois"] == pytest.approx(journee, abs=0.01)


def test_forfait_un_mois_entier_absent_garde_la_retenue_du_jour_reporte():
    # Octobre entier sans solde (ou en congé parental) : le mois vaut zéro, et
    # la journée du 18/09 reportée se retient en plus, elle n'est pas absorbée.
    ctx = build_test_contexte(statut="Cadre", salaire_base=3831.39,
                              specificites_extra={"is_forfait_jour": True})
    debut, fin = date(2026, 9, 21), date(2026, 10, 25)
    absent = [
        {"date_complete": (debut + timedelta(days=k)).isoformat(), "type": "absence_non_remuneree", "heures": 0.0}
        for k in range((fin - debut).days + 1)
        if (debut + timedelta(days=k)).weekday() < 5
    ]
    seul = calculer_salaire_brut_forfait(ctx, absent, debut, fin, [])
    avec = calculer_salaire_brut_forfait(ctx, absent + [_evenement_reporte(0.0, jour=18)], debut, fin, [])
    journee = round(3831.39 / _diviseur_jour_absence(ctx), 2)
    assert seul["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)
    assert avec["salaire_brut_total"] == pytest.approx(-journee, abs=0.02)


def test_heures_un_mois_entier_absent_garde_la_retenue_du_jour_reporte():
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    absent = [
        {"date_complete": f"2026-10-{j:02d}", "type": "absence_non_remuneree", "heures": 7.0}
        for j in range(1, 32)
        if date(2026, 10, j).weekday() < 5
    ]
    octobre = (date(2026, 10, 1), date(2026, 10, 31))
    seul = calculer_salaire_brut(ctx, absent, *octobre, nb_jours_travail_planifies=0)
    avec = calculer_salaire_brut(ctx, absent + [_evenement_reporte(7.0)], *octobre, nb_jours_travail_planifies=0)
    assert seul["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)
    assert avec["salaire_brut_total"] < -100


def test_heures_39h_mois_entier_en_arret_la_part_d_hs_reportee_n_est_pas_absorbee():
    ctx = build_test_contexte(salaire_base=2275.0 * 39 / 35, duree_hebdo=39.0)
    octobre = (date(2026, 10, 1), date(2026, 10, 31))
    arret_du_mois = [
        {"date_complete": f"2026-10-{j:02d}", "type": "arret_maladie", "heures": 7.8,
         "arret_type": "maladie_simple", "date_debut_arret_reel": "2026-09-28",
         "date_fin_arret_reel": "2026-10-31"}
        for j in range(1, 32) if date(2026, 10, j).weekday() < 5
    ]
    reportes = [_evenement_reporte(0.0, jour=j) for j in (28, 29, 30)]
    seul = calculer_salaire_brut(ctx, arret_du_mois, *octobre, nb_jours_travail_planifies=0)
    avec = calculer_salaire_brut(ctx, arret_du_mois + reportes, *octobre, nb_jours_travail_planifies=0)
    travail = _octobre_travaille(7.8)
    reference = calculer_salaire_brut(ctx, travail, *octobre)["salaire_brut_total"] - calculer_salaire_brut(
        ctx, travail + reportes, *octobre)["salaire_brut_total"]
    assert seul["salaire_brut_total"] - avec["salaire_brut_total"] == pytest.approx(reference, abs=0.02)


def test_un_jour_requalifie_n_a_pas_de_seconde_retenue_aux_deux_generateurs():
    sans = {**_evenement_reporte(7.0), "sans_retenue": True}
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    res = calculer_salaire_brut(ctx, _octobre_travaille(7.0) + [sans], date(2026, 10, 1), date(2026, 10, 31))
    assert not any("arrêt reporté" in str(l.get("libelle")) for l in res["lignes_composants_brut"])
    forfait = build_test_contexte(statut="Cadre", salaire_base=3831.39, specificites_extra={"is_forfait_jour": True})
    res_f = calculer_salaire_brut_forfait(forfait, [{**_evenement_reporte(0.0, jour=18), "sans_retenue": True}],
                                          date(2026, 9, 21), date(2026, 10, 25), [])
    assert res_f["salaire_brut_total"] == pytest.approx(3831.39, abs=0.01)


def test_forfait_toute_la_periode_reportee_vaut_le_salaire_comme_aux_heures():
    forfait = build_test_contexte(statut="Cadre", salaire_base=3831.39, specificites_extra={"is_forfait_jour": True})
    aout = [
        {**_evenement_reporte(0.0, jour=j), "date_complete": f"2026-08-{j:02d}", "mois": 8}
        for j in range(1, 32) if date(2026, 8, j).weekday() < 5
    ]
    res = calculer_salaire_brut_forfait(forfait, aout, date(2026, 9, 21), date(2026, 10, 25), [])
    assert res["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    septembre = [_evenement_reporte(7.0, jour=j) for j in range(1, 31) if date(2026, 9, j).weekday() < 5]
    base = calculer_salaire_brut(ctx, _octobre_travaille(7.0), date(2026, 10, 1), date(2026, 10, 31))
    tout = calculer_salaire_brut(ctx, _octobre_travaille(7.0) + septembre, date(2026, 10, 1), date(2026, 10, 31))
    assert base["salaire_brut_total"] - tout["salaire_brut_total"] == pytest.approx(2275.0, abs=0.02)


def test_une_regularisation_manuelle_garde_son_libelle_sans_arret_reporte():
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    manuelle = {k: v for k, v in _evenement_reporte(7.0).items() if k not in ("arret_reporte", "absence_id")}
    res = calculer_salaire_brut(ctx, _octobre_travaille(7.0) + [manuelle], date(2026, 10, 1), date(2026, 10, 31))
    assert any(l.get("libelle") == "Absence arrêt maladie du 29/09" for l in res["lignes_composants_brut"])


# --- Maintien et IJ des jours reportés -------------------------------------------------

REGLAGES = {"apply_legal_maintenance": True}


class _Reglages:
    def model_dump(self, mode="json"):
        return dict(REGLAGES)


@pytest.fixture
def sans_base(monkeypatch):
    import app.modules.payroll.infrastructure.salaires_de_reference as salaires
    from app.modules.maintenance_settings.application import queries

    appels = []
    monkeypatch.setattr(queries, "get_maintenance_settings", lambda company_id: _Reglages())
    monkeypatch.setattr(salaires, "poser_salaires_de_reference", lambda arret, eid: None)
    monkeypatch.setattr(
        payslip_run_heures, "poser_les_arrets_connus",
        lambda arret, *a: appels.append(arret) or arret.setdefault("arrets_connus", []),
    )
    return appels


def _contexte(forfait: bool):
    if forfait:
        ctx = build_test_contexte(statut="Cadre", salaire_base=3831.39, date_entree="2015-01-01",
                                  specificites_extra={"is_forfait_jour": True})
        ctx.contrat["contrat"]["is_forfait_jour"] = True
        return ctx
    return build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0, date_entree="2015-01-01")


@pytest.mark.parametrize("forfait", [False, True], ids=["heures", "forfait_jours"])
def test_le_maintien_du_jour_reporte_porte_sur_ce_seul_jour(sans_base, monkeypatch, forfait):
    from app.modules.payroll.engine import maintien_salaire_service as mss

    appels = []
    vrai = mss.calculer_maintien
    monkeypatch.setattr(
        mss, "calculer_maintien",
        lambda arret, c, s, d, f, **kw: appels.append((arret, d, f)) or vrai(arret, c, s, d, f, **kw),
    )
    # Accident du travail : pas de carence employeur, le maintien est versé.
    ev = _evenement_reporte(0.0 if forfait else 7.0, arret_type="accident_travail")
    blocs = maintien_des_arrets_reportes(
        [ev], _contexte(forfait), company_id="societe", employee_id="A",
        year=2026, month=10, saisie_du_mois={}, avec_arret_du_mois=False,
    )
    assert len(blocs) == 1 and blocs[0].absence_id == ARRET_ID
    arret, debut, fin = appels[0]
    assert (debut, fin) == (date(2026, 9, 29), date(2026, 9, 29))
    assert arret["mois_entier_en_arret"] is False
    assert arret["date_debut"] == "2026-09-29"  # vrai début : carence et rang de jour
    assert sans_base, "la chaîne des arrêts connus est posée, comme pour l'arrêt du mois"
    verse = blocs[0].resultat["maintien"]["maintien_verse"]
    assert 0 < verse < (3831.39 if forfait else 2275.0) / 10


def test_des_ij_saisies_pour_le_mois_ne_s_additionnent_jamais_a_une_estimation(sans_base):
    ev = _evenement_reporte(7.0, arret_type="accident_travail")
    avec = maintien_des_arrets_reportes(
        [ev], _contexte(False), company_id="societe", employee_id="A", year=2026, month=10,
        saisie_du_mois={"ijss_brut_override": 50.0}, avec_arret_du_mois=True,
    )
    assert avec[0].resultat["ijss"]["ijss_theorique"] == 0.0
    assert any("IJ de l'arrêt reporté" in a for a in avec[0].resultat.get("alertes") or [])
    # Sans arrêt du mois, la saisie est celle de l'arrêt reporté : elle n'est pas ignorée.
    seul = maintien_des_arrets_reportes(
        [ev], _contexte(False), company_id="societe", employee_id="A", year=2026, month=10,
        saisie_du_mois={"ijss_brut_override": 50.0}, avec_arret_du_mois=False,
    )
    assert seul[0].resultat["ijss"]["ijss_theorique"] == pytest.approx(50.0)


def test_ij_saisies_sans_arret_du_mois_vont_au_premier_arrete_reporte_seulement(sans_base):
    premier = {**_evenement_reporte(7.0, jour=8, arret_type="accident_travail"), "absence_id": "premier"}
    second = {**_evenement_reporte(7.0, jour=29, arret_type="accident_travail"), "absence_id": "second"}
    blocs = maintien_des_arrets_reportes(
        [premier, second], _contexte(False), company_id="societe", employee_id="A", year=2026, month=10,
        saisie_du_mois={"ijss_brut_override": 50.0}, avec_arret_du_mois=False,
    )
    assert [b.absence_id for b in blocs] == ["premier", "second"]
    assert blocs[0].resultat["ijss"]["ijss_theorique"] == pytest.approx(50.0)
    assert blocs[1].resultat["ijss"]["ijss_theorique"] == 0.0
    alertes = blocs[1].resultat.get("alertes") or []
    assert "celui de l'arrêt reporté du 08/09/26" in alertes[-1]


def test_le_maintien_reporte_suit_la_vraie_chaine_de_prolongation(monkeypatch):
    # Le 29/09 prolonge un arrêt du 21 au 28/09 connu aux calendriers : pas de
    # nouvelle carence, l'IJ du jour est due. Seul, il serait en carence.
    import app.modules.payroll.infrastructure.salaires_de_reference as salaires
    from app.modules.maintenance_settings.application import queries

    monkeypatch.setattr(queries, "get_maintenance_settings", lambda company_id: _Reglages())
    monkeypatch.setattr(salaires, "poser_salaires_de_reference", lambda arret, eid: None)

    def ij_du_29(connus):
        monkeypatch.setattr(payslip_run_heures, "arrets_connus_du_salarie", lambda eid, a, m: connus)
        blocs = maintien_des_arrets_reportes(
            [_evenement_reporte(7.0)], _contexte(False), company_id="societe", employee_id="A",
            year=2026, month=10, saisie_du_mois={}, avec_arret_du_mois=False,
        )
        return blocs[0].resultat["ijss"]["ijss_theorique"]

    assert ij_du_29([]) == 0.0
    assert ij_du_29([{"debut": "2026-09-21", "fin": "2026-09-28", "type": "maladie_simple"}]) > 0


def test_parcours_forfait_jusqu_aux_lignes_et_a_la_trace(sans_base):
    # Le générateur du forfait passe le report par les saisies ; le moteur tire
    # les jours du planning, retient la journée, verse maintien et IJ, trace.
    report = Report(
        jours=(JourReporte(date(2026, 9, 18), ARRET_ID),),
        planning={"2026-09-18": {"jour": 18, "type": "arret_maladie", "arret_type": "accident_travail",
                                 "subrogation_active": True, "date_debut_arret_reel": "2026-09-18",
                                 "date_fin_arret_reel": "2026-09-18"}},
    )
    saisie = report.vers_les_saisies()
    ctx = _contexte(True)
    cal = appliquer_le_report_aux_evenements([], [], Report.depuis_les_saisies(saisie), 2026, 10)
    res = calculer_salaire_brut_forfait(ctx, cal, date(2026, 9, 21), date(2026, 10, 25), [])
    details = list(res["lignes_composants_brut"])
    ij_du_mois = [{"prime_id": "ijss_subrogees", "libelle": "IJSS subrogées", "montant": 40.0}]
    effet = appliquer_les_arrets_reportes(
        ctx, cal, details, [{"libelle": "CSG déductible IJSS", "base": 40.0}], ij_du_mois,
        company_id="societe", employee_id="A", year=2026, month=10,
        saisie_du_mois=saisie, avec_arret_du_mois=True,
    )
    assert effet.maintien_verse > 0 and effet.brut_modifie
    maintien = [l for l in details if l.get("arret_reporte") and l.get("gain")]
    assert maintien[0]["libelle"] == "Maintien de salaire employeur (arrêt reporté du 18/09/26)"
    reportees = [l for l in effet.ijss_imposables if l["prime_id"] == "ijss_subrogees_arret_reporte"]
    ij = sum(l["montant"] for l in reportees)
    # Une seule CSG des IJ, sur le total du bulletin.
    assert [l["base"] for l in effet.lignes_csg_ijss] == [round(40.0 + ij, 2)] * len(effet.lignes_csg_ijss)
    bulletin: dict = {}
    poser_la_trace(bulletin, cal, date(2026, 9, 21), date(2026, 10, 25), saisie, effet.blocs)
    assert bulletin["arrets_du_bulletin"]["reportes"] == [
        {"date": "2026-09-18", "absence_id": ARRET_ID, "sans_retenue": False}]
    assert bulletin["arrets_reportes"][0]["absence_id"] == ARRET_ID


_AT = {"arret_type": "accident_travail", "subrogation_active": True}


def _jour_d_arret(jour: date, debut: str, fin: str, type_ev: str = "arret_maladie") -> dict:
    return {"date_complete": jour.isoformat(), "type": type_ev, "heures": 7.0 if type_ev.startswith("arret") else 0.0,
            "date_debut_arret_reel": debut, "date_fin_arret_reel": fin, **_AT}


def _maintien_de(cal, ctx, debut, fin):
    from app.modules.payroll.documents.payslip_run_heures import _extraire_arret_pour_maintien
    from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

    arret = _extraire_arret_pour_maintien(cal, ctx, debut, fin)
    return arret and calculer_maintien(arret, ctx, dict(REGLAGES), debut, fin)


def test_origine_regeneree_ne_paie_plus_le_maintien_ni_les_ij_des_jours_repris(sans_base):
    # AT du vendredi 25 au lundi 28/09 ; octobre a repris le 25 et le 28. Septembre
    # régénéré : plus rien de cet arrêt, week-end compris (ses IJ étaient en double).
    cal = [_jour_d_arret(date(2026, 9, d), "2026-09-25", "2026-09-28",
                         "arret_maladie" if date(2026, 9, d).weekday() < 5 else "weekend") for d in (25, 26, 27, 28)]
    reste = sans_les_jours_deja_reportes(cal, {date(2026, 9, 25), date(2026, 9, 28)}, 2026, 9)
    assert reste == []
    assert _maintien_de(reste, _contexte(False), *SEPTEMBRE) is None


def test_origine_regeneree_l_arret_s_arrete_au_dernier_jour_garde(sans_base):
    # AT du 21 au 30/09 ; octobre a repris la prolongation du 28 au 30. Septembre
    # régénéré garde le 21 au 25, avec le même début (carence, rang).
    cal = [_jour_d_arret(date(2026, 9, d), "2026-09-21", "2026-09-30",
                         "arret_maladie" if date(2026, 9, d).weekday() < 5 else "weekend") for d in range(21, 31)]
    repris = {date(2026, 9, d) for d in (26, 27, 28, 29, 30)}
    reste = sans_les_jours_deja_reportes(cal, repris, 2026, 9)
    assert [e["date_complete"][-2:] for e in reste] == ["21", "22", "23", "24", "25"]
    assert {e["date_fin_arret_reel"] for e in reste} == {"2026-09-25"}
    garde = _maintien_de(reste, _contexte(False), *SEPTEMBRE)
    tout = _maintien_de(cal, _contexte(False), *SEPTEMBRE)
    assert garde["ijss"]["nb_jours_indemnises"] < tout["ijss"]["nb_jours_indemnises"]


def test_les_week_ends_d_un_arret_reporte_ont_leurs_ij(sans_base):
    # AT du lundi 14 au dimanche 27/09 reporté en entier : 14 jours d'IJ, pas 12.
    analyse = [_jour_d_arret(date(2026, 9, d), "2026-09-14", "2026-09-27")
               for d in range(14, 28) if date(2026, 9, d).weekday() < 5]
    jours = [JourReporte(date(2026, 9, d), ARRET_ID) for d in range(14, 28)]
    evs = evenements_du_report(analyse, jours, 2026, 9)
    assert [e["date_complete"][-2:] for e in evs] == [f"{d}" for d in range(14, 28)]
    assert {e["type"] for e in evs if date.fromisoformat(e["date_complete"]).weekday() >= 5} == {"repos"}
    blocs = maintien_des_arrets_reportes(evs, _contexte(False), company_id="societe", employee_id="A",
                                         year=2026, month=10, saisie_du_mois={}, avec_arret_du_mois=False)
    assert blocs[0].resultat["ijss"]["nb_jours_indemnises"] == 14
    # Le week-end ne se retient pas : 10 journées.
    ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    res = calculer_salaire_brut(ctx, _octobre_travaille(7.0) + evs, date(2026, 10, 1), date(2026, 10, 31))
    ligne = next(l for l in res["lignes_composants_brut"] if "arrêt reporté" in str(l.get("libelle")))
    assert ligne["quantite"] == 70.0


def test_une_prolongation_du_seul_week_end_est_payee_et_tracee(sans_base):
    analyse = [_jour_d_arret(date(2026, 9, d), "2026-09-21", "2026-09-27") for d in range(21, 26)]
    jours = [JourReporte(date(2026, 9, d), ARRET_ID) for d in (26, 27)]
    evs = evenements_du_report(analyse, jours, 2026, 9)
    assert [e["date_complete"] for e in evs] == ["2026-09-26", "2026-09-27"]
    blocs = maintien_des_arrets_reportes(evs, _contexte(False), company_id="societe", employee_id="A",
                                         year=2026, month=10, saisie_du_mois={}, avec_arret_du_mois=False)
    assert blocs and blocs[0].resultat["ijss"]["nb_jours_indemnises"] == 2
    trace = trace_des_arrets(evs, date(2026, 10, 1), date(2026, 10, 31))
    assert [r["date"] for r in trace["reportes"]] == ["2026-09-26", "2026-09-27"]


def test_forfait_periode_non_civile_entierement_reportee_maintien_sur_la_periode(sans_base, monkeypatch):
    # Période de septembre au forfait : du 24/08 au 20/09. Toute reportée sur octobre.
    import app.modules.payroll.engine.period_forfait as pf
    from app.modules.payroll.engine import maintien_salaire_service as mss

    monkeypatch.setattr(pf, "definir_periode_de_paie",
                        lambda c, a, m: (date(2026, 8, 24), date(2026, 9, 20)) if m == 9 else (date(2026, 9, 21), date(2026, 10, 25)))
    appels = []
    vrai = mss.calculer_maintien
    monkeypatch.setattr(mss, "calculer_maintien",
                        lambda a, c, st, d, f, **kw: appels.append((a, d, f)) or vrai(a, c, st, d, f, **kw))
    ctx = _contexte(True)
    jours = [date(2026, 8, 24) + timedelta(days=k) for k in range(28)]
    evs = [{**_jour_d_arret(d, "2026-08-24", "2026-09-20", "arret_maladie" if d.weekday() < 5 else "repos"),
            "heures": 0.0, "annee": d.year, "mois": d.month, "jour": d.day,
            "is_regularisation_anterieure": True, "arret_reporte": True, "absence_id": ARRET_ID} for d in jours]
    res = calculer_salaire_brut_forfait(ctx, evs, date(2026, 9, 21), date(2026, 10, 25), [])
    retenue = sum((l.get("perte") or 0) - (l.get("gain") or 0) for l in res["lignes_composants_brut"] if l.get("arret_reporte"))
    assert retenue == pytest.approx(3831.39, abs=0.01)
    blocs = maintien_des_arrets_reportes(evs, ctx, company_id="societe", employee_id="A", year=2026, month=10,
                                         saisie_du_mois={}, avec_arret_du_mois=False)
    arret, debut, fin = appels[-1]
    assert (debut, fin) == (date(2026, 8, 24), date(2026, 9, 20)) and arret["mois_entier_en_arret"] is True
    assert blocs[0].resultat["maintien"]["maintien_verse"] > 0


def test_un_mot_d_arret_l_emporte_sur_non_paye_ou_conge():
    from app.modules.payroll.application.arrets_reportes import nature_du_libelle

    assert nature_du_libelle("Congé maternité 010326-310326") == "arret"
    assert nature_du_libelle("Abs. maternité non payée 010326") == "arret"
    assert nature_du_libelle("Abs. Abs injustifiée 290926") == "sans_solde"
    assert nature_du_libelle("Abs. Enfant malade 020226") == "autre"


def test_l_origine_regeneree_signale_un_jour_repris_sans_retenue():
    client = _Client({
        "absence_requests": [{**_arret(["2026-09-29"]), "employee_id": "A"}],
        "payslips": [
            {**_reprise([]), "employee_id": "A"},
            {"employee_id": "A", "year": 2026, "month": 10, "status": "brouillon", "payslip_data": {
                "arrets_du_bulletin": {"reportes": [
                    {"date": "2026-09-29", "absence_id": ARRET_ID, "sans_retenue": True}]}}},
        ],
    })
    report = preparer_le_report(client, "A", 2026, 9, forfait_jours=False, company_data={})
    assert report.repris == {date(2026, 9, 29)}
    assert any("sans seconde retenue" in a and "retenez-le à la main" in a for a in report.alertes)


def test_une_autre_lecture_en_echec_garde_les_jours_repris_par_le_suivant():
    class Client(_Client):
        def table(self, nom):
            requete = _Requete(self.donnees, nom)
            if nom == "payslips":
                execute = requete.execute

                def lire():
                    if requete._filtres.get("month") == 8:
                        raise RuntimeError("bulletin d'août illisible")
                    return execute()

                requete.execute = lire
            return requete

    client = Client({
        "absence_requests": [{**_arret(["2026-08-31", "2026-09-29"]), "employee_id": "A"}],
        "payslips": [{"employee_id": "A", "year": 2026, "month": 10, "status": "valide", "payslip_data": {
            "arrets_du_bulletin": {"reportes": [{"date": "2026-09-29", "absence_id": ARRET_ID}]}}}],
    })
    report = preparer_le_report(client, "A", 2026, 9, forfait_jours=False, company_data={})
    assert report.repris == {date(2026, 9, 29)}
    assert ar.MESSAGE_REPORT_ILLISIBLE in report.alertes


# --- L'écran Arrêts & IJ -----------------------------------------------------------------


def test_l_ecran_dit_ou_en_est_le_report():
    assert etat_du_report(ARRET_ID, None) == ETAT_REPORT_AU_PROCHAIN_CALCUL
    repris = {"status": "brouillon", "payslip_data": {"arrets_du_bulletin": {
        "reportes": [{"date": "2026-09-29", "absence_id": ARRET_ID}]}}}
    assert etat_du_report(ARRET_ID, repris) == ETAT_REPORTE
    assert etat_du_report(ARRET_ID, {"status": "brouillon", "payslip_data": {}}) == ETAT_REPORT_A_RECALCULER
    assert etat_du_report(ARRET_ID, {"status": "valide", "payslip_data": {}}) == ETAT_REMIS_SANS_REPORT


def _ecran(monkeypatch, *, forfait=False, regle=None, planning=None, saisies=(), suivant=None,
           arrets=(), duree=35.0):
    """L'écran sur une base simulée : la période se résout comme au moteur."""
    donnees = {
        "companies": [{"id": "societe", **(regle or {"paie_jour_de_fin": 4, "paie_occurrence": -2})}],
        "employees": [{"id": "A", "statut": "Cadre" if forfait else "Non-Cadre",
                       "is_forfait_jour": forfait, "duree_hebdomadaire": duree}],
        "employee_schedules": [
            {"employee_id": "A", "year": y, "month": m, "planned_calendar": p}
            for (y, m), p in (planning or {}).items()
        ],
        "monthly_inputs": [{"employee_id": "A", **s} for s in saisies],
    }
    monkeypatch.setattr(ecran, "_client", lambda: _Client(donnees))
    return ecran._ReportDesArrets("societe", 2026, 9, lambda eid: suivant, list(arrets))


def test_l_ecran_suit_l_analyse_du_moteur(monkeypatch):
    arret = {**_arret(["2026-09-29"]), "employee_id": "A"}
    # Société reprise : Quadra avait déjà retenu le 29/09. Rien à reporter.
    deja = _reprise([{"libelle": "Absence maladie 290926", "perte": 105.0}])
    assert _ecran(monkeypatch, arrets=[arret]).etat(arret, deja, True) == ETAT_COMPTE_PAR_LE_BULLETIN
    # Porté à la main au planning d'octobre : le dire, ne rien demander.
    planning = {(2026, 10): {"regularisations_anterieures": [
        {"type": "arret_maladie", "date_complete": "2026-09-29"}]}}
    vue = _ecran(monkeypatch, planning=planning, arrets=[arret])
    assert vue.etat(arret, _reprise([]), True) == ETAT_PORTE_A_LA_MAIN
    # À reporter : l'état vient du bulletin d'octobre.
    assert _ecran(monkeypatch, arrets=[arret]).etat(arret, _reprise([]), True) == ETAT_REPORT_AU_PROCHAIN_CALCUL
    # Brouillon de septembre calculé avant l'arrêt : à recalculer, comme avant.
    brouillon = _reprise([], status="brouillon")
    assert _ecran(monkeypatch, arrets=[arret]).etat(arret, brouillon, False) == "bulletin_a_recalculer"
    # Au forfait, le 29/09 est dans la période d'octobre (24/08 au 20/09 pour septembre).
    vue = _ecran(monkeypatch, forfait=True, arrets=[arret])
    assert vue.etat(arret, _reprise([]), True) == ETAT_DANS_LA_PERIODE_SUIVANTE
    # Règle vide : mois civil, comme le moteur ; le 29/09 est alors en septembre.
    vue = _ecran(monkeypatch, forfait=True, regle={"paie_jour_de_fin": None, "paie_occurrence": None},
                 arrets=[arret])
    assert vue.etat(arret, _reprise([]), True) == ETAT_REPORT_AU_PROCHAIN_CALCUL


def test_l_ecran_compte_les_heures_d_une_journee_du_contrat(monkeypatch):
    # 39 h : une journée vaut 7,8 h ; 7,8 h reprises à la main couvrent le 28/09.
    arret = {**_arret(["2026-09-28", "2026-09-29"]), "employee_id": "A"}
    regul = {"year": 2026, "month": 10, "correction_ligne": {
        "type": "regularisation_heures", "nature": "normales", "mois_origine": "2026-09", "quantite": -7.8}}
    vue = _ecran(monkeypatch, saisies=[regul], arrets=[arret], duree=39.0)
    analyse = vue._analyse("A", _reprise([]))
    assert analyse.portes_a_la_main == {date(2026, 9, 28)}
    assert _jours(analyse.jours) == [date(2026, 9, 29)]


def test_la_consigne_a_la_main_disparait_une_fois_le_geste_fait(monkeypatch):
    arret = {**_arret(["2026-09-29"]), "employee_id": "A"}
    octobre_valide = {"status": "valide", "payslip_data": {}}
    vue = _ecran(monkeypatch, suivant=octobre_valide, arrets=[arret])
    assert vue.etat(arret, _reprise([]), True) == ETAT_REMIS_SANS_REPORT
    planning = {(2026, 11): {"regularisations_anterieures": [
        {"type": "arret_maladie", "date_complete": "2026-09-29"}]}}
    vue = _ecran(monkeypatch, suivant=octobre_valide, planning=planning, arrets=[arret])
    assert vue.etat(arret, _reprise([]), True) == ETAT_PORTE_A_LA_MAIN_APRES


# --- DSN -------------------------------------------------------------------------------------


def test_la_dsn_d_octobre_declare_l_arret_reporte_a_ses_vraies_dates():
    absences = [{"id": ARRET_ID, "type": "arret_maladie", "selected_days": ["2026-09-29"],
                 "subrogation_active": True}]
    octobre = (date(2026, 10, 1), date(2026, 10, 31))
    assert blocs_arret(absences, *octobre) == []
    blocs = blocs_arret(absences, *octobre, jours_reportes=[date(2026, 9, 29)])
    assert len(blocs) == 1
    assert blocs[0]["S21.G00.60.003"] == "29092026"
    assert blocs[0]["S21.G00.60.010"] == "30092026"


def test_la_dsn_lit_les_deux_dates_d_un_libelle_avec_l_annee():
    ligne = {"libelle": "Absence arrêt maladie du 28/12/26 au 02/01/27 (arrêt reporté)"}
    assert _bornes_ligne_d_arret(ligne, 2027) == (date(2026, 12, 28), date(2027, 1, 2))
    assert _bornes_ligne_d_arret({"libelle": "Absence arrêt maladie du 01/10 au 30/10"}, 2026) == (
        date(2026, 10, 1), date(2026, 10, 30))


def test_un_arret_repris_au_milieu_se_dit_au_bulletin_d_origine():
    """Origine régénérée, arrêt repris au milieu par le suivant : alerte visible."""
    from types import SimpleNamespace

    from app.modules.payroll.documents.arrets_reportes_bulletin import (
        MESSAGE_REPORT_PARTIEL,
        appliquer_les_arrets_reportes,
    )

    contexte = SimpleNamespace(alertes_baremes=[])
    calendrier = [
        {"date_complete": "2026-09-21", "type": "arret_maladie", "report_partiel": True},
        {"date_complete": "2026-09-22", "type": "travail"},
    ]
    appliquer_les_arrets_reportes(
        contexte, calendrier, [], [], [],
        company_id=None, employee_id=None, year=2026, month=9,
        saisie_du_mois=None, avec_arret_du_mois=True,
    )
    assert contexte.alertes_baremes == [MESSAGE_REPORT_PARTIEL]

    sans = SimpleNamespace(alertes_baremes=[])
    appliquer_les_arrets_reportes(
        sans, [{"date_complete": "2026-09-21", "type": "arret_maladie"}], [], [], [],
        company_id=None, employee_id=None, year=2026, month=9,
        saisie_du_mois=None, avec_arret_du_mois=True,
    )
    assert sans.alertes_baremes == []
