"""Chaque ligne d'un bulletin a un code stable, lu sur la ligne elle-même.

Une correction vise une ligne par ce code. Il n'est pas stocké : un bulletin
sans correction reste identique, et un bulletin d'avant se corrige aussi. Un
libellé écrit dans un producteur de lignes sans code ferait échouer le test du
théorème : on l'attrape ici d'abord.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
from app.modules.payroll.engine import (
    calcul_brut,
    calcul_brut_forfait,
    indemnites_sortie_brut,
    regime_indemnites_rupture,
    salary_evolution_brut,
)
from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    RAISON_HORS_SALAIRE,
    RAISON_INCONNUE,
    RAISON_INFORMATION,
    RAISON_REGULARISATION,
    RAISON_SAISIE,
    RAISON_SOUS_TOTAL,
    Numerotation,
    champ_du_montant,
    code_de_ligne,
    famille_du_code,
    mode_de_correction,
    numeroter,
    slug,
)

pytestmark = pytest.mark.unit


def _gain(libelle, **champs):
    return {"libelle": libelle, "quantite": None, "taux": None, "gain": None, "perte": None, **champs}


@pytest.mark.parametrize(
    "ligne, code",
    [
        (_gain("Salaire de base", quantite=151.67, taux=16.4832, gain=2500.0), "brut:salaire_base"),
        (_gain("Salaire de base (forfait jour)", gain=3608.0), "brut:salaire_base"),
        (_gain("Heures suppl. structurelles majorées à 25%", quantite=17.33, taux=15.31, gain=265.37), "brut:hs_structurelles"),
        (_gain("Heures suppl. majorées à 25%", quantite=4.0, taux=20.6039, gain=82.42), "brut:heures_sup:25"),
        (_gain("Heures suppl. majorées à 50%", quantite=2.0, taux=24.72, gain=49.44), "brut:heures_sup:50"),
        (_gain("Heures complémentaires majorées à 10%", quantite=3.0, taux=18.1, gain=54.3), "brut:heures_complementaires:10"),
        (_gain("SOUS-TOTAL SALAIRE CONTRACTUEL", quantite=169.0, gain=2123.38, is_sous_total=True), "brut:sous_total"),
        (_gain("Absence pour entrée ou sortie", quantite=14.0, taux=16.48, perte=230.72), "brut:absence_entree_sortie"),
        (_gain("Absence injustifiée du 21/01/26 (base)", quantite=3.5, taux=16.4832, perte=57.69), "brut:absence_injustifiee:du-21-01-26-base"),
        (_gain("Absence injustifiée (2 jours)", quantite=2.0, taux=166.5, perte=333.0), "brut:absence_injustifiee:2-jours"),
        (_gain("Absence non rémunérée du 16/03/26 (1 jour)", quantite=1.0, taux=166.4975, perte=166.5), "brut:absence_non_remuneree:16-03-26-1-jour"),
        (_gain("Absence événement familial du 10/03/26", quantite=7.0, taux=16.48, perte=115.36), "brut:absence_evenement_familial:10-03-26"),
        (_gain("Abs. jour férié non payé du 11/11/26", quantite=7.0, taux=16.48, perte=115.36), "brut:absence_ferie_non_paye:11-11-26"),
        (_gain("Absence maladie du 03/09 au 05/09", quantite=21.0, taux=16.48, perte=346.08, is_arret_maladie=True), "brut:arret:absence-maladie-du-03-09-au-05-09"),
        (_gain("Absence maladie du 16/03/26", quantite=1.0, taux=164.0, perte=164.0), "brut:absence_maladie:16-03-26"),
        (_gain("Réduction HS structurelles (jours d'absence)", quantite=0.36, taux=15.31, perte=5.51), "brut:reduction_hs_absence"),
        (_gain("Réduction HS structurelles (événement familial)", quantite=2.4, taux=15.31, perte=36.74), "brut:reduction_hs_evenement_familial"),
        (_gain("Maintien de salaire (événement familial)", gain=151.0), "brut:maintien_evenement_familial"),
        (_gain("Complément retenue absence intégrale du mois (fériés et repos)", perte=80.0), "brut:complement_absence_integrale"),
        (_gain("Retenue absence intégrale du mois limitée au salaire mensuel", gain=-12.0), "brut:retenue_absence_integrale"),
        (_gain("Absence sur tout le mois : retenue ramenée au salaire du mois", perte=10.0), "brut:retenue_absence_mois_complet"),
        (_gain("Lissage modulation", gain=10.0), "brut:lissage_modulation"),
        (_gain("Absence congés payés (3 jours : du 01/09 au 03/09)", quantite=21.0, perte=346.0), "brut:absence_conges_payes"),
        (_gain("Indemnité de congés payés (partie base)", quantite=21.0, taux=16.48, gain=346.08), "brut:indemnite_conges_payes:partie-base"),
        (_gain("Indemnité de congés payés (partie HS 25%)", quantite=2.4, taux=20.6, gain=49.44), "brut:indemnite_conges_payes:partie-hs-25"),
        (_gain("Indemnité de congés payés (règle du 1/10ème)", gain=400.0), "brut:indemnite_conges_payes:regle-du-1-10eme"),
        (_gain("Indemnité compensatrice de congés payés (CDD)", taux=0.1, gain=1210.0), "brut:iccp:cdd"),
        (_gain("Indemnité compensatrice de congés payés", taux=0.1, gain=300.0), "brut:iccp"),
        (_gain("Indemnité compensatrice de préavis", gain=2500.0, is_indemnite_sortie=True), "brut:indemnite_sortie:indemnite-compensatrice-de-preavis"),
        (_gain("Prime de précarité (CDD)", taux=0.1, gain=1100.0), "brut:precarite"),
        (_gain("Indemnité de fin de mission (intérim)", taux=0.1, gain=250.0), "brut:ifm"),
        (_gain("Avantages en nature", gain=120.0), "brut:avantages_en_nature"),
        (_gain("Rappel de salaire (période du 01/09 au 30/09)", gain=50.0), "brut:rappel_salaire:periode-du-01-09-au-30-09"),
        (_gain("Rappel de salaire", gain=50.0), "brut:rappel_salaire"),
        (_gain("Réintégration NDF Repas", gain=3.0), "brut:reintegration:ndf-repas"),
        (_gain("Prime d'ancienneté", quantite=2000.0, taux=0.03, gain=60.0, meta={"plein_mois": 60.0}), "brut:prime_anciennete"),
        # Telle qu'elle arrive au bulletin : `calcul_brut` retire son `meta`.
        (_gain("Prime d'ancienneté (5 ans, 2,4 %)", quantite=2289.38, taux=0.024002, gain=54.95), "brut:prime_anciennete"),
        (_gain("Prime d'ancienneté métallurgie (classe 7, 6 ans)", quantite=2000.0, taux=0.06, gain=120.0), "brut:prime_anciennete"),
        (_gain("Prime exceptionnelle", gain=100.0, saisie_id="s-1"), "brut:saisie:s-1"),
        (_gain("Prime de fin d'année", gain=100.0), "brut:prime:prime-de-fin-d-annee"),
        (_gain("Heures de nuit majorées à 50%", quantite=10.0, taux=24.72, gain=82.42), "brut:heures_nuit"),
        (_gain("Pause rémunérée (planning)", quantite=5.0, taux=16.48, gain=82.42), "brut:pause_remuneree"),
        (_gain("Maintien de salaire employeur", gain=300.0, is_maintien_employeur=True), "brut:maintien_employeur"),
        (_gain("HS reportées au compte modulation", quantite=3.0, is_informative=True), "brut:information:hs-reportees-au-compte-modulation"),
    ],
)
def test_chaque_ligne_de_gain_a_son_code(ligne, code):
    assert code_de_ligne(BLOC_BRUT, ligne) == code


@pytest.mark.parametrize(
    "ligne, code",
    [
        ({"coti_id": "securite_sociale_maladie", "libelle": "Maladie, maternité, invalidité, décès"}, "cotisation:securite_sociale_maladie"),
        ({"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS non déductible"}, "cotisation:csg_non_deductible:csg-crds-non-deductible"),
        ({"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS sur HS non déductible"}, "cotisation:csg_non_deductible:csg-crds-sur-hs-non-deductible"),
        ({"coti_id": "forfait_social", "libelle": "Forfait social 8% sur prévoyance"}, "cotisation:forfait_social:forfait-social-8-sur-prevoyance"),
        ({"coti_id": "mutuelle", "libelle": "Mutuelle Frais de Santé"}, "cotisation:mutuelle:mutuelle-frais-de-sante"),
        ({"libelle": "CSG déductible IJSS", "base": 300.0, "taux_salarial": 0.038}, "cotisation:sans_organisme:csg-deductible-ijss"),
        ({"libelle": "CSG déductible — Participation", "is_participation": True}, "cotisation:sans_organisme:csg-deductible-participation"),
        ({"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales"}, "cotisation:reduction_generale"),
        ({"coti_id": "mutuelle", "libelle": "Régularisation – Mutuelle", "regularisation": {"saisie_id": "s1"}}, "cotisation:regularisation:s1"),
        ({"libelle": ""}, None),
    ],
)
def test_chaque_cotisation_a_son_code(ligne, code):
    assert code_de_ligne(BLOC_COTISATIONS, ligne) == code


def test_l_impot_a_son_code():
    assert code_de_ligne(BLOC_IMPOT, {"base": 2000.0, "taux": 5.2, "montant": 104.0}) == CODE_IMPOT == "impot"


def test_une_ligne_que_l_inventaire_ne_connait_pas_n_a_pas_de_code():
    assert code_de_ligne(BLOC_BRUT, _gain("Ligne inventée", quantite=1.0, taux=2.0, perte=2.0)) is None
    assert mode_de_correction(BLOC_BRUT, {}, None) == (None, RAISON_INCONNUE)


def test_le_slug_et_la_famille():
    assert slug("Absence du 12/09/26 (règle)") == "absence-du-12-09-26-regle"
    assert famille_du_code("brut:heures_sup:25#2") == "brut:heures_sup"
    assert famille_du_code("cotisation:mutuelle:gan-sante") == "cotisation:mutuelle"
    assert famille_du_code("impot") == "impot"
    assert famille_du_code(None) == ""


def test_deux_lignes_de_meme_code_sont_numerotees_dans_leur_ordre():
    assert numeroter(["a", "b", "a", None, "a"]) == ["a", "b", "a#2", None, "a#3"]
    numeros = Numerotation()
    ligne = {"coti_id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée"}
    assert numeros.code(BLOC_COTISATIONS, ligne) == "cotisation:vieillesse_deplafonnee"
    assert numeros.code(BLOC_COTISATIONS, dict(ligne)) == "cotisation:vieillesse_deplafonnee#2"


def test_le_montant_d_une_retenue_est_sa_perte():
    assert champ_du_montant(_gain("Absence", quantite=1.0, taux=2.0, perte=2.0)) == "perte"
    assert champ_du_montant(_gain("Prime", gain=2.0)) == "gain"


@pytest.mark.parametrize(
    "bloc, ligne, attendu",
    [
        (BLOC_BRUT, _gain("Salaire de base", quantite=151.67, taux=16.48, gain=2500.0), (MODE_BASE_OU_TAUX, None)),
        (BLOC_BRUT, _gain("Absence non rémunérée du 16/03/26", quantite=7.0, taux=16.48, perte=115.36), (MODE_BASE_OU_TAUX, None)),
        # Un taux sans quantité (précarité) : le montant seul.
        (BLOC_BRUT, _gain("Prime de précarité (CDD)", taux=0.1, gain=1100.0), (MODE_MONTANT, None)),
        (BLOC_BRUT, _gain("Prime exceptionnelle", gain=100.0, saisie_id="s-1"), (None, RAISON_SAISIE)),
        (BLOC_BRUT, _gain("SOUS-TOTAL SALAIRE CONTRACTUEL", gain=1.0, is_sous_total=True), (None, RAISON_SOUS_TOTAL)),
        (BLOC_BRUT, _gain("HS reportées au compte modulation", is_informative=True), (None, RAISON_INFORMATION)),
        (BLOC_COTISATIONS, {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2000.0, "taux_salarial": 0.0, "taux_patronal": 0.07}, (MODE_BASE_OU_TAUX, None)),
        (BLOC_COTISATIONS, {"coti_id": "allocations_familiales", "libelle": "AF", "base": 2000.0, "taux_salarial": None, "taux_patronal": 0.0525}, (MODE_BASE_OU_TAUX, None)),
        # La réduction générale porte un coefficient cumulé, pas un taux du mois.
        (BLOC_COTISATIONS, {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales", "base": 2500.0, "taux_patronal": 0.1978}, (MODE_MONTANT, None)),
        (BLOC_COTISATIONS, {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None}, (MODE_MONTANT, None)),
        (BLOC_COTISATIONS, {"coti_id": "mutuelle", "libelle": "Régularisation – Mutuelle", "regularisation": {"saisie_id": "s1"}}, (None, RAISON_REGULARISATION)),
        (BLOC_COTISATIONS, {"libelle": "CSG déductible — Participation", "base": 100.0, "taux_salarial": 0.068, "is_participation": True}, (None, RAISON_HORS_SALAIRE)),
        (BLOC_IMPOT, {"base": 2000.0, "taux": 5.2}, (MODE_TAUX, None)),
    ],
)
def test_la_regle_3_dit_par_quoi_chaque_ligne_se_corrige(bloc, ligne, attendu):
    assert mode_de_correction(bloc, ligne, code_de_ligne(bloc, ligne)) == attendu


def _lignes_ecrites(module) -> list[dict]:
    """Les lignes de gain écrites en dur dans un producteur : libellé (parties
    variables remplacées par « 25 »), et drapeaux posés à True."""
    lignes = []
    for noeud in ast.walk(ast.parse(inspect.getsource(module))):
        if not isinstance(noeud, ast.Dict):
            continue
        cles = {c.value: v for c, v in zip(noeud.keys, noeud.values) if isinstance(c, ast.Constant)}
        if "libelle" not in cles or not ({"gain", "perte"} & cles.keys()):
            continue
        valeur = cles["libelle"]
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            libelle = valeur.value
        elif isinstance(valeur, ast.JoinedStr):
            libelle = "".join(p.value if isinstance(p, ast.Constant) else "25" for p in valeur.values)
        else:
            continue  # libellé calculé : couvert par le test paramétré et le test du théorème
        drapeaux = {
            cle: True
            for cle, v in cles.items()
            if str(cle).startswith("is_") and isinstance(v, ast.Constant) and v.value is True
        }
        lignes.append({"libelle": libelle, "quantite": 1.0, "taux": 1.0, "perte": 1.0, **drapeaux})
    return lignes


PRODUCTEURS_DE_GAINS = [
    calcul_brut,
    calcul_brut_forfait,
    indemnites_sortie_brut,
    regime_indemnites_rupture,
    salary_evolution_brut,
    payslip_run_heures,
    payslip_run_forfait,
]


@pytest.mark.parametrize("module", PRODUCTEURS_DE_GAINS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_chaque_libelle_ecrit_dans_un_producteur_de_gains_a_un_code(module):
    """Un nouveau type de ligne n'entre pas sans sa correction (spec § 9)."""
    inconnues = [l["libelle"] for l in _lignes_ecrites(module) if code_de_ligne(BLOC_BRUT, l) is None]
    assert inconnues == []
