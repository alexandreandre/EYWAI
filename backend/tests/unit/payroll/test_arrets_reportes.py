"""Arrêt arrivé après la validation du bulletin de son mois : repris par le bulletin suivant.

Retour d'Elsa du 26/11/2026 (LEWIS, salarié A : arrêt du 29/09 saisi le 26/11,
septembre déjà validé). Quadra et le cabinet de Colorplast comptent l'arrêt au
bulletin de sa période ; connu après, il passe sur le bulletin suivant à ses
vraies dates (Cartol, « Absence maladie 230726-240726 » sur août). Les deux
générateurs : heures et forfait jours.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.ijss_tracking.domain.arrets_du_mois import (
    ETAT_REMIS_SANS_REPORT,
    ETAT_REPORT_A_RECALCULER,
    ETAT_REPORT_AU_PROCHAIN_CALCUL,
    ETAT_REPORTE,
    etat_du_report,
)
from app.modules.payroll.application.arrets_reportes import (
    JourReporte,
    evenements_du_report,
    jours_a_reporter,
    jours_des_libelles,
    mois_repris_a_la_main,
    periode_precedente,
    sans_les_jours_deja_reportes,
)
from app.modules.payroll.documents import arrets_reportes_bulletin as bulletin_report
from app.modules.payroll.documents.arrets_reportes_bulletin import (
    fusionner_le_report,
    trace_des_arrets,
)
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import (
    _diviseur_jour_absence,
    calculer_salaire_brut_forfait,
)
from app.modules.payroll.engine.calcul_cotisations import jours_maintenus_du_mois

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
        "generated_at": "2026-11-08T03:09:44+00:00",
        "payslip_data": {"reprise": {"logiciel_precedent": "Quadra"}, "calcul_du_brut": lignes},
    }


def _reporter(arrets, bulletins, **kw):
    return jours_a_reporter(arrets, bulletins, SEPTEMBRE, annee_origine=2026, mois_origine=9, **kw)


# --- Ce qu'un bulletin a compté --------------------------------------------------


def test_les_retenues_datees_de_quadra_et_de_martine_se_lisent():
    lignes = [
        {"libelle": "Absence maladie 220926-230926", "perte": 348.31},
        {"libelle": "Absence A.T. 310826", "perte": 102.41},
        {"libelle": "Absence arrêt maladie du 28/09 au 30/09", "perte": 300.0},
        # Un gain daté ne retient rien : il ne couvre aucun jour.
        {"libelle": "Rappel 250926", "gain": 10.0, "perte": None},
    ]
    jours = jours_des_libelles(lignes, 2026, 9)
    assert jours == {
        date(2026, 9, 22),
        date(2026, 9, 23),
        date(2026, 8, 31),
        date(2026, 9, 28),
        date(2026, 9, 29),
        date(2026, 9, 30),
    }


def test_decembre_sur_un_bulletin_de_janvier_est_de_l_annee_d_avant():
    jours = jours_des_libelles([{"libelle": "Absence arrêt maladie du 31/12", "perte": 1}], 2027, 1)
    assert jours == {date(2026, 12, 31)}


# --- Le choix des jours ------------------------------------------------------------


def test_le_29_09_saisi_apres_la_validation_de_septembre_est_reporte():
    # LEWIS, salarié A : le bulletin de septembre repris de Quadra ne porte que
    # de l'activité partielle ; l'arrêt du 29/09 a été saisi le 26/11.
    septembre = _reprise([{"libelle": "Act. partiel. 250926", "perte": 105.0}])
    jours = _reporter([_arret(["2026-09-29"])], [septembre])
    assert jours == [JourReporte(date(2026, 9, 29), ARRET_ID)]


def test_un_jour_que_quadra_a_deja_retenu_n_est_pas_reporte():
    # Arrêt saisi après coup sur tout septembre ; Quadra en avait retenu le 1 au 7.
    septembre = _reprise([{"libelle": "Absence maladie 010926-070926", "perte": 674.99}])
    jours_arret = [f"2026-09-{j:02d}" for j in range(1, 10)]
    jours = _reporter([_arret(jours_arret)], [septembre])
    assert [j.jour for j in jours] == [date(2026, 9, 8), date(2026, 9, 9)]


def test_rien_tant_que_le_bulletin_d_origine_n_est_pas_valide():
    # Un brouillon se recalcule : c'est lui qui comptera l'arrêt.
    brouillon = _reprise([], status="brouillon")
    assert _reporter([_arret(["2026-09-29"])], [brouillon]) == []
    # Pas de bulletin du tout (mois d'avant Martine) : rien non plus.
    assert _reporter([_arret(["2026-09-29"])], []) == []


def test_un_bulletin_de_martine_calcule_apres_la_saisie_a_compte_l_arret():
    martine = {"status": "valide", "generated_at": "2026-11-27T08:00:00+00:00", "payslip_data": {}}
    assert _reporter([_arret(["2026-09-29"])], [martine]) == []
    avant = {**martine, "generated_at": "2026-11-20T08:00:00+00:00"}
    assert [j.jour for j in _reporter([_arret(["2026-09-29"])], [avant])] == [date(2026, 9, 29)]


def test_la_trace_du_bulletin_fait_foi():
    trace = {"jours_comptes": ["2026-09-29"], "reportes": []}
    compte = {"status": "valide", "generated_at": "2026-12-01T00:00:00+00:00",
              "payslip_data": {"arrets_du_bulletin": trace}}
    assert _reporter([_arret(["2026-09-29"])], [compte]) == []
    # Calculé après la saisie, mais sans ce jour (le bulletin suivant l'avait
    # déjà repris quand celui-ci a été régénéré) : la trace dit qu'il ne l'a pas compté.
    sans = {**compte, "payslip_data": {"arrets_du_bulletin": {"jours_comptes": [], "reportes": []}}}
    assert [j.jour for j in _reporter([_arret(["2026-09-29"])], [sans])] == [date(2026, 9, 29)]


def test_pas_de_double_compte_avec_une_saisie_a_la_main():
    septembre = _reprise([])
    # Régularisation antérieure du même jour posée au planning d'octobre.
    assert _reporter([_arret(["2026-09-29"])], [septembre], deja_portes={date(2026, 9, 29)}) == []
    # Heures normales de septembre reprises depuis l'onglet « Corriger ».
    regul = [{"nature": "normales", "mois_origine": "2026-09", "quantite": -7.0}]
    assert mois_repris_a_la_main(regul, 2026, 9)
    assert not mois_repris_a_la_main([{**regul[0], "quantite": 7.0}], 2026, 9)
    assert _reporter([_arret(["2026-09-29"])], [septembre], repris_a_la_main=True) == []


def test_un_arret_annule_ne_se_reporte_plus():
    septembre = _reprise([])
    assert _reporter([_arret(["2026-09-29"], status="cancelled")], [septembre]) == []


def test_un_week_end_seul_ne_se_reporte_pas():
    # Arrêt du jeudi 24 au dimanche 27/09, Quadra a retenu jusqu'au vendredi.
    septembre = _reprise([{"libelle": "Absence maladie 240926-250926", "perte": 200.0}])
    jours = _reporter([_arret(["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"])], [septembre])
    assert jours == []


def test_la_periode_precedente_est_le_mois_civil_aux_heures_et_la_periode_au_forfait():
    assert periode_precedente(2026, 10, forfait_jours=False) == (2026, 9, SEPTEMBRE)
    assert periode_precedente(2026, 1, forfait_jours=False)[:2] == (2025, 12)
    # Avant-dernier vendredi : septembre 2026 va du 24/08 au 20/09.
    assert periode_precedente(2026, 10, forfait_jours=True, jour_de_fin=4, occurrence=-2) == (
        2026,
        9,
        (date(2026, 8, 24), date(2026, 9, 20)),
    )


def test_les_evenements_reportes_gardent_leur_date_et_le_disent():
    analyse_septembre = [
        {"jour": 28, "type": "travail_base", "heures": 7.0},
        {"jour": 29, "type": "arret_maladie", "heures": 0.0, "arret_type": "maladie_simple",
         "date_debut_arret_reel": "2026-09-29", "date_fin_arret_reel": "2026-09-29"},
    ]
    evs = evenements_du_report(analyse_septembre, [JourReporte(date(2026, 9, 29), ARRET_ID)], 2026, 9)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["date_complete"] == "2026-09-29"
    assert ev["is_regularisation_anterieure"] and ev["arret_reporte"]
    assert ev["absence_id"] == ARRET_ID
    assert (ev["annee"], ev["mois"], ev["jour"]) == (2026, 9, 29)


def test_le_bulletin_d_origine_regenere_ne_recompte_pas_le_jour_repris():
    evs = [
        {"jour": 29, "type": "arret_maladie", "heures": 0.0},
        {"jour": 30, "type": "travail_base", "heures": 7.0},
    ]
    restants = sans_les_jours_deja_reportes(evs, {date(2026, 9, 29)}, 2026, 9)
    assert [e["jour"] for e in restants] == [30]


# --- Le bulletin d'octobre : retenue aux deux générateurs ------------------------------


def _evenement_reporte(heures: float, jour: int = 29) -> dict:
    return {
        "date_complete": f"2026-09-{jour:02d}",
        "annee": 2026,
        "mois": 9,
        "jour": jour,
        "type": "arret_maladie",
        "heures": heures,
        "arret_type": "maladie_simple",
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
    assert len(lignes) == 1
    assert lignes[0]["libelle"] == "Absence arrêt maladie du 29/09/26 (arrêt reporté)"
    assert lignes[0]["quantite"] == 7.0
    assert lignes[0]["perte"] > 0
    sans = calculer_salaire_brut(ctx, _octobre_travaille(7.0), date(2026, 10, 1), date(2026, 10, 31))
    assert res["salaire_brut_total"] == pytest.approx(
        sans["salaire_brut_total"] - lignes[0]["perte"], abs=0.01
    )


def test_forfait_jours_la_retenue_du_jour_reporte_est_sur_octobre_a_sa_date():
    # Au forfait, la période d'octobre va du 21/09 au 25/10 : le jour reporté
    # vient de celle de septembre (24/08 au 20/09), ici le vendredi 18/09.
    ctx = build_test_contexte(statut="Cadre", salaire_base=3831.39,
                              specificites_extra={"is_forfait_jour": True})
    periode = (date(2026, 9, 21), date(2026, 10, 25))
    cal = [_evenement_reporte(0.0, jour=18)]
    res = calculer_salaire_brut_forfait(ctx, cal, *periode, [])
    lignes = [l for l in res["lignes_composants_brut"] if l.get("arret_reporte")]
    assert len(lignes) == 1
    assert lignes[0]["libelle"] == "Absence arrêt maladie du 18/09/26 (arrêt reporté)"
    journee = round(3831.39 / _diviseur_jour_absence(ctx), 2)
    assert lignes[0]["perte"] == pytest.approx(journee, abs=0.01)
    assert res["salaire_brut_total"] == pytest.approx(3831.39 - journee, abs=0.02)
    # Le report ne rend pas le mois « entièrement absent ».
    assert res["retenues_absence_mois"] == pytest.approx(journee, abs=0.01)


# --- Maintien et IJ des jours reportés -------------------------------------------------

REGLAGES = {"apply_legal_maintenance": True}


class _Reglages:
    def model_dump(self, mode="json"):
        return dict(REGLAGES)


@pytest.fixture
def reglages_de_maintien(monkeypatch):
    import app.modules.payroll.infrastructure.salaires_de_reference as salaires
    from app.modules.maintenance_settings.application import queries

    monkeypatch.setattr(queries, "get_maintenance_settings", lambda company_id: _Reglages())
    monkeypatch.setattr(salaires, "poser_salaires_de_reference", lambda arret, eid: None)


@pytest.mark.parametrize("forfait", [False, True], ids=["heures", "forfait_jours"])
def test_le_maintien_du_jour_reporte_porte_sur_ce_seul_jour(reglages_de_maintien, monkeypatch, forfait):
    # Sans borne, le moteur voyait la période « entièrement en arrêt » et
    # maintenait le salaire du mois entier pour un seul jour.
    from app.modules.payroll.engine import maintien_salaire_service as mss

    appels = []
    vrai = mss.calculer_maintien

    def espion(arret, contexte, settings, debut, fin, **kw):
        appels.append((arret, debut, fin))
        return vrai(arret, contexte, settings, debut, fin, **kw)

    monkeypatch.setattr(mss, "calculer_maintien", espion)
    if forfait:
        ctx = build_test_contexte(statut="Cadre", salaire_base=3831.39,
                                  specificites_extra={"is_forfait_jour": True})
    else:
        ctx = build_test_contexte(salaire_base=2275.0, duree_hebdo=35.0)
    report = bulletin_report.maintien_des_arrets_reportes(
        [_evenement_reporte(0.0 if forfait else 7.0)], ctx, "societe", None
    )
    assert report is not None and len(report["arrets"]) == 1
    arret, debut, fin = appels[0]
    assert (debut, fin) == (date(2026, 9, 29), date(2026, 9, 29))
    assert arret["mois_entier_en_arret"] is False
    assert arret["date_debut"] == "2026-09-29"  # vrai début : carence et rang de jour
    verse = report["arrets"][0][1]["maintien"]["maintien_verse"]
    assert 0 <= verse < (3831.39 if forfait else 2275.0) / 10


def test_le_maintien_reporte_rejoint_celui_du_mois_sans_couvrir_ses_jours():
    report = {"arrets": [([date(2026, 9, 29)], {
        "maintien": {"maintien_verse": 103.41},
        "ijss": {"ijss_theorique": 0.0},
        "subrogation_active": True,
    })]}
    # Pas d'arrêt en octobre : le report tient lieu de maintien du bulletin.
    seul = fusionner_le_report(None, report)
    assert seul["maintien"]["maintien_verse"] == 103.41
    assert seul["maintien"]["maintien_verse_du_mois"] == 0.0
    assert seul["arrets_reportes"][0]["du"] == "2026-09-29"
    # Défaut A11 : le 29/09 ne fait pas du 29/10 un jour maintenu.
    assert jours_maintenus_du_mois({29}, seul) == set()

    octobre = {"maintien": {"maintien_verse": 200.0}, "ijss": {"ijss_theorique": 50.0},
               "subrogation_active": True}
    fusion = fusionner_le_report(octobre, report)
    assert fusion["maintien"]["maintien_verse"] == 303.41
    assert fusion["maintien"]["maintien_verse_du_mois"] == 200.0
    assert fusion["ijss"]["ijss_theorique"] == 50.0
    assert jours_maintenus_du_mois({12, 13}, fusion) == {12, 13}
    assert octobre["maintien"]["maintien_verse"] == 200.0  # non modifié
    assert fusionner_le_report(octobre, None) is octobre


def test_la_trace_dit_les_jours_traites_et_les_jours_repris():
    cal = [
        {"date_complete": "2026-10-15", "type": "arret_maladie",
         "date_debut_arret_reel": "2026-10-15", "date_fin_arret_reel": "2026-10-18"},
        {"date_complete": "2026-10-16", "type": "arret_maladie",
         "date_debut_arret_reel": "2026-10-15", "date_fin_arret_reel": "2026-10-18"},
        _evenement_reporte(7.0),
    ]
    trace = trace_des_arrets(cal, date(2026, 10, 1), date(2026, 10, 31))
    # Le week-end du 17-18 est compris : ses IJ sont celles du bulletin d'octobre.
    assert trace["jours_comptes"] == ["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
    assert trace["reportes"] == [{"date": "2026-09-29", "absence_id": ARRET_ID}]


# --- L'écran Arrêts & IJ -----------------------------------------------------------------


def test_l_ecran_dit_ou_en_est_le_report():
    assert etat_du_report(ARRET_ID, None) == ETAT_REPORT_AU_PROCHAIN_CALCUL
    repris = {"status": "brouillon", "payslip_data": {"arrets_du_bulletin": {
        "reportes": [{"date": "2026-09-29", "absence_id": ARRET_ID}]}}}
    assert etat_du_report(ARRET_ID, repris) == ETAT_REPORTE
    assert etat_du_report(ARRET_ID, {"status": "brouillon", "payslip_data": {}}) == ETAT_REPORT_A_RECALCULER
    assert etat_du_report(ARRET_ID, {"status": "valide", "payslip_data": {}}) == ETAT_REMIS_SANS_REPORT
