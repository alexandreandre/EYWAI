"""Les adaptateurs conservent le canal des cumuls et les deux blocs de lignes."""
from datetime import date
from unittest.mock import patch

from app.modules.payroll.engine.calcul_brut import _iccp_legale_par_periode
from app.modules.payroll.infrastructure.reference_dixieme import (
    base_de_reference,
    lignes_pour_dixieme,
)
from app.shared.domain.dixieme_conges import calculer_base_dixieme


def test_les_absences_et_les_gains_se_lisent_ensemble():
    lignes = lignes_pour_dixieme({
        "calcul_du_brut": [{"libelle": "Maintien de salaire", "gain": 900.0}],
        "details_absences": [{"libelle": "Absence maladie du 01/09", "perte": 1000.0}],
    })
    assert len(lignes) == 2
    assert calculer_base_dixieme(2900.0, lignes).base == 2800.0


def test_le_code_stable_prime_sur_un_libelle_renomme():
    lignes = lignes_pour_dixieme({"details_absences": [
        {"code": "brut:reduction_hs_absence", "libelle": "Autre présentation", "perte": 100.0},
        {"libelle": "Absence maladie du 01/09", "perte": 1000.0},
    ]})
    assert calculer_base_dixieme(1900.0, lignes).base == 2780.0


def test_un_contrat_range_transmet_son_identifiant_au_lecteur():
    with patch("app.modules.payroll.infrastructure.reference_dixieme.lire_bulletins_reference", return_value=[]) as lire:
        resultat = base_de_reference(None, "salarie-fictif", date(2026, 6, 1), date(2026, 6, 30), lire_cumul=False, contract_period_id="contrat-fictif")
    assert resultat.base is None
    assert lire.call_args.kwargs["contract_period_id"] == "contrat-fictif"


def test_iccp_du_mois_de_sortie_reconstitue_la_maladie_et_exclut_la_prime():
    from types import SimpleNamespace

    ctx = SimpleNamespace(cp_fin_de_contrat={"periode_en_cours": {
        "brut_avant_mois": 2000.0, "droits": 10.0, "restants": 10.0,
    }}, alertes_baremes=[], exit_indemnities=None)
    resultat = _iccp_legale_par_periode(ctx, 2500.0, 0.1, None, None, 1.0, [
        {"libelle": "Absence maladie du 01/09", "perte": 1000.0},
        {"libelle": "Prime de fin d'année", "gain": 500.0},
    ])
    assert resultat.total == 480.0  # 10 % de 2 000 + (2 500 + 800 - 500)


def test_iccp_ne_transforme_pas_un_passe_inconnu_en_zero():
    from types import SimpleNamespace

    ctx = SimpleNamespace(cp_fin_de_contrat={"periode_en_cours": {
        "brut_avant_mois": None, "droits": 10.0, "restants": 10.0,
    }}, alertes_baremes=[], exit_indemnities=None)
    resultat = _iccp_legale_par_periode(ctx, 2500.0, 0.1, None, None, 100.0)
    assert resultat.total == 1000.0
    assert resultat.periodes[0].dixieme is None


def test_bulletin_repris_mixant_conges_et_maladie_affecte_chaque_retenue_hs():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "H.Absence Congés Payés", "perte": 920.01},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 131.43},
        {"libelle": "Absence maladie 170826-310826", "perte": 1012.01},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 146.22},
    ]}, importe=True)
    resultat = calculer_base_dixieme(1162.72, lignes)
    assert resultat.base == 2089.30  # 1162,72 + 80 % de (1012,01 + 146,22)


def test_retenue_hs_calculee_hors_conges_payes_ne_se_repartit_pas_sur_eux():
    lignes = lignes_pour_dixieme({"details_absences": [
        {"libelle": "Absence maladie du 01/09", "perte": 1000.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 100.0},
        {"libelle": "Absence congés payés", "perte": 500.0},
    ]})
    assert calculer_base_dixieme(2000.0, lignes).base == 2880.0


def test_ferie_non_paye_repris_partage_les_hs_sans_reconstitution():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "Absence maladie 050526-080526", "perte": 341.60},
        {"libelle": "Abs. JF non payé 140526", "perte": 85.40},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 61.0},
    ]}, importe=True)
    assert calculer_base_dixieme(1664.78, lignes).base == 1977.10


def test_retenue_hs_unique_reprise_ne_depende_pas_de_la_derniere_absence():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "Absence non rémunérée", "perte": 500.0},
        {"libelle": "Absence maladie 050526-080526", "perte": 1000.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 150.0},
    ]}, importe=True)
    assert calculer_base_dixieme(2000.0, lignes).base == 2880.0


def test_abreviations_reprises_parentalite_et_autres_absences():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "Abs. Evt familli 160226-180226", "perte": 300.0},
        {"libelle": "Abs. paternité 190226-280226", "perte": 700.0},
        {"libelle": "Abs. Abs injustifiée 130726", "perte": 100.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 110.0},
    ]}, importe=True)
    assert calculer_base_dixieme(2000.0, lignes).base == 2770.0


def test_abreviation_reprise_accident_du_travail():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "Absence A.T. 010526-310526", "perte": 2000.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 200.0},
    ]}, importe=True)
    assert calculer_base_dixieme(0.0, lignes).base == 2200.0


def test_hs_reprises_par_groupes_separes_par_le_salaire():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "H.Absence Congés Payés", "perte": 100.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 10.0},
        {"libelle": "Salaire de base", "gain": 2000.0},
        {"libelle": "Abs. JF non payé 080526", "perte": 100.0},
        {"libelle": "Abs. JF non payé 140526", "perte": 100.0},
        {"libelle": "Absence A.T. 230526-290526", "perte": 400.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 60.0},
    ]}, importe=True)
    assert calculer_base_dixieme(1000.0, lignes).base == 1440.0


def test_hs_reprises_du_groupe_maladie_et_absence_non_payee():
    lignes = lignes_pour_dixieme({"calcul_du_brut": [
        {"libelle": "H.Absence Congés Payés", "perte": 500.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 50.0},
        {"libelle": "Salaire de base", "gain": 2000.0},
        {"libelle": "Abs. Abs aut nonpayé 310726", "perte": 100.0},
        {"libelle": "Absence maladie 170826-310826", "perte": 1000.0},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "perte": 110.0},
    ]}, importe=True)
    assert calculer_base_dixieme(1000.0, lignes).base == 1880.0
