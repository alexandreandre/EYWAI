"""Reprise Cartol Industrie et LEWIS (métallurgie) : le programme de Mont Blanc réglé par société,
et ce que leurs bulletins Quadra ont de différent. Données fabriquées, aucun nom réel."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.reprise_comitech as rc
import scripts.reprise_mont_blanc as rmb
from scripts.backtest import colorplast_lignes_quadra as q
from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne

pytestmark = pytest.mark.unit


# --- Lecture des PDF ------------------------------------------------------------------------


def test_la_premiere_version_d_un_mois_n_est_pas_lue_quand_la_definitive_est_la(tmp_path, monkeypatch):
    """Septembre 2026 : Elsa a envoyé deux versions. LEWIS : `09-2026-lewis-premiere-version.pdf`
    passait avant `09-2026-lewis.pdf` dans l'ordre alphabétique ; la définitive fait foi."""
    dossier = tmp_path / "lewis" / "bulletins" / "2026-09"
    dossier.mkdir(parents=True)
    (dossier / "09-2026-lewis-premiere-version.pdf").write_bytes(b"%PDF")
    (dossier / "09-2026-lewis.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(q, "RACINE_DATA", tmp_path)
    assert q.pdf_du_mois(2026, 9, "lewis").name == "09-2026-lewis.pdf"
    (dossier / "09-2026-lewis.pdf").unlink()
    assert q.pdf_du_mois(2026, 9, "lewis").name == "09-2026-lewis-premiere-version.pdf"


def test_un_matricule_a_deux_mots_n_est_pas_tronque_chez_cartol_et_lewis():
    """« ESSAI » et « ESSAI AB » sont deux salariées (deux NIR) : tronqué au premier mot, le
    matricule les fusionnait dans un seul bulletin. Les autres sociétés gardent leur clé."""
    page = "   Matricule : ESSAI AB            NoSécu.: 299017500000145\n"
    assert q.matricule_de_la_page(page, "lewis") == "ESSAI AB"
    assert q.matricule_de_la_page(page, "cartol") == "ESSAI AB"
    assert q.matricule_de_la_page(page, "mbc") == "ESSAI"
    seul = "   Matricule : APPRENTI\n\n   Entré(e) le : 31/08/2026\n"
    assert q.matricule_de_la_page(seul, "cartol") == "APPRENTI"
    assert q.matricule_de_la_page("aucun en-tête", "cartol") is None


def test_deux_numeros_de_securite_sociale_sous_une_meme_cle_arretent_la_lecture(monkeypatch):
    """Garde-fou : un bulletin ne mélange jamais deux salariés."""
    pages = ["   Matricule : HOMONYME     NoSécu.: 1800175000001 12\n",
             "   Matricule : HOMONYME     NoSécu.: 2900175000002 34\n"]
    monkeypatch.setattr(q, "pdf_du_mois", lambda *a, **k: Path("x.pdf"))
    monkeypatch.setattr(q, "pages_texte", lambda _pdf: pages)
    with pytest.raises(ValueError, match="HOMONYME"):
        q.lire_bulletins(2026, 9, "mbc")


# --- Réglage par société --------------------------------------------------------------------


@pytest.fixture
def remise_en_etat():
    avant_rc = (rc.SOCIETE, rc.COMPANY_ID, rc._RGDU_TDELTA, rc._RGDU_TMAX)
    avant_rmb = (rmb.SOCIETE, rmb.COMPANY_ID, rmb.TDELTA)
    yield
    rc.SOCIETE, rc.COMPANY_ID, rc._RGDU_TDELTA, rc._RGDU_TMAX = avant_rc
    rmb.SOCIETE, rmb.COMPANY_ID, rmb.TDELTA = avant_rmb


def test_mont_blanc_reste_la_societe_par_defaut():
    assert rmb.SOCIETE == "mbc" and rmb.TDELTA == 0.3821
    assert rmb.COMPANY_ID == "b541df31-e964-485e-ac36-cf580633fd1d"


def test_lewis_moins_de_50_salaries_garde_le_tdelta_de_0_3781(remise_en_etat):
    rmb.regler_pour("lewis")
    assert (rmb.SOCIETE, rmb.TDELTA) == ("lewis", 0.3781)
    assert (rc.SOCIETE, rc.COMPANY_ID, rc._RGDU_TDELTA, rc._RGDU_TMAX) == (
        "lewis", rmb.SOCIETES["lewis"]["company_id"], 0.3781, 0.3981)


def test_cartol_50_salaries_et_plus_prend_le_tdelta_de_0_3821(remise_en_etat):
    rmb.regler_pour("cartol")
    assert (rmb.SOCIETE, rmb.TDELTA, rc._RGDU_TMAX) == ("cartol", 0.3821, 0.4021)


def test_une_societe_inconnue_est_refusee(remise_en_etat):
    with pytest.raises(KeyError):
        rmb.regler_pour("inconnue")


def test_les_dsn_de_cartol_et_lewis_completent_jusqu_a_la_bascule():
    """Mont Blanc n'avait ses DSN que jusqu'à juin ; Cartol et LEWIS les ont toutes."""
    assert rmb.SOCIETES["mbc"]["dsn_jusqu_a"] == 6
    assert rmb.SOCIETES["cartol"]["dsn_jusqu_a"] == 9 and rmb.SOCIETES["lewis"]["dsn_jusqu_a"] == 9


# --- Salaire de base ------------------------------------------------------------------------


def _bulletin(*lignes) -> Bulletin:
    b = Bulletin(matricule="X")
    b.lignes = list(lignes)
    b.infos = {"nir": "1", "entree": "01/01/2020"}
    return b


def test_deux_salaires_de_base_dans_le_mois_ne_disent_pas_le_salaire_du_mois():
    """Changement de contrat ou de taux en cours de mois : deux lignes « SALAIRE DE BASE »."""
    fiche = {"salaire_de_base": {"valeur": 1823.07, "type": "mensuel"}, "duree_hebdomadaire": 35.0}
    b = _bulletin(Ligne(None, "SALAIRE DE BASE", base=151.67, taux=12.31, gain=1867.06),
                  Ligne(None, "SALAIRE DE BASE", base=151.67, taux=12.3162, gain=1868.0))
    assert rmb.plan_de_salaire(fiche, b) is None


def test_un_horaire_de_37_h_30_paye_en_entier_au_salaire_de_base_est_suivi_tel_quel():
    """Cartol : 162,50 h au taux de base, sans ligne d'heures structurelles. La fiche (37,5 h,
    salaire pour l'horaire entier) suit le montant, sans le réglage « hors heures structurelles »."""
    fiche = {"salaire_de_base": {"valeur": 2645.0, "type": "mensuel"}, "duree_hebdomadaire": "37.50",
             "specificites_paie": {}}
    b = _bulletin(Ligne(None, "SALAIRE DE BASE", base=162.5, taux=16.5846, gain=2695.0))
    plan = rmb.plan_de_salaire(fiche, b)
    assert plan["salaire_de_base"]["valeur"] == 2695.0
    assert plan["salaire_hors_hs_structurelles"] is None


def test_le_treizieme_mois_mensualise_de_lewis_est_le_salaire_que_quadra_paie():
    """LEWIS, juillet 2026 : 2 000,00 → 2 166,67 (13/12), avec le prorata du 13e mois versé à
    part. La fiche suit la ligne de base de septembre."""
    fiche = {"salaire_de_base": {"valeur": 2000.0, "type": "mensuel"}, "duree_hebdomadaire": 35.0}
    b = _bulletin(Ligne(None, "SALAIRE DE BASE", base=151.67, taux=14.2854, gain=2166.67))
    assert rmb.plan_de_salaire(fiche, b)["salaire_de_base"]["valeur"] == 2166.67


# --- Prévoyance -----------------------------------------------------------------------------


def test_la_prevoyance_groupama_de_cartol_est_reconnue_et_la_tranche_b_prend_sa_base():
    fiche = {"specificites_paie": {"prevoyance": {"adhesion": False, "lignes_specifiques": []}}}
    b = _bulletin(
        Ligne(None, "SALAIRE DE BASE", base=None, taux=None, gain=6746.67),
        Ligne("EP3", "PREV GROUPAMA CADRE TA", base=4005.0, taux=0.75, montant_sal=30.04, montant_pat=60.08,
              section="Q802 EXO."),
        Ligne("EP4", "PREV GROUPAMA CADRE TB", base=2741.67, taux=0.75, montant_sal=20.56, montant_pat=20.56,
              section="Q802 EXO."),
        Ligne("BPRV", "Remboursement prévoyance", base=1234.8, taux=50.0, gain=617.4),
    )
    plan = rmb.plan_de_prevoyance(fiche, b)
    assert [(l["base"], l["salarial"], l["patronal"]) for l in plan["lignes_specifiques"]] == [
        ("brut_plafonne", 0.0075, 0.015), ("tranche_2", 0.0075, 0.0075)]


def test_la_prevoyance_de_lewis_sans_code_est_reconnue_a_son_libelle():
    """« E_V6 PREVOYANCE NON CADRE TU1 META » : le code (avec un tiret bas) reste dans le libellé."""
    fiche = {"specificites_paie": {}}
    b = _bulletin(Ligne(None, "E_V6 PREVOYANCE NON CADRE TU1 META", base=617.4, taux=0.73, montant_sal=4.51,
                        montant_pat=4.51, section="Q802 EXO."),
                  Ligne(None, "Cotis. Retraite/Prév./F.santé", gain=58.03, section="Q802 EXO."))
    plan = rmb.plan_de_prevoyance(fiche, b)
    assert [(l["base"], l["salarial"], l["patronal"]) for l in plan["lignes_specifiques"]] == [
        ("brut_plafonne", 0.0073, 0.0073)]


# --- Ouverture : ce que la DSN corrige dans les PDF ------------------------------------------

from datetime import date  # noqa: E402

from scripts.verification_rgdu.dsn_quadra import BaseReduction  # noqa: E402

NIR = "1800175000001"


def _mois(brut: float, reduction: float, cumul: float, net: float = 0.0, cumul_net: float = 0.0,
          pas: float = 0.0, cumul_pas: float = 0.0) -> Bulletin:
    b = Bulletin(matricule="X")
    b.lignes = [Ligne(None, "SALAIRE DE BASE", base=151.67, taux=10.0, gain=brut),
                Ligne(None, "SALAIRE BRUT", gain=brut),
                Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", montant_pat=reduction,
                      section="Q802 EXO., ECRET. ET ALLEG. COTIS")]
    b.infos = {"nir": NIR + "45", "entree": "12/01/2026"}
    b.droite = {"plafond": 4005.0, "cumul_bruts": cumul, "heures_periode": 151.67, "cumul_heures": 0.0}
    b.net = {"net_imposable": net, "net_imposable_cumul": cumul_net, "pas_montant": pas, "pas_cumul": cumul_pas}
    b.cp = {"Solde": (0.0, 0.0)}
    b.pages = [1]
    return b


