"""Tableau des charges au format de Quadra : une ligne par cotisation et par taux, un
sous-total par caisse, l'impôt à la source par taux, le total général et l'effectif payé.

Demande d'Elsa du 03/11/2026 : l'export « Charges sociales par caisse » doit ressembler,
voire être identique, au « Tableau des charges » de Quadra (pièce : Comitech, août 2026).
"""

from __future__ import annotations

import pytest

from app.modules.exports.domain.tableau_des_charges import construire_tableau

pytestmark = pytest.mark.unit


def _ligne(coti_id, libelle, base, sal=0.0, pat=0.0, taux_sal=None, taux_pat=None):
    return {"coti_id": coti_id, "libelle": libelle, "base": base, "montant_salarial": sal,
            "montant_patronal": pat, "taux_salarial": taux_sal, "taux_patronal": taux_pat}


def _bulletin(lignes, pas=None, sexe="M", employee_id="e1"):
    return {"employee_id": employee_id, "cotisations_detail": lignes, "pas": pas, "sexe": sexe}


def test_deux_bulletins_au_meme_taux_font_une_ligne_qui_somme_base_et_montants():
    t = construire_tableau([
        _bulletin([_ligne("at_mp", "Accident du travail", 1000.0, pat=31.5)], employee_id="e1"),
        _bulletin([_ligne("at_mp", "Accident du travail", 2000.0, pat=63.0)], employee_id="e2"),
    ])
    urssaf = t.sections[0]
    assert urssaf.organisme == "URSSAF"
    [ligne] = urssaf.lignes
    assert (ligne.base, ligne.montant_patronal, ligne.montant_total) == (3000.0, 94.5, 94.5)
    assert ligne.taux_patronal == 3.15 and ligne.taux_total == 3.15


def test_meme_libelle_a_deux_taux_fait_deux_lignes():
    """Quadra sépare la maladie à 7 % et le complément à 6 % (libellés identiques au bulletin)."""
    t = construire_tableau([_bulletin([
        _ligne("securite_sociale_maladie", "Sécu.Soc-Mal.Mater.Inval.Déc.", 4822.55, pat=337.58),
        _ligne("securite_sociale_maladie", "Sécu.Soc-Mal.Mater.Inval.Déc.", 4822.55, pat=289.35),
    ])])
    taux = sorted(l.taux_patronal for l in t.sections[0].lignes)
    assert taux == [6.0, 7.0]


def test_part_salariale_et_patronale_sur_une_ligne():
    t = construire_tableau([_bulletin([
        # Le bulletin range les taux en fraction (0,069 pour 6,90 %).
        _ligne("vieillesse_plafonnee", "Vieillesse plafonnée", 1000.0, sal=69.0, pat=85.5, taux_sal=0.069, taux_pat=0.0855),
    ])])
    [l] = t.sections[0].lignes
    assert (l.taux_salarial, l.taux_patronal, l.taux_total) == (6.9, 8.55, 15.45)
    assert (l.montant_salarial, l.montant_patronal, l.montant_total) == (69.0, 85.5, 154.5)


def test_sous_totaux_par_caisse_dans_l_ordre_de_quadra_et_total_general():
    t = construire_tableau([_bulletin(
        [
            _ligne("mutuelle", "Mutuelle", 0.0, sal=35.24, pat=40.0),
            _ligne("retraite_comp_t1", "Retraite T1", 1000.0, sal=31.5, pat=47.2),
            _ligne("at_mp", "Accident du travail", 1000.0, pat=31.5),
        ],
        pas={"base": 900.0, "taux": 2.2, "montant": 19.8},
    )])
    assert [s.organisme for s in t.sections] == ["URSSAF", "RETRAITE", "DGFIP", "MUTUELLE"]
    assert [(s.salarial, s.patronal) for s in t.sections] == [(0.0, 31.5), (31.5, 47.2), (19.8, 0.0), (35.24, 40.0)]
    assert (t.salarial, t.patronal, t.total) == (86.54, 118.7, 205.24)


def test_l_impot_a_la_source_par_taux():
    t = construire_tableau([
        _bulletin([], pas={"base": 1428.54, "taux": 1.8, "montant": 25.71}, employee_id="e1"),
        _bulletin([], pas={"base": 3404.86, "taux": 4.5, "montant": 153.22}, employee_id="e2"),
        _bulletin([], pas={"base": 100.0, "taux": 1.8, "montant": 1.8}, employee_id="e3"),
        _bulletin([], pas={"base": 500.0, "taux": 0.0, "montant": 0.0}, employee_id="e4"),
    ])
    [dgfip] = t.sections
    assert dgfip.organisme == "DGFIP"
    assert [(l.taux_salarial, l.base, l.montant_salarial) for l in dgfip.lignes] == [(1.8, 1528.54, 27.51), (4.5, 3404.86, 153.22)]


