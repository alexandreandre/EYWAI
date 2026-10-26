"""Reprise Mont Blanc : le programme de Comitech réglé pour une société de 50 salariés et plus,
un mois absent du PDF complété depuis la DSN, l'ancienneté de Quadra. Données fabriquées."""

from __future__ import annotations

from datetime import date

import pytest

import scripts.reprise_comitech as rc
from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_mont_blanc import (
    TDELTA,
    complements_depuis_la_dsn,
    plafond_au_prorata,
    plan_d_anciennete,
)
from scripts.verification_rgdu.dsn_quadra import BaseReduction

pytestmark = pytest.mark.unit


@pytest.fixture
def reglage_mont_blanc():
    avant = (rc.SOCIETE, rc.COMPANY_ID, rc._RGDU_TDELTA, rc._RGDU_TMAX)
    rc.regler_pour("mbc", "societe-essai", TDELTA)
    yield
    rc.SOCIETE, rc.COMPANY_ID, rc._RGDU_TDELTA, rc._RGDU_TMAX = avant


def _bulletin(mat: str, nir: str, entree: str, **infos) -> Bulletin:
    b = Bulletin(matricule=mat)
    b.lignes = [Ligne(None, "SALAIRE BRUT", gain=2000.0)]
    b.infos = {"nir": nir, "entree": entree, **infos}
    b.pages = [1]
    return b


def test_a_partir_de_50_salaries_le_plafond_du_coefficient_est_0_4021(reglage_mont_blanc):
    """Un coefficient de 0,4000 est plafonné sous 50 salariés (0,3981), pas à Mont Blanc :
    il dit alors combien d'heures de SMIC Quadra a retenues."""
    smic, raison = rc.smic_retrouve_de_la_reduction(10000.0, 4000.0)
    assert raison is None and smic is not None
    assert rc.smic_retrouve_de_la_reduction(10000.0, 4021.0)[0] is None


def test_le_reglage_ne_change_pas_comitech():
    assert (rc._RGDU_TDELTA, rc._RGDU_TMAX) == (0.3781, 0.3981)
    assert rc.smic_retrouve_de_la_reduction(10000.0, 4000.0)[0] is None


def test_le_plafond_d_un_mois_d_entree_est_au_prorata_des_jours():
    assert plafond_au_prorata(3, date(2026, 3, 2)) == round(4005.0 * 30 / 31, 2)
    assert plafond_au_prorata(4, date(2026, 3, 2)) == 4005.0


def test_un_mois_declare_en_dsn_sans_bulletin_dans_le_pdf_est_complete():
    """Entrée le 02/03 : bulletin de mars absent du PDF, mais le salarié est dans la DSN de
    mars. Le mois entre dans l'ouverture avec le brut et la réduction de la DSN."""
    nir = "2990175000001"
    lus = {
        3: {"AUTRE": _bulletin("AUTRE", "1800175000009", "01/01/2020")},
        7: {"ESSAI": _bulletin("ESSAI", nir + "45", "02/03/2026")},
    }
    base = BaseReduction(nir=nir, nom="", prenom="", debut=date(2026, 3, 1), fin=date(2026, 3, 31),
                         assiette=1985.79, montant_018=-480.0, montant_106=-95.5)
    autre = BaseReduction(nir="1800175000009", nom="", prenom="", debut=date(2026, 3, 1),
                          fin=date(2026, 3, 31), assiette=2500.0)
    complements = complements_depuis_la_dsn(lus, 7, {3: [base, autre]})
    assert list(complements) == [3] and list(complements[3]) == ["ESSAI"]
    b = complements[3]["ESSAI"]
    from scripts.reprise_colorplast_import_litteral import _brut_du_mois
    from scripts.reprise_colorplast_solde_ouverture import (
        EST_REDUCTION_GENERALE,
        _somme_des_lignes,
    )

    assert _brut_du_mois(b) == 1985.79
    assert _somme_des_lignes(b, EST_REDUCTION_GENERALE) == -575.5
    assert b.droite["plafond"] == round(4005.0 * 30 / 31, 2)