def _base(mois: int, assiette: float, reduction: float) -> BaseReduction:
    return BaseReduction(nir=NIR, nom="", prenom="", debut=date(2026, mois, 1), fin=date(2026, mois, 28),
                         assiette=assiette, montant_018=-reduction)


def test_un_mois_reedite_apres_l_impression_du_pdf_est_pris_dans_la_dsn():
    """LEWIS, avril : le PDF imprime 3 750,00 de brut, la DSN déclare 6 250,00 et le cumul de mai
    l'a repris (+ 2 500). Pour l'ouverture, le mois est celui de la DSN (brut et réduction)."""
    lus = {3: {"X": _mois(3750.0, -180.0, 7500.0)}, 4: {"X": _mois(3750.0, -182.63, 11250.0)},
           5: {"X": _mois(3784.69, -164.87, 17534.69)}}
    bases = {3: [_base(3, 3750.0, 180.0)], 4: [_base(4, 6250.0, -17.39)], 5: [_base(5, 3784.69, 164.87)]}
    remplaces = rmb.mois_reedites_depuis_la_dsn(lus, 5, bases)
    assert list(remplaces) == [4] and list(remplaces[4]) == ["X"]
    from scripts.reprise_colorplast_import_litteral import _brut_du_mois
    from scripts.reprise_colorplast_solde_ouverture import EST_REDUCTION_GENERALE, _somme_des_lignes

    b = remplaces[4]["X"]
    assert _brut_du_mois(b) == 6250.0 and _somme_des_lignes(b, EST_REDUCTION_GENERALE) == 17.39
    assert b.droite["plafond"] == 4005.0