def test_une_ligne_a_zero_n_apparait_pas_et_une_reduction_se_lit_comme_chez_quadra():
    """Quadra : « REDUCTION GENERALE  base 5725.81  taux 100.0000-  montant 5725.81- ». Le
    bulletin repris porte la base en négatif ; la part retraite est ventilée à part."""
    t = construire_tableau([_bulletin([
        _ligne("fnal", "FNAL", 1000.0, pat=0.0),
        _ligne("reduction_generale", "EXO., ECRET. ET ALLEG. COTIS", -6660.4, pat=-5654.9),
    ])])
    [l] = t.sections[0].lignes
    assert (l.base, l.taux_patronal, l.montant_patronal) == (5654.9, -100.0, -5654.9)


def test_pas_de_taux_retrouve_pour_un_forfait_de_mutuelle_ni_pour_la_deduction_d_heures_sup():
    """La mutuelle est un forfait ; la déduction patronale d'heures sup a pour base des
    heures (1,50 € l'heure) : un « taux » retrouvé n'y voudrait rien dire."""
    t = construire_tableau([_bulletin([
        _ligne("mutuelle", "GAN MUTUELLE ISOLE", 350.88, sal=350.88, pat=350.76),
        _ligne("deduction_hs_patronale", "REDUCT HEURES SUPPL.", 173.0, pat=-259.55),
    ])])
    lignes = [l for s in t.sections for l in s.lignes]
    assert all(l.taux_salarial is None and l.taux_patronal is None for l in lignes)


def test_effectif_paye_femmes_et_hommes():
    t = construire_tableau([
        _bulletin([], sexe="F", employee_id="e1"),
        _bulletin([], sexe="M", employee_id="e2"),
        _bulletin([], sexe="M", employee_id="e2"),  # deux bulletins (deux contrats) : un salarié
        _bulletin([], sexe=None, employee_id="e3"),
    ])
    assert (t.payes, t.femmes, t.hommes) == (3, 1, 1)


def test_la_feuille_porte_le_titre_les_sous_totaux_et_l_effectif():
    from datetime import datetime

    from openpyxl import Workbook

    from app.modules.exports.infrastructure.export_tableau_des_charges import ecrire_tableau_des_charges

    t = construire_tableau([_bulletin(
        [_ligne("at_mp", "Accident du travail", 1000.0, pat=31.5),
         _ligne("retraite_comp_t1", "Retraite T1", 1000.0, sal=31.5, pat=47.2)],
        pas={"base": 900.0, "taux": 2.2, "montant": 19.8}, sexe="F",
    )])
    wb = Workbook()
    ecrire_tableau_des_charges(wb.active, t, "2026-08", {"company_name": "SOCIÉTÉ"}, datetime(2026, 9, 9, 13, 52))
    valeurs = [tuple(r) for r in wb.active.iter_rows(values_only=True)]
    textes = [str(v) for r in valeurs for v in r if v is not None]
    assert "TABLEAU DES CHARGES DE 08/26 - En Euros" in textes
    assert "Le : 09/09/2026 à 13:52" in textes
    total_general = next(r for r in valeurs if r[0] == ">>>> TOTAUX GÉNÉRAUX")
    assert total_general[4:9] == (130.0, None, 51.3, None, 78.7)
    assert any(str(r[0]).startswith(">>>> URSSAF") for r in valeurs)
    assert "Employés payés sur la période : 1 (Femmes : 1 Hommes : 0)" in textes


def test_un_taux_imprime_suffit_a_regrouper_malgre_l_arrondi_de_l_autre_part():
    """Prévoyance non cadre : part salariale imprimée à 0,465 %, part patronale retrouvée
    (83,95 / 18 059,04 = 0,4649 ; 35,75 / 7 685,20 = 0,4652) : une seule ligne."""
    t = construire_tableau([
        _bulletin([_ligne("prevoyance_non_cadre", "PREVOYANCE NON CADRE TA", 18059.04, sal=83.95, pat=83.95, taux_sal=0.00465)], employee_id="e1"),
        _bulletin([_ligne("prevoyance_non_cadre", "PREVOYANCE NON CADRE TA", 7685.20, sal=35.75, pat=35.75, taux_sal=0.00465)], employee_id="e2"),
    ])
    [l] = t.sections[0].lignes
    assert (l.base, l.taux_salarial, l.montant_patronal) == (25744.24, 0.465, 119.7)


def test_la_mutuelle_n_a_jamais_de_taux_meme_imprime():
    t = construire_tableau([_bulletin([_ligne("mutuelle", "GAN MUTUELLE ISOLE", 350.88, sal=350.88, pat=350.76, taux_sal=0.01)])])
    [l] = t.sections[0].lignes
    assert (l.taux_salarial, l.taux_patronal, l.taux_total) == (None, None, None)


def test_la_reduction_generale_calculee_par_martine_fait_une_seule_ligne():
    """Martine imprime le coefficient de chaque salarié comme taux : une ligne par salarié.
    Quadra n'en fait qu'une : base = montant, taux −100 %."""
    t = construire_tableau([
        _bulletin([_ligne("reduction_generale", "Réduction générale de cotisations", 1793.0, pat=-43.74, taux_pat=0.0244)], employee_id="e1"),
        _bulletin([_ligne("reduction_generale", "Réduction générale de cotisations", 1871.6, pat=-423.72, taux_pat=0.2264)], employee_id="e2"),
    ])
    [l] = t.sections[0].lignes
    assert (l.base, l.taux_patronal, l.montant_patronal) == (467.46, -100.0, -467.46)
