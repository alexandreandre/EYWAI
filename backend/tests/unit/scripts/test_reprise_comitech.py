"""Reprise Comitech : un bulletin Quadra copié dans notre format, contrôlé avant écriture."""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_comitech import (
    _nir,
    apres_le_net,
    donnees_du_bulletin,
    equilibre,
    lignes_du_brut,
    structure_des_cotisations,
    zones,
)

pytestmark = pytest.mark.unit


def _bulletin(lignes, net=None, **infos) -> Bulletin:
    b = Bulletin(matricule="ESSAI")
    b.lignes = lignes
    b.net = net or {}
    b.infos = infos
    b.pages = [1]
    return b


def _mensuel() -> Bulletin:
    """Un bulletin de juillet type (chiffres d'un vrai bulletin, anonymisé)."""
    return _bulletin(
        [
            Ligne(None, "SALAIRE DE BASE", base=151.67, taux=12.689, gain=1924.54),
            Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=15.8612, gain=274.87),
            Ligne("BANC", "Prime ancienneté", base=1759.53, taux=6.0, gain=105.57),
            Ligne("BPOS", "Prime poste difficile", base=60.0, gain=60.0),
            Ligne(None, "Solde Heures recup =-0.5h"),
            Ligne(None, "SALAIRE BRUT", gain=2364.98),
            Ligne(None, "Sécu.Soc-Mal.Mater.Inval.Déc.", base=2364.98, montant_pat=165.55),
            Ligne(None, "Sécu.Soc Plafonnée", base=2364.98, taux=6.9, montant_sal=163.18, montant_pat=202.21),
            Ligne(None, "Sécu.Soc Déplafonnée", base=2364.98, taux=0.4, montant_sal=9.46, montant_pat=49.9),
            Ligne(None, "Complémentaire Tranche 1", base=2364.98, taux=4.01, montant_sal=94.84, montant_pat=142.14),
            Ligne(None, "Autres contrib. dues par empl.", base=2364.98, montant_pat=49.56),
            Ligne(None, "CSG déductible à l'IR", base=2093.76, taux=6.8, montant_sal=142.38),
            Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=-592.27, montant_pat=-592.27),
            Ligne("EMU3", "GAN MUTUELLE ISOLE", base=29.24, taux=1.0, montant_sal=29.24, montant_pat=29.23),
            Ligne("EPR3", "GAN PREVOYANCE NON CADRE TA", base=2364.98, taux=0.465, montant_sal=11.0, montant_pat=11.0),
            Ligne("EWA2", "REDUCTION SALARIALE HS/HC 2019", base=274.87, taux=-11.31, montant_sal=-31.09),
            Ligne("EWZB", "REDUCT HEURES SUPPL. P.P.<= 20", base=17.33, montant_pat=-26.0),
            Ligne(None, "TOTAL DES RETENUES", montant_sal=419.01, montant_pat=31.32),
            Ligne(None, "Cotis. Retraite/Prév./F.santé", gain=29.23),
            Ligne(None, "NET IMPOSABLE", gain=1700.33),
            Ligne(None, "Cotis. Retraite/Prév./F.santé", montant_sal=29.23),
            Ligne("SMU2", "GAN MUTUELLE FAMILLE", base=-98.12, gain=-98.12),
            Ligne(None, "CSG/CRDS non déductible à l'IR", base=2093.76, taux=2.9, montant_sal=60.72),
            Ligne(None, "CSG/CRDS non déductible à l'IR", base=270.06, taux=9.7, montant_sal=26.2),
            Ligne("SPPV", "PRIME PARTAGE DE LA VALEUR", base=100.0, gain=100.0),
        ],
        net={"net_a_payer": 1860.93, "pas_montant": 0.0, "net_imposable": 1700.33},
        nir="166109935323859",
    )


def test_le_nir_se_compare_sans_sa_cle():
    assert _nir("1 66 10 99 353 238 59") == _nir("1661099353238") == "1661099353238"


def test_les_lignes_du_brut_redonnent_le_brut_et_gardent_les_compteurs():
    lignes, mentions = lignes_du_brut(_mensuel())
    assert [l["libelle"] for l in lignes][:2] == ["Salaire de base", "Heures suppl. structurelles majorées à 25%"]
    assert mentions["ecart_brut"] == 0.0
    assert mentions["solde_heures_recup"] == -0.5