def test_la_date_d_anciennete_de_quadra_remplace_la_reprise_en_mois():
    """Entrée le 01/04/2012, ancienneté du 04/06/1986 (société d'origine) : la fiche portait
    173 mois de « reprise », l'ancienneté déjà écoulée, comptée deux fois."""
    fiche = {"hire_date": "2012-04-01", "seniority_reference_date": None, "prior_service_months": 173}
    plan = plan_d_anciennete(fiche, _bulletin("X", "1", "01/04/2012", anciennete="04/06/1986"))
    assert plan["seniority_reference_date"] == "1986-06-04"
    assert plan["prior_service_months"] == 0


def test_une_anciennete_egale_a_l_entree_est_posee_quand_meme():
    """Sans date posée, le moteur prend la date « d'ancienneté » de l'ancien import DSN, lue
    sur une suspension (congé enfant malade du 08/01/2026) : la prime d'ancienneté tombait à
    zéro. La date de Quadra est donc toujours écrite."""
    fiche = {"hire_date": "2018-01-11", "seniority_reference_date": None, "prior_service_months": 103,
             "specificites_paie": {"dsn_anciennete": {"date_anciennete": "2026-01-08"}}}
    plan = plan_d_anciennete(fiche, _bulletin("X", "1", "11/01/2018", anciennete="11/01/2018"))
    assert plan["seniority_reference_date"] == "2018-01-11" and plan["prior_service_months"] == 0


def test_une_prime_que_quadra_paie_a_part_n_est_pas_fondue_dans_le_salaire():
    from scripts.reprise_mont_blanc import plan_prime_anciennete

    fiche = {"specificites_paie": {"prime_anciennete": {"incluse_dans_salaire_base": True}}}
    b = _avec_base(151.67, 15.5126, 2352.8, Ligne("BANC", "Prime ancienneté", base=1994.55, taux=15.0, gain=299.18))
    assert plan_prime_anciennete(fiche, b) is True
    assert plan_prime_anciennete({"specificites_paie": {}}, b) is False


def test_une_fiche_deja_juste_n_est_pas_touchee():
    fiche = {"hire_date": "2012-04-01", "seniority_reference_date": "1986-06-04", "prior_service_months": 0}
    assert plan_d_anciennete(fiche, _bulletin("X", "1", "01/04/2012", anciennete="04/06/1986")) is None
    fiche = {"hire_date": "2018-01-11", "seniority_reference_date": "2018-01-11", "prior_service_months": 0}
    assert plan_d_anciennete(fiche, _bulletin("X", "1", "11/01/2018", anciennete="11/01/2018")) is None
    fiche = {"hire_date": "2012-04-01", "seniority_reference_date": "1986-06-04", "prior_service_months": 0}
    assert plan_d_anciennete(fiche, _bulletin("X", "1", "01/04/2012", anciennete="04/06/1986")) is None


def test_un_solde_negatif_de_quadra_affiche_a_zero_est_juste():
    assert rc.verdict_des_conges((0.0, -2.84), (0.0, 0.0)).startswith("= Quadra")
    assert rc.verdict_des_conges((0.0, 4.16), (0.0, 0.0)) == "ÉCART"
    assert rc.verdict_des_conges((10.0, 2.08), (10.0, 2.08)) == "= Quadra"


def test_une_anciennete_dans_le_futur_est_une_faute_de_frappe():
    from scripts.reprise_mont_blanc import anciennete_de_quadra

    juin = _bulletin("X", "1", "21/08/2023", anciennete="21/08/2023")
    juillet = _bulletin("X", "1", "21/08/2023", anciennete="21/08/2026")
    assert anciennete_de_quadra([juin, juillet], date(2026, 7, 31)) == date(2023, 8, 21)


def test_l_anciennete_se_compare_a_l_embauche_de_la_fiche():
    """Fiche embauchée en 2022, Quadra : entrée et ancienneté au 05/01/2026 (nouveau
    contrat) : la date de Quadra reste, sinon la prime partirait de 2022."""
    fiche = {"hire_date": "2022-05-02", "seniority_reference_date": "2026-01-05", "prior_service_months": 6}
    plan = plan_d_anciennete(fiche, _bulletin("X", "1", "05/01/2026", anciennete="05/01/2026"))
    assert plan["seniority_reference_date"] == "2026-01-05" and plan["prior_service_months"] == 0


