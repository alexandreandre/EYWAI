"""R-209, R-221 : les lignes liées au compteur de récupération ne se corrigent pas en montant.

R-209 : le crédit du compteur est calculé avant la ligne : une heure ajoutée sur
la ligne serait payée ET créditée. R-221 : corriger le paiement du solde laisse
le compteur débité. On renvoie vers le bon geste, sans changer aucun montant.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_du_bulletin import lignes_corrigeables

pytestmark = pytest.mark.unit

HS = {"libelle": "Heures suppl. majorées à 25%", "quantite": 4.0, "taux": 15.0, "gain": 60.0}
SOLDE = {"libelle": "Paiement solde heures de récupération", "gain": 40.0}
BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.0, "gain": 1820.0}


def _ligne(data, libelle):
    return next(l for l in lignes_corrigeables(data) if l.libelle == libelle)


def test_heure_sup_avec_compteur_renvoie_aux_heures_declarees():
    data = {"calcul_du_brut": [HS], "modulation_account": {"hs_credited": 4.0, "regle": "account_all"}}
    ligne = _ligne(data, HS["libelle"])
    assert ligne.mode is None
    assert "heures déclarées" in ligne.raison
    assert "au compteur" in ligne.raison


def test_heure_sup_sans_compteur_reste_corrigeable():
    ligne = _ligne({"calcul_du_brut": [HS]}, HS["libelle"])
    assert ligne.mode is not None
    assert ligne.raison is None


def test_societe_qui_paie_ses_heures_rien_au_compteur_reste_corrigeable():
    """Compteur ouvert mais heures payées : aucune heure créditée, pas de double compte."""
    data = {
        "calcul_du_brut": [HS],
        "modulation_account": {"hs_credited": 0.0, "hs_paid": 4.0, "regle": "pay_all"},
        "pied_de_page": {"solde_conges": {"recuperation": {"solde": 0}}},
    }
    assert _ligne(data, HS["libelle"]).mode is not None


def test_une_correction_deja_posee_reste_retirable():
    posee = {**HS, "correction": {"ligne": "brut:heures_sup:25", "saisie_id": "s1"}}
    data = {"calcul_du_brut": [posee], "modulation_account": {"hs_credited": 4.0}}
    assert _ligne(data, HS["libelle"]).mode is not None


def test_le_paiement_du_solde_se_corrige_depuis_la_carte():
    ligne = _ligne({"calcul_du_brut": [SOLDE]}, SOLDE["libelle"])
    assert ligne.mode is None
    assert "Heures de récupération" in ligne.raison
    assert "Annuler le paiement" in ligne.raison


def test_les_autres_lignes_ne_changent_pas():
    data = {"calcul_du_brut": [BASE], "modulation_account": {"hs_credited": 4.0}}
    assert _ligne(data, BASE["libelle"]).mode is not None
