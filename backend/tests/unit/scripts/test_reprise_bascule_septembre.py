"""Reprise Quadra avec une bascule au 30/09 : le mois de bascule devient un paramètre.

Colorplast et Comitech reprennent septembre 2026 comme août (décision du 24/10/2026).
Trois choses à tenir : l'usage d'août ne change pas, un bulletin repris s'équilibre
sur le PDF, et un salarié revenu en cours d'année ouvre avec les cumuls de son seul
contrat en cours (comme MARTINE au premier mois d'un contrat).
"""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne

pytestmark = pytest.mark.unit


def _bulletin(lignes, net=None, droite=None, **infos) -> Bulletin:
    b = Bulletin(matricule="ESSAI")
    b.lignes = lignes
    b.net = net or {}
    b.droite = droite or {}
    b.infos = infos
    b.pages = [1]
    return b


def _mois(brut: float, entree: str, cumul: float, heures: float = 151.67, rg: float = -100.0) -> Bulletin:
    return _bulletin(
        [
            Ligne(None, "SALAIRE DE BASE", base=151.67, taux=round(brut / 151.67, 4), gain=brut),
            Ligne(None, "SALAIRE BRUT", gain=brut),
            Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=rg, montant_pat=rg),
        ],
        net={"net_imposable": round(brut * 0.78, 2), "pas_montant": 0.0, "net_hs_exo": 0.0,
             "net_imposable_cumul": round(cumul * 0.78, 2), "pas_cumul": 0.0},
        droite={"cumul_bruts": cumul, "cumul_heures": 0.0, "heures_periode": heures, "plafond": 4005.0},
        entree=entree,
    )


# ---------------------------------------------------------------------------
# Le mois de bascule, paramètre des deux scripts Colorplast
# ---------------------------------------------------------------------------


def test_sans_parametre_la_reprise_reste_celle_d_aout():
    from scripts.reprise_colorplast_import_litteral import (
        MOIS_REPRIS,
        _arguments,
        mois_repris,
    )

    assert MOIS_REPRIS == (1, 2, 3, 4, 5, 6, 7, 8)
    assert _arguments(["x"]) == (False, MOIS_REPRIS, 8)
    assert _arguments(["x", "--mois", "8", "--apply"]) == (True, (8,), 8)
    assert mois_repris(9)[-1] == 9


def test_septembre_n_est_repris_qu_avec_la_bascule_au_30_09():
    from scripts.reprise_colorplast_import_litteral import _arguments

    with pytest.raises(SystemExit):
        _arguments(["x", "--mois", "9"])
    assert _arguments(["x", "--bascule", "9", "--mois", "9"]) == (False, (9,), 9)


def test_le_solde_d_ouverture_lit_le_mois_de_bascule_demande():
    from scripts.reprise_colorplast_solde_ouverture import construire_le_solde

    lus = {m: {"A": _mois(2000.0, "01/01/2020", 2000.0 * m)} for m in range(1, 10)}
    lus[9]["A"].cp = {"Solde": (3.0, 8.32)}
    solde = construire_le_solde(lus, 9)["A"]
    assert solde["periode"]["dernier_mois_calcule"] == 9
    assert solde["mois_presents"] == list(range(1, 10))
    assert solde["cumuls"]["brut_total"] == 18000.0
    assert solde["controle_somme_des_bruts"] == 18000.0
    assert solde["conges"] == {"cp_n1": 3.0, "cp_n": 8.32}
    # Juin à septembre : la base du dixième de la période qui a ouvert le 1er juin.
    assert solde["cumuls"]["brut_reference_n_1"] == 8000.0


# ---------------------------------------------------------------------------
# Contrôle d'équilibre d'un bulletin Colorplast repris
# ---------------------------------------------------------------------------


def test_un_bulletin_colorplast_s_equilibre_sans_compter_le_sous_total():
    from scripts.reprise_colorplast_import_litteral import controle_du_pdf

    b = _bulletin(
        [
            Ligne(None, "SALAIRE DE BASE", base=151.67, taux=13.0, gain=1971.71),
            Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=16.25, gain=281.61),
            Ligne(None, "SOUS TOTAL SALAIRE DE BASE", base=169.0, gain=2253.32),
            Ligne(None, "SALAIRE BRUT", gain=2253.32),
            Ligne(None, "Sécu.Soc Plafonnée", base=2253.32, taux=6.9, montant_sal=155.48, montant_pat=192.66),
            Ligne(None, "TOTAL DES RETENUES", montant_sal=155.48, montant_pat=192.66),
            Ligne(None, "NET IMPOSABLE", gain=2097.84),
        ],
        net={"net_a_payer": 2097.84, "pas_montant": 0.0},
    )
    assert controle_du_pdf(b) == {"brut": 0.0, "net": 0.0, "total_salarial": 155.48}


def test_un_bulletin_qui_ne_s_equilibre_pas_se_voit():
    from scripts.reprise_colorplast_import_litteral import controle_du_pdf

    b = _bulletin(
        [Ligne(None, "SALAIRE DE BASE", gain=2000.0), Ligne(None, "SALAIRE BRUT", gain=2000.0)],
        net={"net_a_payer": 1990.0, "pas_montant": 0.0},
    )
    assert controle_du_pdf(b)["net"] == -10.0


