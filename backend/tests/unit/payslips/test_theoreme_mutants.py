"""Le test du théorème rougit quand le calcul est faux (R-180, § 2.8 et § 3.5 de la relecture 6).

Il comparait deux calculs entre eux : huit erreurs injectées sur onze restaient
vertes. Ici, un petit moteur en mémoire (salaire, cotisations, réduction par la
formule du registre, impôt, prime non soumise, compteur) tourne juste, et chaque
erreur injectée (`scripts/theoreme_mutants.py`) doit faire rougir un constat du
script : valeur attendue calculée à part, jamais le seul mouvement entre deux
calculs.

Ce test prouve que les assertions rougissent ; le passage sur les vrais bulletins,
par société, est `scripts/theoreme_sept_societes.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, BLOC_COTISATIONS, Numerotation
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    JournalDesCorrections,
    corriger_le_taux_d_impot,
    poser_les_corrections_en_attente,
)
from tests.unit.payslips.test_theoreme_script import FauxSupabase, script  # noqa: F401 — la fixture
from theoreme_mutants import ERREURS_DU_REGISTRE, MUTANTS
from verification_rgdu.oracle import Parametres, reduction_cumulee
from verification_rgdu.oracle_smic import SMIC_H_2026

pytestmark = pytest.mark.unit

SALAIRE_DE_DEPART = 2426.72
BRUT_ANTERIEUR, HEURES_ANTERIEURES, REDUCTION_ANTERIEURE = 20000.0, 1365.03, -2000.0
CUMULS_AVANT = {
    "brut_total": BRUT_ANTERIEUR,
    "brut_annee_civile": BRUT_ANTERIEUR,
    "net_imposable": 16000.0,
    "impot_preleve_a_la_source": 800.0,
    "reduction_generale_patronale": REDUCTION_ANTERIEURE,
    "heures_remunerees": HEURES_ANTERIEURES,
}


def _cotisation(coti_id, libelle, base, taux_salarial=None, taux_patronal=None, patronal=None):
    ligne = {"coti_id": coti_id, "libelle": libelle, "base": base, "taux_salarial": taux_salarial, "taux_patronal": taux_patronal}
    ligne["montant_salarial"] = round(base * taux_salarial, 2) if taux_salarial is not None else 0.0
    ligne["montant_patronal"] = patronal if patronal is not None else (round(base * taux_patronal, 2) if taux_patronal is not None else 0.0)
    return ligne


def _reduction(brut: float, heures: float, cumuls_avant: dict) -> float:
    """Le moteur juste : la formule du registre (`verification_rgdu.oracle`), hors du moteur de paie."""
    b = float(cumuls_avant.get("brut_annee_civile") or 0.0) + brut
    h = float(cumuls_avant.get("heures_remunerees") or 0.0) + heures
    deja = abs(float(cumuls_avant.get("reduction_generale_patronale") or 0.0))
    return -round(reduction_cumulee(b, round(SMIC_H_2026 * h, 2), Parametres(tdelta=0.3781)) - deja, 2)


def _bulletin(saisies, cumuls_avant, mois, gains_en_plus=(), heures_sup_en_plus=0.0):
    journal = JournalDesCorrections(
        CorrectionDeLigne.depuis(s["correction_ligne"], saisie_id=s["id"]) for s in saisies if s.get("correction_ligne")
    )
    salaire = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.0, "gain": SALAIRE_DE_DEPART, "perte": None}
    journal.corriger(salaire, "brut", "brut:salaire_base")
    numeros_brut = Numerotation()
    extras = []
    heures_supplementaires = heures_sup_en_plus
    for source in gains_en_plus:
        ligne = dict(source)
        journal.corriger(ligne, BLOC_BRUT, numeros_brut.code(BLOC_BRUT, ligne))
        extras.append(ligne)
        if "Heures" in str(ligne.get("libelle")) and ligne.get("quantite") is not None:
            heures_supplementaires += float(ligne["quantite"])
    brut = round(float(salaire["gain"]) + sum(float(l.get("gain") or 0.0) - float(l.get("perte") or 0.0) for l in extras), 2)
    avantages = sum(float(l.get("gain") or 0.0) for l in extras if l.get("libelle") == "Avantages en nature")
    heures = float(salaire["quantite"]) + heures_supplementaires
    lignes = [
        _cotisation("vieillesse_deplafonnee", "Vieillesse déplafonnée", brut, 0.004, 0.019),
        _cotisation("csg_deductible", "CSG déductible", round(brut * 0.9825, 2), 0.068),
        _cotisation("csg_non_deductible", "CSG/CRDS non déductible", round(brut * 0.9825, 2), 0.029),
        _cotisation("mutuelle", "Mutuelle santé", None, patronal=20.0),
        _cotisation("mutuelle", "Mutuelle santé", None, patronal=10.0),
        _cotisation("reduction_generale", "Réduction générale de cotisations patronales", brut, patronal=_reduction(brut, heures, cumuls_avant)),
    ]
    numeros = Numerotation()
    for ligne in lignes:
        journal.corriger(ligne, BLOC_COTISATIONS, numeros.code(BLOC_COTISATIONS, ligne))
    salarial = round(sum(l["montant_salarial"] for l in lignes), 2)
    patronal = round(sum(l["montant_patronal"] for l in lignes), 2)
    non_deductible = sum(l["montant_salarial"] for l in lignes if l["coti_id"] in ("csg_non_deductible", "crds"))
    net_imposable = round(brut - (salarial - non_deductible), 2)
    taux, trace = corriger_le_taux_d_impot(5.0, net_imposable, journal)
    impot = round(net_imposable * taux / 100, 2)
    prime = 50.0
    net = round(brut - salarial - impot + prime - avantages, 2)
    data = {
        "salaire_brut": brut,
        "calcul_du_brut": [salaire, *extras],
        "details_conges": [],
        "details_absences": [],
        "cotisations_officielles": [{"code": "sante", "lignes": lignes, "total_salarial": salarial, "total_patronal": patronal}],
        "structure_cotisations": {"bloc_principales": lignes, "total_salarial": salarial, "total_patronal": patronal},
        "primes_non_soumises": [{"libelle": "Prime de transport", "montant": prime}],
        "synthese_net": {
            "net_imposable": net_imposable,
            "montant_net_social": round(brut - salarial, 2),
            "impot_prelevement_a_la_source": {"base": net_imposable, "taux": taux, "montant": impot, **(trace or {})},
            **({"avantages_en_nature": avantages} if avantages else {}),
        },
        "net_a_payer": net,
        "pied_de_page": {"solde_conges": {"acquis": 2.08, "pris": 0.0}, "cout_total_employeur": round(brut + patronal, 2)},
    }
    poser_les_corrections_en_attente(data, journal)

    def _cumul(cle, valeur):
        return round(float(cumuls_avant.get(cle) or 0.0) + valeur, 2)

    cumuls = {
        "brut_total": _cumul("brut_total", brut),
        "brut_annee_civile": _cumul("brut_annee_civile", brut),
        "net_imposable": _cumul("net_imposable", net_imposable),
        "impot_preleve_a_la_source": _cumul("impot_preleve_a_la_source", impot),
        "reduction_generale_patronale": _cumul("reduction_generale_patronale", lignes[-1]["montant_patronal"]),
        "heures_remunerees": _cumul("heures_remunerees", heures),
        "heures_supplementaires_remunerees": _cumul("heures_supplementaires_remunerees", heures_supplementaires),
    }
    return {"payslip_data": data, "cumuls": {"cumuls": cumuls}}


def _jouer(module, monkeypatch, mutants):
    def generer(employee_id, year, month, cumuls, saisies_en_plus=()):
        precedents = (cumuls or {}).get("cumuls", cumuls or {}) if isinstance(cumuls, dict) else {}
        return _bulletin(saisies_en_plus, precedents, month)

    monkeypatch.setattr(module, "_generer_moteur", generer)
    monkeypatch.setattr(module, "_cumuls_precedents", lambda *a, **k: dict(CUMULS_AVANT))
    monkeypatch.setattr(module, "supabase", FauxSupabase(employees=[{"id": "e1"}]))
    return module.jouer_mutants("c1", "e1", 2026, 10, tuple(mutants), avec_regularisations=False)


def test_le_moteur_juste_est_vert(script, monkeypatch):  # noqa: F811
    resultat = _jouer(script, monkeypatch, [])
    assert resultat["cas_de_reference"] > 3
    assert resultat["rouges_sans_mutant"] == []


@pytest.mark.parametrize("mutant", MUTANTS, ids=[m.nom for m in MUTANTS])
def test_chaque_erreur_injectee_rougit(script, monkeypatch, mutant):  # noqa: F811
    resultat = _jouer(script, monkeypatch, [mutant])["mutants"][mutant.nom]
    assert resultat["verdict"] == "vu", resultat
    assert resultat["attendus_vus"], resultat


def test_les_onze_erreurs_du_registre_sont_dans_la_suite():
    assert set(ERREURS_DU_REGISTRE) <= {m.nom for m in MUTANTS}
    assert len(ERREURS_DU_REGISTRE) == 11


def test_une_injection_sans_effet_ne_compte_pas_pour_vue_et_le_dit(script, monkeypatch):  # noqa: F811
    from theoreme_mutants import Mutant

    rien = Mutant(nom="RIEN", quoi="ne change rien", constats=frozenset({"residu_nul"}), bulletin=lambda res, ctx: None)
    resultat = _jouer(script, monkeypatch, [rien])["mutants"]["RIEN"]
    assert resultat["verdict"] == "sans effet"
    assert resultat["effet"] is False


def test_une_injection_qui_change_tout_sans_constat_est_dite_non_vue(script, monkeypatch):  # noqa: F811
    from theoreme_mutants import Mutant

    def discrete(res, ctx):
        res["payslip_data"]["champ_que_personne_ne_lit"] = 1

    fantome = Mutant(nom="FANTOME", quoi="change un champ muet", constats=frozenset({"residu_nul"}), bulletin=discrete)
    resultat = _jouer(script, monkeypatch, [fantome])["mutants"]["FANTOME"]
    assert resultat["verdict"] == "NON VU"


#: Ce que la revue doit voir d'une erreur posée sur un bulletin juste (R-170).
REVUE_ATTENDUE = {
    "net à payer +100": True,
    "impôt +100": True,
    "cotisation doublée": True,
    "brut +100": True,
    "réduction doublée": True,
}


def _revue(mini_data):
    from app.modules.payslips.domain.anomalies_bulletin import anomalies_du_bulletin
    from theoreme_mutants import revue_contre_les_erreurs

    return revue_contre_les_erreurs(mini_data, anomalies_du_bulletin)


def _bulletin_juste_pour_la_revue():
    data = _bulletin((), dict(CUMULS_AVANT), 10)["payslip_data"]
    data["synthese_net"]["net_social_avant_impot"] = round(data["net_a_payer"] + data["synthese_net"]["impot_prelevement_a_la_source"]["montant"], 2)
    return data


@pytest.mark.parametrize("erreur", sorted(REVUE_ATTENDUE))
def test_la_revue_voit_l_erreur_d_un_bulletin_juste(erreur):
    assert _revue(_bulletin_juste_pour_la_revue())[erreur], erreur


@pytest.mark.parametrize(
    "erreur",
    ["net imposable +100", "net social +100", "cumul brut faux", "coût employeur +100"],
)
@pytest.mark.xfail(
    strict=True,
    reason="R-170 : les règles B ne relisent ni net imposable, ni net social, ni cumuls, ni coût employeur. "
    "Reste à faire (A14), avec filet : une nouvelle règle critique bloque la validation.",
)
def test_la_revue_voit_aussi(erreur):
    assert _revue(_bulletin_juste_pour_la_revue())[erreur], erreur
