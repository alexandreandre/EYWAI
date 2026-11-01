"""Exonération salariale de l'apprenti en DSN.

Fiche net-entreprises n° 831 « Modalités déclaratives pour les apprentis »
(mise à jour du 30/04/2026) : la part de rémunération exonérée (jusqu'à 50 %
du SMIC pour un contrat débutant depuis le 01/03/2025) se déclare
- au niveau du salarié : un code 001/002/003 (loi de 1979, 1987, 1992) sur les
  bases 02 et 03 avec l'assiette exonérée, la vieillesse (076) au seul taux
  patronal sur cette part et au taux plein au-delà, l'exonération de retraite
  complémentaire en 109, le 131 net de l'exonération ;
- au bordereau Urssaf : la part exonérée sur les CTP 726 (cotisations
  patronales de sécurité sociale) et 423 (assurance chômage), le reste sur les
  CTP 100 et 772.
C'est aussi ce que déclarait Quadra (DSN de septembre 2026 d'un apprenti).
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.agregats import bordereau_urssaf
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations

pytestmark = pytest.mark.unit

BRUT = 1152.16
EXONERE = 933.51  # 50 % du SMIC du mois

LIGNES_APPRENTI = [
    {"coti_id": "retraite_secu_plafond", "libelle": "Sécurité sociale Vieillesse plafonnée", "base": BRUT,
     "montant_salarial": 79.50, "montant_patronal": 98.51, "taux_salarial": 0.069, "taux_patronal": 0.0855},
    {"coti_id": "retraite_secu_deplafond", "libelle": "Sécurité sociale Vieillesse déplafonnée", "base": BRUT,
     "montant_salarial": 4.61, "montant_patronal": 24.31, "taux_salarial": 0.004, "taux_patronal": 0.0211},
    {"coti_id": "retraite_comp_t1", "libelle": "Retraite Complémentaire Tranche 1 (AGIRC-ARRCO)", "base": BRUT,
     "montant_salarial": 36.29, "montant_patronal": 54.38, "taux_salarial": 0.0315, "taux_patronal": 0.0472},
    {"coti_id": "ceg_t1", "libelle": "Contribution d'Équilibre Général (CEG) T1", "base": BRUT,
     "montant_salarial": 9.91, "montant_patronal": 14.86, "taux_salarial": 0.0086, "taux_patronal": 0.0129},
    {"coti_id": "exoneration_apprenti_salariale", "libelle": "Exonération cotisations salariales apprenti",
     "base": EXONERE, "montant_salarial": -105.58, "montant_patronal": 0.0},
    {"coti_id": "assurance_chomage", "libelle": "Assurance Chômage", "base": BRUT,
     "montant_salarial": 0.0, "montant_patronal": 46.09, "taux_patronal": 0.04},
]


def _construire(code_exoneration="002"):
    bases, cotisations, avertissements = build_bases_and_cotisations(
        LIGNES_APPRENTI, brut=BRUT, period_start="01102026", period_end="31102026",
        default_ops="OPS-URSSAF", code_exoneration_apprenti=code_exoneration,
    )
    par_base: dict[str, list[dict]] = {}
    for c in cotisations:
        r = c.rubriques
        par_base.setdefault(r["_base"], []).append(
            {k: r.get(k) for k in ("S21.G00.81.001", "S21.G00.81.002", "S21.G00.81.003",
                                   "S21.G00.81.004", "S21.G00.81.007", "_apprenti")}
        )
    return {b.code: b.montant for b in bases}, par_base, avertissements


def _codes(lignes, code):
    return [l for l in lignes if l["S21.G00.81.001"] == code]


def test_la_vieillesse_plafonnee_se_scinde_a_l_assiette_exoneree():
    _, par_base, _ = _construire()
    vieillesse = sorted(
        (l["S21.G00.81.003"], l["S21.G00.81.004"], l["S21.G00.81.007"]) for l in _codes(par_base["02"], "076")
    )
    assert vieillesse == [("218.65", "33.78", "15.450"), ("933.51", "79.82", "8.550")]


def test_la_vieillesse_deplafonnee_se_scinde_aussi():
    _, par_base, _ = _construire()
    vieillesse = sorted(
        (l["S21.G00.81.003"], l["S21.G00.81.004"], l["S21.G00.81.007"]) for l in _codes(par_base["03"], "076")
    )
    assert vieillesse == [("218.65", "5.49", "2.510"), ("933.51", "19.70", "2.110")]


def test_l_exoneration_loi_de_1987_porte_l_assiette_exoneree_sur_les_deux_bases():
    _, par_base, _ = _construire()
    for base in ("02", "03"):
        (exo,) = _codes(par_base[base], "002")
        assert (exo["S21.G00.81.002"], exo["S21.G00.81.003"], exo["S21.G00.81.004"]) == (
            "OPS-URSSAF", "933.51", "0.00")


def test_la_retraite_complementaire_est_nette_de_l_exoneration():
    _, par_base, _ = _construire()
    (agirc,) = _codes(par_base["02"], "131")
    assert agirc["S21.G00.81.004"] == "78.00"  # 115,44 − 29,41 − 8,03
    (exo,) = _codes(par_base["03"], "109")
    assert (exo["S21.G00.81.002"], exo["S21.G00.81.003"], exo["S21.G00.81.004"]) == (None, "933.51", "0.00")


def test_les_bases_gardent_le_brut_entier_et_rien_n_est_ignore():
    montants, _, avertissements = _construire()
    assert montants["02"] == BRUT and montants["03"] == BRUT
    assert not any("apprenti" in a.lower() for a in avertissements)


def test_sans_dispositif_l_exoneration_est_signalee_et_rien_ne_se_scinde():
    _, par_base, avertissements = _construire(code_exoneration=None)
    assert len(_codes(par_base["02"], "076")) == 1
    assert any("apprenti" in a.lower() for a in avertissements)


def _salarie_urssaf():
    _, par_base, _ = _construire()
    lignes = []
    for base, cotisations in par_base.items():
        for l in cotisations:
            if l["S21.G00.81.002"] != "OPS-URSSAF":
                continue
            lignes.append({"code": l["S21.G00.81.001"], "base": base,
                           "assiette": float(l["S21.G00.81.003"] or 0), "montant": float(l["S21.G00.81.004"]),
                           "taux": float(l["S21.G00.81.007"]), "apprenti": l["_apprenti"] or ""})
    lignes.append({"code": "075", "base": "03", "assiette": BRUT, "montant": 80.65, "taux": 7.0, "apprenti": ""})
    lignes.append({"code": "045", "base": "03", "assiette": BRUT, "montant": 36.29, "taux": 3.15, "apprenti": ""})
    return lignes


def test_le_bordereau_porte_la_part_exoneree_sur_les_ctp_726_et_423():
    lignes_23, total, inconnus = bordereau_urssaf([_salarie_urssaf()])
    ctp = {(l["ctp"], l["qualifiant"]): (l["assiette"], l["taux"]) for l in lignes_23}
    assert ctp[("726", "921")] == ("934.00", "")
    assert ctp[("726", "920")] == ("934.00", "3.15")
    assert ctp[("423", "920")] == ("934.00", "")
    assert ctp[("100", "921")] == ("219.00", "")
    assert ctp[("100", "920")] == ("219.00", "3.15")
    assert ctp[("772", "920")] == ("219.00", "")
    assert inconnus == []


def test_le_bordereau_ne_perd_ni_ne_cree_de_cotisation():
    lignes = _salarie_urssaf()
    _, total, _ = bordereau_urssaf([lignes])
    # Chaque CTP s'arrondit à l'euro : le total reste à moins d'un euro par CTP
    # de la somme des cotisations individuelles.
    # La part patronale Agirc-Arrco (142) ne sert qu'au contrôle de la réduction.
    assert abs(total - sum(l["montant"] for l in lignes if l["code"] != "142")) < 6


APPRENTI = {
    "id": "a1", "first_name": "Alix", "last_name": "IMAGINAIRE", "nir": "107010112345678", "sexe": "M",
    "date_naissance": "2007-01-15", "lieu_naissance": "LYON (69)",
    "adresse": {"rue": "2 rue Inventée", "ville": "LYON", "code_postal": "69002"},
    "hire_date": "2026-08-31", "contract_type": "Apprentissage", "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {"pcs": "674a", "idcc": "0292", "dispositif_politique_publique": "65"},
}


def test_le_contrat_d_apprentissage_declare_son_exoneration_et_la_range_au_bordereau():
    from app.modules.dsn_export.application.builder import (
        _cotisations_du_salarie,
        build_individu_from_payroll,
    )

    individu, _ = build_individu_from_payroll(
        APPRENTI,
        {"salaire_brut": BRUT, "synthese_net": {"net_imposable": 1000.0},
         "structure_cotisations": {"bloc_principales": LIGNES_APPRENTI}},
        period="2026-10", company_siret="49861035100015", default_ops="OPS-URSSAF",
    )
    (versement,) = individu.contrats[0].versements
    codes = [(c.rubriques.get("_base"), c.rubriques["S21.G00.81.001"]) for c in versement.cotisations_individuelles]
    assert ("02", "002") in codes and ("03", "002") in codes and ("03", "109") in codes
    lignes = _cotisations_du_salarie(individu)
    assert {l["apprenti"] for l in lignes if l["code"] == "076"} == {"exonere", "reste"}