def test_un_mois_ou_le_pdf_et_la_dsn_disent_le_meme_brut_n_est_pas_remplace():
    lus = {4: {"X": _mois(3750.0, -182.63, 3750.0)}}
    assert rmb.mois_reedites_depuis_la_dsn(lus, 4, {4: [_base(4, 3750.0, 100.0)]}) == {}


def test_un_cumul_imprime_qui_contredit_les_mois_et_la_dsn_est_refait_par_la_somme():
    """Cartol, septembre : le bulletin définitif compte le brut du mois deux fois dans son cumul
    (25 772,13 pour 23 063,32 de bruts, déclarés tels quels en DSN). L'ouverture prend la somme."""
    lus = {8: {"X": _mois(1000.0, -100.0, 1000.0, 800.0, 800.0, 10.0, 10.0)},
           9: {"X": _mois(1200.0, -90.0, 3400.0, 950.0, 2700.0, 0.0, 0.0)}}
    bases = {8: [_base(8, 1000.0, 100.0)], 9: [_base(9, 1200.0, 90.0)]}
    assert rmb.cumuls_imprimes_faux(lus, 9, bases) == {"X"}
    solde = rc.solde_d_ouverture(lus, 9, "X", par_la_somme=True)
    c = solde["cumuls"]
    assert (c["brut_total"], c["net_imposable"], c["impot_preleve_a_la_source"]) == (2200.0, 1750.0, 10.0)
    assert solde["controle_somme_des_bruts"] == 2200.0
    assert solde["reprise"]["cumul_brut_imprime_par_quadra"] == 3400.0