def test_la_sortie_designe_un_salarie_par_ses_initiales():
    from scripts.reprise_colorplast_import_litteral import etiquette

    fiche = {"id": "1c4cc8b6-0000", "first_name": "jeanne", "last_name": "durand"}
    assert etiquette(fiche) == "J.D. 1c4cc8b6"
    assert etiquette(None, "23/09/2026") == "sans fiche (entré le 23/09/2026)"


# ---------------------------------------------------------------------------
# Comitech : retour en cours d'année sur la même fiche, même matricule Quadra
# ---------------------------------------------------------------------------


def _retour_le_1er_septembre() -> dict:
    """CDD de janvier à mai, puis nouveau contrat le 01/09 : Quadra garde le matricule
    et continue son cumul brut sur l'année (Comitech, 2026, chiffres arrondis)."""
    lus: dict[int, dict] = {}
    cumul = 0.0
    for m in range(1, 6):
        cumul += 2000.0
        lus[m] = {"M": _mois(2000.0, "19/01/2026", cumul, rg=-600.0)}
    for m in range(1, 10):
        lus.setdefault(m, {})["N"] = _mois(2500.0, "01/03/2015", 2500.0 * m)
    lus[9]["M"] = _mois(2365.33, "01/09/2026", cumul + 2365.33, heures=169.0, rg=-636.98)
    return lus


def test_un_salarie_revenu_ouvre_avec_son_seul_contrat_en_cours():
    from scripts.reprise_comitech import mois_du_contrat_en_cours, solde_d_ouverture

    lus = _retour_le_1er_septembre()
    assert mois_du_contrat_en_cours(lus, 9, "M") == [9]
    solde = solde_d_ouverture(lus, 9, "M")
    c = solde["cumuls"]
    assert c["brut_total"] == 2365.33
    assert c["heures_remunerees"] == 169.0
    assert c["reduction_generale_patronale"] == -636.98
    assert c["cumul_pss_agirc_arrco"] == 4005.0
    assert c["net_imposable"] == round(2365.33 * 0.78, 2)
    assert solde["controle_somme_des_bruts"] == 2365.33
    assert solde["reprise"]["mois_repris"] == [9]
    assert solde["reprise"]["contrat_en_cours_depuis"] == "01/09/2026"
    assert solde["reprise"]["cumul_brut_imprime_sur_l_annee"] == 12365.33


def test_un_salarie_present_toute_l_annee_garde_les_cumuls_imprimes():
    from scripts.reprise_comitech import mois_du_contrat_en_cours, solde_d_ouverture

    lus = _retour_le_1er_septembre()
    assert mois_du_contrat_en_cours(lus, 9, "N") == list(range(1, 10))
    solde = solde_d_ouverture(lus, 9, "N")
    assert solde["cumuls"]["brut_total"] == 22500.0
    assert "contrat_en_cours_depuis" not in solde["reprise"]


def test_les_conges_d_une_fiche_restee_sur_l_ancien_contrat_ne_sont_pas_repris():
    from scripts.reprise_comitech import fiche_hors_du_contrat

    b = _mois(2365.33, "01/09/2026", 12365.33)
    raison = fiche_hors_du_contrat({"contract_end_date": "2026-05-31"}, b)
    assert raison and "31/05/2026" in raison and "Nouveau contrat" in raison
    assert fiche_hors_du_contrat({"contract_end_date": None}, b) is None
    assert fiche_hors_du_contrat({"contract_end_date": "2026-12-18"}, b) is None


# ---------------------------------------------------------------------------
# Une embauche au nom en deux mots retrouve sa fiche au solde d'ouverture
# ---------------------------------------------------------------------------


def test_le_solde_retrouve_la_fiche_d_un_matricule_coupe_au_premier_blanc():
    """Quadra imprime « Matricule : MARTIN DUVAL » ; le lecteur s'arrête au blanc et lit
    « MARTIN ». L'import apparie par préfixe : le solde doit faire de même, sinon il
    compte la fiche comme absente et refuse d'écrire."""
    from scripts.reprise_colorplast_solde_ouverture import fiches_des_matricules

    deux_mots = {"id": "a", "last_name": "MARTIN DUVAL"}
    un_mot = {"id": "b", "last_name": "DURAND"}
    par_nom = {"MARTINDUVAL": deux_mots, "DURAND": un_mot}
    assert fiches_des_matricules(par_nom, ["MARTIN", "DURAND", "INCONNU"]) == {
        "MARTIN": deux_mots,
        "DURAND": un_mot,
    }


def test_un_prefixe_qui_designe_deux_fiches_ne_designe_personne():
    from scripts.reprise_colorplast_solde_ouverture import fiches_des_matricules

    par_nom = {"MARTINDUVAL": {"id": "a"}, "MARTINEAU": {"id": "b"}}
    assert fiches_des_matricules(par_nom, ["MARTIN"]) == {}
    assert fiches_des_matricules(par_nom, ["MARTINEAU"]) == {"MARTINEAU": {"id": "b"}}
