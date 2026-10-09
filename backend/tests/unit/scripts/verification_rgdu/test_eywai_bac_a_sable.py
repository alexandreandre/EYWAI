"""Logique pure du calcul MARTINE en bac à sable (complément de la tâche 9, point 5).

Aucun appel au moteur ni à la base : on vérifie la jointure salarié ↔ clé Quadra, le plan
des appels (janvier, mois d'embauche, cumuls reconstruits, données manquantes), la reprise
depuis le cache et le tri des écritures tentées.
"""
from datetime import date

import pytest

from scripts.verification_rgdu.chemins import parametres_de
from scripts.verification_rgdu.dsn_quadra import BaseReduction
from scripts.verification_rgdu.eywai_bac_a_sable import (
    CUMULS_A_ZERO, a_faire, cle_cache, ecritures_interdites, joindre_employes, plan_des_appels,
    smic_dsn_du_salarie,
)
from scripts.verification_rgdu.quadra_mois import MoisQuadra

pytestmark = pytest.mark.unit

NIR_A = "1999999999999"
NIR_B = "2888888888888"


def _mq(mois, cumul_bruts, reduction, nir=NIR_A, matricule="AAA", entree=None):
    m = MoisQuadra("essai", mois, matricule, nir, 2000.0, cumul_bruts, 0.0, 151.67, reduction)
    m.entree = entree
    return m


def _base(nir, mois, smic):
    return BaseReduction(nir, "", "", date(2026, mois, 1), date(2026, mois, 28), smic_retenu=smic)


def test_smic_dsn_du_salarie_ne_garde_que_la_base_du_mois_et_du_nir():
    bases = {
        1: [_base(NIR_A, 1, 1823.03), _base(NIR_B, 1, 2000.0)],
        2: [_base(NIR_A, 2, 1850.0), _base(NIR_A, 1, 0.0)],   # bloc de continuité du mois précédent
        3: [],
    }
    assert smic_dsn_du_salarie(bases, NIR_A) == {1: 1823.03, 2: 1850.0}


def test_jointure_par_nir_et_matricule_puis_par_nir_seul_quand_il_est_unique():
    cles = {f"{NIR_A}/AAA", f"{NIR_B}/BBB2", f"{NIR_B}/BBB3"}
    employes = [
        {"id": "e-a", "nir": NIR_A + "12", "matricule": "AUTRE"},     # matricule différent, NIR unique
        {"id": "e-b2", "nir": NIR_B + "34", "matricule": "BBB2"},     # jointure exacte
        {"id": "e-x", "nir": None, "matricule": None},                # rien pour joindre
    ]
    j = joindre_employes(employes, cles)
    assert j == {f"{NIR_A}/AAA": ("e-a", "nir seul"), f"{NIR_B}/BBB2": ("e-b2", "nir/matricule")}


def test_deux_employes_sur_une_meme_cle_ne_sont_pas_joints():
    cles = {f"{NIR_A}/AAA"}
    employes = [{"id": "e-1", "nir": NIR_A, "matricule": "AAA"}, {"id": "e-2", "nir": NIR_A, "matricule": "AAA"}]
    assert joindre_employes(employes, cles) == {}


def test_plan_des_appels_janvier_embauche_cumuls_reconstruits_et_manquants():
    prm = parametres_de("comitech")
    cle_a, cle_b, cle_c = f"{NIR_A}/AAA", f"{NIR_B}/BBB", "CCC"
    mois_par_cle = {
        # Présent toute l'année : janvier hors bac à sable, février reconstruit depuis la DSN.
        cle_a: [_mq(1, 2000.0, 700.0), _mq(2, 4000.0, 700.0)],
        # Embauché en mars : cumuls à zéro ce mois-là, puis avril reconstruit.
        cle_b: [_mq(3, 1000.0, 390.0, NIR_B, "BBB", entree="16/03/2026"), _mq(4, 3000.0, 750.0, NIR_B, "BBB")],
        # Mois 5 sans mois 4 ni embauche : aucun cumul de départ.
        cle_c: [_mq(5, 9000.0, 0.0, "", "CCC")],
    }
    jointure = {cle_a: ("e-a", "nir/matricule"), cle_b: ("e-b", "nir/matricule")}
    smic_dsn = {cle_a: {1: 1823.03, 2: 1823.03}, cle_b: {3: 900.0}}
    plan = {(t.cle, t.mois): t for t in plan_des_appels(mois_par_cle, jointure, smic_dsn, prm)}

    janvier = plan[(cle_a, 1)]
    assert janvier.cumuls is None and janvier.statut == "janvier" and janvier.employee_id == "e-a"

    fevrier = plan[(cle_a, 2)]
    assert fevrier.statut == "a_calculer" and fevrier.depart == "quadra"
    assert fevrier.cumuls == {"cumuls": {"brut_total": 2000.0, "heures_remunerees": round(1823.03 / 12.02, 2),
                                         "reduction_generale_patronale": -700.0}}

    embauche = plan[(cle_b, 3)]
    assert embauche.statut == "a_calculer" and embauche.depart == "embauche" and embauche.cumuls == CUMULS_A_ZERO

    avril = plan[(cle_b, 4)]
    assert avril.statut == "a_calculer" and avril.depart == "quadra"
    assert avril.cumuls["cumuls"]["heures_remunerees"] == round(900.0 / 12.02, 2)

    sans = plan[(cle_c, 5)]
    assert sans.statut == "sans_employe" and sans.cumuls is None


def test_un_mois_sans_cumuls_reconstructibles_est_note_sans_appel():
    prm = parametres_de("comitech")
    cle = f"{NIR_A}/AAA"
    mois_par_cle = {cle: [_mq(3, 6000.0, 0.0), _mq(5, 9000.0, 0.0)]}   # mois 4 absent
    plan = {t.mois: t for t in plan_des_appels(mois_par_cle, {cle: ("e-a", "nir/matricule")}, {cle: {}}, prm)}
    assert plan[5].statut == "sans_cumuls" and plan[5].cumuls is None and plan[5].raison
    assert plan[3].statut == "sans_cumuls"


def test_la_reprise_saute_ce_qui_est_deja_en_cache():
    prm = parametres_de("comitech")
    cle = f"{NIR_A}/AAA"
    mois_par_cle = {cle: [_mq(1, 2000.0, 700.0), _mq(2, 4000.0, 700.0), _mq(3, 6000.0, 700.0)]}
    plan = plan_des_appels(mois_par_cle, {cle: ("e-a", "nir/matricule")}, {cle: {1: 1823.03, 2: 1823.03}}, prm)
    cache = {cle_cache(cle, 2): {"statut": "ok"}, cle_cache(cle, 3): {"statut": "erreur"}}
    assert [t.mois for t in a_faire(plan, cache)] == []
    assert [t.mois for t in a_faire(plan, cache, refaire_erreurs=True)] == [3]
    assert [t.mois for t in a_faire(plan, {})] == [2, 3]


def test_seules_les_ecritures_hors_droits_d_anciennete_sont_interdites():
    ecritures = ["insert employee_cp_seniority_grants", "update employee_cp_seniority_grants",
                 "upsert employee_schedules", "upload payslips"]
    assert ecritures_interdites(ecritures) == ["upsert employee_schedules", "upload payslips"]
