"""Le test du théorème rougit quand le calcul est faux (R-180, § 2.8 de la relecture 6).

Il comparait deux calculs entre eux : huit erreurs injectées sur onze restaient
vertes. Ici, un petit moteur en mémoire (une ligne de salaire, cinq cotisations,
l'impôt) porte chaque erreur, et le script doit la voir : valeur attendue
calculée à part, jamais le seul mouvement entre deux calculs.

Ce test prouve que les assertions rougissent ; il ne remplace pas le passage du
script sur les vrais bulletins, à faire sur la base.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_COTISATIONS, code_de_ligne_de_cotisation
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    JournalDesCorrections,
    corriger_le_taux_d_impot,
    poser_les_corrections_en_attente,
)
from tests.unit.payslips.test_theoreme_script import FauxSupabase, script  # noqa: F401 — la fixture

pytestmark = pytest.mark.unit

SALAIRE_DE_DEPART = 2426.72


def _cotisation(coti_id, libelle, base, taux_salarial=None, taux_patronal=None, patronal=None):
    ligne = {"coti_id": coti_id, "libelle": libelle, "base": base, "taux_salarial": taux_salarial, "taux_patronal": taux_patronal}
    ligne["montant_salarial"] = round(base * taux_salarial, 2) if taux_salarial is not None else 0.0
    ligne["montant_patronal"] = patronal if patronal is not None else (round(base * taux_patronal, 2) if taux_patronal is not None else 0.0)
    return ligne


def _bulletin(saisies, cumuls_avant, mutant, mois):
    journal = JournalDesCorrections(
        CorrectionDeLigne.depuis(s["correction_ligne"], saisie_id=s["id"]) for s in saisies if s.get("correction_ligne")
    )
    salaire = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.0, "gain": SALAIRE_DE_DEPART, "perte": None}
    journal.corriger(salaire, "brut", "brut:salaire_base")
    brut = float(salaire["gain"])
    assiette = SALAIRE_DE_DEPART if mutant == "E4" else brut
    reduction = -round((SALAIRE_DE_DEPART if mutant == "E5" else brut) * 0.1, 2)
    lignes = [
        _cotisation("vieillesse_deplafonnee", "Vieillesse déplafonnée", assiette, 0.004, 0.019),
        _cotisation("csg_deductible", "CSG déductible", round(assiette * 0.9825, 2), 0.068),
        _cotisation("csg_non_deductible", "CSG non déductible", round(assiette * 0.9825, 2), 0.024),
        _cotisation("crds", "CRDS", round(assiette * 0.9825, 2), 0.005),
        _cotisation("reduction_generale", "Réduction générale de cotisations patronales", assiette, patronal=reduction),
    ]
    for ligne in lignes:
        journal.corriger(ligne, BLOC_COTISATIONS, code_de_ligne_de_cotisation(ligne))
    salarial = round(sum(l["montant_salarial"] for l in lignes), 2)
    patronal = round(sum(l["montant_patronal"] for l in lignes), 2)
    non_deductible = sum(l["montant_salarial"] for l in lignes if l["coti_id"] in ("csg_non_deductible", "crds"))
    net_imposable = 2000.0 if mutant == "E7" else round(brut - (salarial - non_deductible), 2)
    taux, trace = corriger_le_taux_d_impot(5.0, net_imposable, journal)
    impot = round(net_imposable * taux / 100, 2)
    if mutant == "E6":
        impot = 90.0
    net = round(brut - salarial - impot + (100.0 if mutant == "E3" else 0.0), 2)
    data = {
        "salaire_brut": brut,
        "calcul_du_brut": [salaire],
        "details_conges": [],
        "details_absences": [],
        "cotisations_officielles": [{"code": "sante", "lignes": lignes, "total_salarial": salarial, "total_patronal": patronal}],
        "structure_cotisations": {"bloc_principales": lignes, "total_salarial": salarial, "total_patronal": patronal},
        "synthese_net": {
            "net_imposable": net_imposable,
            "montant_net_social": 1900.0 if mutant == "E11" else round(brut - salarial, 2),
            "impot_prelevement_a_la_source": {"base": net_imposable, "taux": taux, "montant": impot, **(trace or {})},
        },
        "net_a_payer": net,
    }
    poser_les_corrections_en_attente(data, journal)

    def _cumul(cle, valeur):
        return round(float(cumuls_avant.get(cle) or 0.0) + valeur, 2)

    oublie = mutant == "E8" and mois == 11
    cumuls = {
        "brut_total": _cumul("brut_total", brut),
        "net_imposable": net_imposable if oublie else _cumul("net_imposable", net_imposable),
        "impot_preleve_a_la_source": impot if oublie else _cumul("impot_preleve_a_la_source", impot),
        "reduction_generale_patronale": _cumul("reduction_generale_patronale", lignes[-1]["montant_patronal"]),
        "heures_remunerees": _cumul("heures_remunerees", float(salaire["quantite"])),
        "heures_supplementaires_remunerees": _cumul("heures_supplementaires_remunerees", 0.0),
    }
    return {"payslip_data": data, "cumuls": {"cumuls": cumuls}}


def _jouer(module, monkeypatch, mutant):
    def generer(employee_id, year, month, cumuls, saisies_en_plus=()):
        precedents = (cumuls or {}).get("cumuls", cumuls or {}) if isinstance(cumuls, dict) else {}
        return _bulletin(saisies_en_plus, precedents, mutant, month)

    monkeypatch.setattr(module, "_generer", generer)
    monkeypatch.setattr(module, "_cumuls_precedents", lambda *a, **k: {"brut_total": 20000.0, "net_imposable": 16000.0, "impot_preleve_a_la_source": 800.0, "reduction_generale_patronale": 2000.0, "heures_remunerees": 1365.03})
    monkeypatch.setattr(module, "supabase", FauxSupabase(employees=[{"id": "e1"}]))
    if mutant == "E10":
        vraie_ligne_od = module.ligne_od_du_bulletin

        def sans_patronal(**champs):
            ligne = vraie_ligne_od(**champs)
            ligne["cotisations_detail"] = [{**c, "montant_patronal": 0.0} for c in ligne["cotisations_detail"]]
            return ligne

        monkeypatch.setattr(module, "ligne_od_du_bulletin", sans_patronal)
    rapport = []
    module._corrections_directes("c1", "e1", 2026, 10, rapport)
    return rapport


def _echecs(rapport):
    return sorted({e for cas in rapport for e in cas.get("echecs", [])})


def test_le_moteur_juste_est_vert(script, monkeypatch):  # noqa: F811
    rapport = _jouer(script, monkeypatch, None)
    assert len(rapport) > 3
    assert [(c.get("code"), c.get("echecs")) for c in rapport if not c["ok"]] == []


@pytest.mark.parametrize(
    "mutant, constat",
    [
        ("E3", "residu_nul"),
        ("E4", "cotisations_suivent_le_brut"),
        ("E5", "reduction_suit"),
        ("E6", "impot_base_fois_taux"),
        ("E7", "net_imposable_suit"),
        ("E8", "mois_suivant"),
        ("E10", "compta_patronales"),
        ("E11", "net_social_suit"),
    ],
)
def test_chaque_erreur_injectee_rougit(script, monkeypatch, mutant, constat):  # noqa: F811
    assert constat in _echecs(_jouer(script, monkeypatch, mutant))