def _avec_base(base, taux, gain, *autres):
    b = _bulletin("X", "1", "01/01/2020")
    b.lignes = [Ligne(None, "SALAIRE DE BASE", base=base, taux=taux, gain=gain), *autres]
    return b


def test_le_salaire_de_la_fiche_suit_le_taux_de_quadra_au_mois_de_bascule():
    """Le SMIC passé à 12,31 € : la fiche gardait 12,02 × 151,67 (1 823,07 €)."""
    from scripts.reprise_mont_blanc import plan_de_salaire

    fiche = {"salaire_de_base": {"valeur": 1823.07, "type": "mensuel"}, "duree_hebdomadaire": "37.50",
             "specificites_paie": {"salaire_hors_hs_structurelles": True}}
    hs = Ligne(None, "H. supp majorées à 25 %", base=10.83, taux=15.3875, gain=166.65)
    plan = plan_de_salaire(fiche, _avec_base(151.67, 12.31, 1867.06, hs))
    assert plan["salaire_de_base"] == {"valeur": 1867.06, "type": "mensuel"}
    assert plan["salaire_hors_hs_structurelles"] is True


def test_une_fiche_qui_comptait_les_heures_structurelles_dans_le_salaire_est_ramenee_a_la_base():
    """37,5 h : Quadra paie 151,67 h de base et 10,83 h structurelles à 25 % ; la fiche portait
    les deux dans le salaire, sans le réglage « salaire hors heures structurelles »."""
    from scripts.reprise_mont_blanc import plan_de_salaire

    fiche = {"salaire_de_base": {"valeur": 1985.79, "type": "mensuel"}, "duree_hebdomadaire": "37.50",
             "specificites_paie": {}}
    hs = Ligne(None, "H. supp majorées à 25 %", base=10.83, taux=15.3875, gain=166.65)
    plan = plan_de_salaire(fiche, _avec_base(151.67, 12.31, 1867.06, hs))
    assert plan["salaire_de_base"]["valeur"] == 1867.06
    assert plan["salaire_hors_hs_structurelles"] is True


def test_un_mois_incomplet_ne_dit_pas_le_salaire_du_mois_complet():
    from scripts.reprise_mont_blanc import plan_de_salaire

    fiche = {"salaire_de_base": {"valeur": 2017.61, "type": "mensuel"}, "duree_hebdomadaire": "37.50"}
    assert plan_de_salaire(fiche, _avec_base(21.0, 13.3026, 279.35)) is None


def test_un_forfait_jours_prend_le_montant_imprime():
    from scripts.reprise_mont_blanc import plan_de_salaire

    fiche = {"salaire_de_base": {"valeur": 3900.0, "type": "mensuel"}, "duree_hebdomadaire": "35.00"}
    plan = plan_de_salaire(fiche, _avec_base(None, None, 3984.0, Ligne(None, "Forfait 216 jours")))
    assert plan["salaire_de_base"]["valeur"] == 3984.0 and plan["salaire_hors_hs_structurelles"] is None


def test_une_fiche_deja_juste_n_a_pas_de_plan_de_salaire():
    from scripts.reprise_mont_blanc import plan_de_salaire

    fiche = {"salaire_de_base": {"valeur": 1867.06, "type": "mensuel"}, "duree_hebdomadaire": "37.50",
             "specificites_paie": {"salaire_hors_hs_structurelles": True}}
    hs = Ligne(None, "H. supp majorées à 25 %", base=10.83, taux=15.3875, gain=166.65)
    assert plan_de_salaire(fiche, _avec_base(151.67, 12.31, 1867.06, hs)) is None


def test_le_taux_de_chomage_module_se_lit_sur_les_bulletins_de_quadra():
    """Bonus-malus : Quadra applique 2,95 % (60,00 € sur 2 033,71 €) ; l'apprenti reste à 4 %."""
    from scripts.reprise_mont_blanc import taux_de_chomage_de_quadra

    def bulletin(base, montant):
        b = _bulletin("X", "1", "01/01/2020")
        b.lignes = [Ligne(None, "SALAIRE BRUT", gain=base), Ligne(None, "Chômage", base=base, montant_pat=montant)]
        return b

    assert taux_de_chomage_de_quadra([bulletin(2033.71, 60.0), bulletin(3984.0, 117.53),
                                      bulletin(1232.23, 49.29)]) == 2.95