def test_un_cumul_imprime_juste_n_est_pas_touche():
    lus = {8: {"X": _mois(1000.0, -100.0, 1000.0)}, 9: {"X": _mois(1200.0, -90.0, 2200.0)}}
    bases = {8: [_base(8, 1000.0, 100.0)], 9: [_base(9, 1200.0, 90.0)]}
    assert rmb.cumuls_imprimes_faux(lus, 9, bases) == set()


def test_un_cumul_que_la_dsn_ne_confirme_pas_reste_une_anomalie():
    """La somme des mois ne fait pas foi si la DSN dit encore autre chose : rien n'est deviné."""
    lus = {8: {"X": _mois(1000.0, -100.0, 1000.0)}, 9: {"X": _mois(1200.0, -90.0, 3400.0)}}
    bases = {8: [_base(8, 1000.0, 100.0)], 9: [_base(9, 1500.0, 90.0)]}
    assert rmb.cumuls_imprimes_faux(lus, 9, bases) == set()


def test_un_bulletin_de_participation_sans_salaire_s_equilibre_avec_son_remboursement_de_csg():
    """Cartol, mai : ancien salarié, CSG sur participation prélevée (24,76) puis remboursée en gain,
    net nul. Le remboursement est une somme versée, pas une cotisation."""
    b = Bulletin(matricule="X")
    b.lignes = [Ligne("SWXI", "SWXI CSG AUTRES REVENUS", base=255.25, taux=9.7, montant_sal=24.76),
                Ligne(None, "Participation", base=255.25),
                Ligne("SCS1", "RBST CSG/CRD sur PART au PEE", base=255.25, taux=9.7, gain=24.76)]
    b.net = {"net_a_payer": 0.0, "pas_montant": 0.0}
    structure = rc.structure_des_cotisations(b)
    versees, retenues = rc.apres_le_net(b)
    assert rc.equilibre(b, structure, versees, retenues) == 0.0


# --- Sorties, prévoyance (suite), mutuelle ----------------------------------------------------


def _entree(entree: str, sortie: str | None = None) -> Bulletin:
    b = Bulletin(matricule="A")
    b.infos = {"nir": "1", "entree": entree, **({"sortie": sortie} if sortie else {})}
    return b


def test_une_sortie_suivie_d_un_nouveau_contrat_n_est_pas_posee():
    """Cartol : CDD clos le 31/07, nouveau contrat le 26/08 sous le même matricule. Poser la sortie
    archiverait une fiche payée en octobre."""
    juillet = {"A": _entree("01/03/2026", "31/07/2026")}
    septembre = {"A": _entree("26/08/2026")}
    assert rmb.sorties_de_quadra([juillet, septembre], date(2026, 9, 30)) == []
    assert [m for m, _b, _d in rmb.sorties_de_quadra([juillet, {}], date(2026, 9, 30))] == ["A"]


def test_la_tranche_2_de_lewis_prend_la_base_de_la_tranche_2_et_le_taux_salarial_a_montants_egaux():
    """« E_V7 PREVOYANCE NON CADRE TU2 META » sur 1 300,00 : 9,49 et 9,49. Le patronal recalculé
    (9,49 / 1 300 = 0,0073 ; sur une petite base l'arrondi le décale) prend le taux imprimé."""
    b = _bulletin(Ligne(None, "E_V6 PREVOYANCE NON CADRE TU1 META", base=4005.0, taux=0.73, montant_sal=29.24,
                        montant_pat=29.24, section="Q802"),
                  Ligne(None, "E_V7 PREVOYANCE NON CADRE TU2 META", base=101.25, taux=0.73, montant_sal=0.74,
                        montant_pat=0.74, section="Q802"))
    plan = rmb.plan_de_prevoyance({"specificites_paie": {}}, b)
    assert [(l["base"], l["salarial"], l["patronal"]) for l in plan["lignes_specifiques"]] == [
        ("brut_plafonne", 0.0073, 0.0073), ("tranche_2", 0.0073, 0.0073)]


