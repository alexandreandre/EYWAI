"""Heures de récupération : mise au compteur à l'équivalent majoré, solde reporté.

Spec : docs/superpowers/specs/2026-11-05-heures-de-recuperation-design.md.
"""

from datetime import date

from app.modules.modulation.domain.hour_account_rules import (
    etat_du_mois,
    mettre_hs_au_compteur,
    mouvements_hors_paie_du_mois,
    solde_au,
)

MAJ = {"travail_hs25": 0.25, "travail_hs50": 0.5}


def _hs(jour: int, heures: float, type_: str = "travail_hs25", mois: int = 10) -> dict:
    return {
        "type": type_,
        "heures": heures,
        "jour": jour,
        "date_complete": date(2026, mois, jour).isoformat(),
    }


def test_une_heure_a_25_pour_cent_donne_une_heure_quinze():
    r = mettre_hs_au_compteur([_hs(5, 4)], majorations=MAJ)
    assert r.heures_sup_au_compteur == 4.0
    assert r.repos_credite == 5.0
    assert r.heures_sup_payees == 0.0
    assert [e for e in r.calendrier if e["type"].startswith("travail_hs")] == []


def test_heures_a_50_pour_cent_donnent_une_heure_trente():
    r = mettre_hs_au_compteur([_hs(5, 8), _hs(6, 2, "travail_hs50")], majorations=MAJ)
    assert r.repos_credite == 13.0  # 8 × 1,25 + 2 × 1,5
    assert r.heures_par_type == {"travail_hs25": 8.0, "travail_hs50": 2.0}


def test_le_plafond_se_compte_en_heures_de_repos_et_le_reste_est_paye():
    # Solde 8 h, plafond 10 h : 2 h de repos de place = 1,6 h sup à 25 %.
    r = mettre_hs_au_compteur(
        [_hs(5, 4)], majorations=MAJ, solde=8.0, plafond=10.0
    )
    assert r.repos_credite == 2.0
    assert r.heures_sup_au_compteur == 1.6
    assert r.heures_sup_payees == 2.4
    payees = sum(e["heures"] for e in r.calendrier if e["type"] == "travail_hs25")
    assert payees == 2.4


def test_compteur_plein_tout_est_paye():
    cal = [_hs(5, 4)]
    r = mettre_hs_au_compteur(cal, majorations=MAJ, solde=10.0, plafond=10.0)
    assert r.repos_credite == 0.0
    assert r.calendrier == cal


def test_les_heures_hors_de_la_fenetre_des_variables_ne_bougent_pas():
    cal = [_hs(28, 3, mois=9), _hs(5, 2)]
    r = mettre_hs_au_compteur(
        cal, majorations=MAJ, bornes=(date(2026, 10, 1), date(2026, 10, 31))
    )
    assert r.heures_sup_au_compteur == 2.0
    assert r.calendrier == [cal[0]]


def test_heures_a_payer_imposees_par_la_decision_du_mois():
    r = mettre_hs_au_compteur(
        [_hs(5, 3), _hs(12, 2)], majorations=MAJ, heures_a_payer=5.0
    )
    assert r.repos_credite == 0.0
    assert r.heures_sup_payees == 5.0
    r2 = mettre_hs_au_compteur(
        [_hs(5, 3), _hs(12, 2)], majorations=MAJ, heures_a_payer=1.0
    )
    assert r2.heures_sup_au_compteur == 4.0
    assert r2.repos_credite == 5.0


def test_les_derniers_jours_vont_au_compteur_en_premier():
    r = mettre_hs_au_compteur(
        [_hs(5, 3), _hs(12, 2)], majorations=MAJ, heures_a_payer=3.0
    )
    restant = {e["jour"]: e["heures"] for e in r.calendrier}
    assert restant == {5: 3}


def _mvt(t, h, annee, mois, statut="validated", source="manual_rh", **kw):
    return {
        "movement_type": t,
        "hours": h,
        "year": annee,
        "month": mois,
        "status": statut,
        "source": source,
        **kw,
    }


def test_le_solde_se_reporte_d_une_annee_sur_l_autre():
    mvts = [
        _mvt("opening_balance", 2.0, 2026, 9),
        _mvt("credit_hs", 5.0, 2026, 12, source="payroll_auto"),
        _mvt("debit_recovery", 3.0, 2027, 1, source="absence"),
    ]
    assert solde_au(mvts, 2026, 9) == 2.0
    assert solde_au(mvts, 2026, 12) == 7.0
    assert solde_au(mvts, 2027, 1) == 4.0


def test_un_mouvement_annule_ne_compte_pas():
    mvts = [
        _mvt("opening_balance", 2.0, 2026, 9),
        _mvt("debit_recovery", 2.0, 2026, 10, statut="cancelled", source="absence"),
    ]
    assert solde_au(mvts, 2026, 10) == 2.0


def test_mouvements_hors_paie_du_mois_retire_les_credits_de_la_paie_du_mois():
    mvts = [
        _mvt("opening_balance", 2.0, 2026, 9),
        _mvt("credit_hs", 5.0, 2026, 10, source="payroll_auto"),
        _mvt("credit_hs", 1.0, 2026, 11, source="payroll_auto"),
        _mvt("debit_recovery", 1.0, 2026, 10, source="absence"),
    ]
    restants = mouvements_hors_paie_du_mois(mvts, 2026, 10)
    assert [m["hours"] for m in restants] == [2.0, 1.0, 1.0]


def test_etat_du_mois_acquis_pris_avec_dates_et_solde():
    mvts = [
        _mvt("opening_balance", 0.5, 2026, 6),
        _mvt("credit_hs", 9.0, 2026, 7, source="payroll_auto"),
        _mvt(
            "debit_recovery",
            7.0,
            2026,
            7,
            source="absence",
            metadata={"jours": {"2026-07-13": 7.0}},
        ),
    ]
    etat = etat_du_mois(mvts, 2026, 7)
    assert etat["acquis"] == 9.0
    assert etat["pris"] == 7.0
    assert etat["paye"] == 0.0
    assert etat["solde"] == 2.5
    assert etat["prises"] == [{"date": "2026-07-13", "heures": 7.0}]


def test_etat_du_mois_compte_le_credit_du_calcul_en_cours():
    mvts = [
        _mvt("opening_balance", 2.0, 2026, 9),
        # Crédit d'une génération précédente du même mois : remplacé.
        _mvt("credit_hs", 4.0, 2026, 10, source="payroll_auto"),
    ]
    etat = etat_du_mois(mvts, 2026, 10, credit_du_calcul=5.0)
    assert etat["acquis"] == 5.0
    assert etat["solde"] == 7.0


def test_etat_du_mois_donne_aussi_le_cumul_de_l_annee():
    mvts = [
        _mvt("opening_balance", 2.0, 2026, 9),
        _mvt("credit_hs", 5.0, 2026, 10, source="payroll_auto"),
        _mvt("debit_recovery", 3.0, 2026, 10, source="absence"),
        _mvt("credit_hs", 1.25, 2026, 11, source="payroll_auto"),
        _mvt("debit_payout", 1.0, 2026, 11),
        _mvt("credit_hs", 9.0, 2026, 12, source="payroll_auto"),
    ]
    etat = etat_du_mois(mvts, 2026, 11)
    # Le solde d'ouverture n'est pas un acquis : il est dans le solde.
    assert etat["acquis_annee"] == 6.25
    assert etat["pris_annee"] == 4.0
    assert etat["solde"] == 4.25
