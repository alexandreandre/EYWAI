"""À la création, « salaire de base à 35 h » suit la pratique des collègues.

Une fiche créée par l'écran n'avait jamais `salaire_hors_hs_structurelles` :
un salaire saisi en base 35 h (1 867,06 € = 151,67 h × SMIC) était payé comme
le brut de 169 h, sous le SMIC horaire. On propose ce que porte la majorité
des salariés actifs de la société au-delà de 35 h.
"""

from app.modules.employees.domain.valeurs_embauche import valeurs_d_embauche


def _salarie(duree: float, base35: bool | None, statut: str = "actif") -> dict:
    specificites = {} if base35 is None else {"salaire_hors_hs_structurelles": base35}
    return {
        "employment_status": statut,
        "statut": "Non-Cadre",
        "duree_hebdomadaire": duree,
        "specificites_paie": specificites,
    }


def test_la_majorite_des_collegues_a_39_h_en_base_35_h_le_propose():
    employes = [_salarie(39, True), _salarie(39, True), _salarie(39, None), _salarie(35, None)]
    assert valeurs_d_embauche(employes, [])["salaire_hors_hs_structurelles"] is True


def test_une_societe_qui_saisit_le_brut_complet_ne_le_propose_pas():
    employes = [_salarie(39, None), _salarie(39, False), _salarie(39, True)]
    assert valeurs_d_embauche(employes, [])["salaire_hors_hs_structurelles"] is False


def test_sans_collegue_au_dela_de_35_h_rien_n_est_propose():
    employes = [_salarie(35, None), _salarie(39, True, statut="parti")]
    assert valeurs_d_embauche(employes, [])["salaire_hors_hs_structurelles"] is False