def test_la_mutuelle_n_est_pas_alignee_chez_cartol_et_lewis():
    """Le catalogue de Cartol n'a aucune formule aux montants de Quadra et ses fiches portent la
    mutuelle de l'import DSN : rien n'est deviné, la mutuelle reste un chantier à part."""
    assert rmb.SOCIETES["mbc"]["aligner_mutuelle"] is True
    assert rmb.SOCIETES["cartol"]["aligner_mutuelle"] is False and rmb.SOCIETES["lewis"]["aligner_mutuelle"] is False


# --- Réduction entièrement reprise par Quadra (08/11) -------------------------------------------


def _arret(brut: float, reduction: float, cumul: float, cumul_heures: float) -> Bulletin:
    b = _mois(brut, reduction, cumul)
    b.droite["cumul_heures"] = cumul_heures
    return b


def _lus_reduction_reprise():
    """Arrêt long : réduction appliquée en janvier, reprise en entier en février (cumul nul)."""
    return {8: {"X": _arret(2247.62, -361.42, 2247.62, 151.67)},
            9: {"X": _arret(1299.87, 361.42, 3547.49, 214.68)}}


def test_une_reduction_que_quadra_a_reprise_en_entier_garde_la_base_de_quadra(remise_en_etat):
    """Cartol, S.S. : Quadra a repris toute sa réduction en avril (SMIC retenu négatif en DSN) ;
    la formule sur les heures imprimées en rendrait 152,28 € en octobre. On suit Quadra (décision du
    08/11) : la base de Martine est un SMIC nul, toutes les heures imprimées hors de la réduction."""
    rmb.regler_pour("cartol")
    c = rc.solde_d_ouverture(_lus_reduction_reprise(), 9, "X")["cumuls"]
    assert c["reduction_generale_patronale"] == 0.0
    assert c["heures_hors_reduction_generale"] == 214.68


def test_mont_blanc_garde_la_formule_quand_quadra_n_a_rien_applique(remise_en_etat):
    rmb.regler_pour("mbc")
    assert "heures_hors_reduction_generale" not in rc.solde_d_ouverture(_lus_reduction_reprise(), 9, "X")["cumuls"]


def test_un_salaire_au_dela_de_trois_smic_sans_reduction_n_est_pas_touche(remise_en_etat):
    """Aucune réduction et la formule n'en donne pas non plus : rien à poser."""
    rmb.regler_pour("cartol")
    lus = {9: {"X": _arret(9000.0, 0.0, 9000.0, 151.67)}}
    assert "heures_hors_reduction_generale" not in rc.solde_d_ouverture(lus, 9, "X")["cumuls"]


# --- Forfait jours réduit (08/11) -----------------------------------------------------------


def test_l_en_tete_quadra_donne_les_jours_du_forfait():
    b = Bulletin(matricule="X")
    q.lire_page("   Emploi :      Méthodiste          Ancienneté :   08/10/2018     Forfait annuel :     171.00 jours\n",
                1, b)
    assert b.infos["forfait_annuel"] == "171.00"


def test_un_forfait_reduit_de_quadra_est_pose_sur_la_fiche():
    """Cartol, D.G. : forfait passé de 214 à 171 jours en septembre (80 %), bulletin « Forfait annuel :
    171.00 jours », DSN 40.013 = 17,00 sur 21,27. La fiche n'a pas de forfait propre : sans lui, le
    moteur prend les 214 jours de la société."""
    b = _bulletin(Ligne(None, "SALAIRE DE BASE", gain=3244.48))
    b.infos["forfait_annuel"] = "171.00"
    fiche = {"is_forfait_jour": True, "specificites_paie": {}}
    plan = rmb.plan_de_forfait(fiche, b, 214.0)
    assert plan["forfait_annual_days"] == 171.0 and plan["avant"] == 214.0
    assert rmb.plan_de_forfait(fiche, _bulletin(), 214.0) is None
    b.infos["forfait_annuel"] = "214.00"
    assert rmb.plan_de_forfait(fiche, b, 214.0) is None
    b.infos["forfait_annuel"] = "171.00"
    assert rmb.plan_de_forfait({"is_forfait_jour": True, "specificites_paie": {"forfait_annual_days": 171}}, b, 214.0) is None
    assert rmb.plan_de_forfait({"is_forfait_jour": False, "specificites_paie": {}}, b, 214.0) is None