def test_les_cotisations_sont_rangees_dans_nos_blocs():
    s = structure_des_cotisations(_mensuel())
    assert {l["coti_id"] for l in s["bloc_allegements"]} == {
        "reduction_generale", "reduction_hs_salariale", "deduction_hs_patronale"}
    assert [l["coti_id"] for l in s["bloc_autres_contributions"]["lignes"]] == ["autres_contributions"]
    assert [l["montant_salarial"] for l in s["bloc_csg_non_deductible"]] == [60.72, 26.2]
    mutuelles = [l for l in s["bloc_principales"] if l["coti_id"] == "mutuelle"]
    assert [l["montant_salarial"] for l in mutuelles] == [29.24, 98.12]
    # Le total imprimé « TOTAL DES RETENUES » : tout sauf la mutuelle facultative d'après le net.
    assert s["total_avant_csg_crds"]["montant_salarial"] == 419.01


def test_le_net_s_equilibre_au_centime():
    b = _mensuel()
    s = structure_des_cotisations(b)
    versees, retenues = apres_le_net(b)
    assert [v["libelle"] for v in versees] == ["PRIME PARTAGE DE LA VALEUR"]
    assert equilibre(b, s, versees, retenues) == 0.0


def test_une_retenue_imprimee_que_quadra_ne_deduit_pas_est_marquee():
    b = _mensuel()
    b.lignes.append(Ligne(None, "Saisie essai", base=180.0, montant_sal=180.0))
    s = structure_des_cotisations(b)
    versees, retenues = apres_le_net(b)
    assert equilibre(b, s, versees, retenues) == 0.0
    assert retenues[0]["sans_effet_sur_le_net"] is True


def test_un_bulletin_de_participation_seule_n_a_pas_de_zone_brut():
    b = _bulletin(
        [
            Ligne(None, "CSG déductible à l'IR", base=768.74, taux=6.8, montant_sal=52.27),
            Ligne(None, "TOTAL DES RETENUES", montant_sal=52.27),
            Ligne(None, "Participation 2025", base=768.74, gain=768.74),
            Ligne(None, "NET IMPOSABLE", gain=716.47),
            Ligne(None, "CSG/CRDS non déductible à l'IR", base=768.74, taux=2.9, montant_sal=22.29),
        ],
        net={"net_a_payer": 694.18},
    )
    assert zones(b)["brut"] == []
    s = structure_des_cotisations(b)
    versees, retenues = apres_le_net(b)
    assert equilibre(b, s, versees, retenues) == 0.0


def test_le_bulletin_complet_porte_la_reprise_et_les_compteurs():
    donnees = donnees_du_bulletin(
        _mensuel(), 2026, 7, {"last_name": "Essai", "first_name": "Jeanne", "statut": "Non-Cadre"},
        {"company_name": "Société QA", "siret": "123"},
    )
    assert donnees["salaire_brut"] == 2364.98 and donnees["net_a_payer"] == 1860.93
    assert donnees["en_tete"]["date_fin_periode"] == "2026-07-31"
    assert donnees["pied_de_page"]["compteurs_quadra"] == {"solde_heures_recup": -0.5}
    assert donnees["reprise"]["logiciel_precedent"] == "Quadra"


def test_un_mois_d_arret_complet_a_un_brut_nul_et_reporte_le_net_negatif():
    """Août : tout le mois en maladie, brut nul (Quadra n'imprime pas « SALAIRE BRUT »),
    et le net négatif de juillet reporté en retenue."""
    b = _bulletin(
        [
            Ligne(None, "SALAIRE DE BASE", base=151.67, taux=12.954, gain=1964.73),
            Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=16.1925, gain=280.62),
            Ligne(None, "Absence maladie 010826-310826", base=151.67, taux=12.954, montant_sal=1964.73),
            Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=16.1925, montant_sal=280.62),
            Ligne(None, "Report NAP négatif", base=419.75, montant_sal=419.75),
        ],
        net={"net_a_payer": -419.75, "pas_montant": 0.0},
    )
    assert lignes_du_brut(b)[1]["ecart_brut"] == 0.0
    s = structure_des_cotisations(b)
    versees, retenues = apres_le_net(b)
    assert [r["libelle"] for r in retenues] == ["Report NAP négatif"]
    assert equilibre(b, s, versees, retenues) == 0.0


def test_deux_contrats_le_meme_mois_l_ouverture_est_celle_du_contrat_qui_continue():
    """Fin de CDD le 30/08 puis apprentissage le 31/08 : Quadra ouvre un second
    matricule dont les cumuls repartent de zéro. Additionner les deux faisait
    rattraper en septembre la réduction générale de tout le CDD."""
    from scripts.reprise_comitech import solde_du_contrat_qui_continue

    cdd = {"cumuls": {"brut_total": 4230.51, "reduction_generale_patronale": -1332.19}}
    apprenti = {"cumuls": {"brut_total": 53.18, "reduction_generale_patronale": -21.17}}
    assert solde_du_contrat_qui_continue([("31/08/2026", apprenti), ("22/06/2026", cdd)]) is apprenti
    assert solde_du_contrat_qui_continue([("22/06/2026", cdd)]) is cdd
