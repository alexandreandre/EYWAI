"""Montant net social : ni prêt, ni frais, ni cantine (audit du 03/11/2026, lot D).

BOSS, « Montant net social » (copie archivée du 08/01/2026, en vigueur jusqu'au
01/10/2026 ; même texte au 01/11/2026) :
- II.A.1, ne sont pas pris en compte « Les remboursements de frais
  professionnels (au réel ou forfaitaires) dans la limite de chacun de leurs
  plafonds d'exonération (ex : nourriture, grand déplacement, trajet
  domicile-travail, indemnité forfaitaire de télétravail […]) » ; question 26 :
  « les remboursements de frais professionnels ne sont pas à inclure dans le
  montant net social » ;
- II.A.1 : « L'ensemble des revenus mentionnés sont pris en compte même en cas
  de saisies sur salaire » : un prêt remboursé ne réduit pas le revenu ;
- question 22 (23 au 01/11/2026) : la participation de l'employeur à un
  restaurant d'entreprise n'est pas prise en compte, et « la participation
  salariale au financement des titres restaurant […] n'est pas déduite du
  montant net social » : la retenue de cantine non plus (verdict D).

Arbitrage D, verdicts 1b et 1c : l'ancien logiciel déduisait les prêts du MNS
et y mettait paniers non soumis, notes de frais et indemnités de transport.
Une société garde ses frais dans le MNS par un réglage (spécificité
documentée, `notes_de_frais_dans_mns`) : elle n'en bouge pas sans accord.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_generator import (
    _is_cantine_input,
    _is_frais_pro_non_soumis_input,
)
from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.frais_professionnels import (
    entree_de_frais_professionnels,
    est_une_saisie_de_frais,
)

pytestmark = pytest.mark.unit

BRUT = 2500.00
COTISATIONS = 550.00
CONTEXTE = SimpleNamespace(year=2026, month=10, cumuls={}, contrat={"specificites_paie": {}})


def _saisie(nom, montant=100.0, soumise=False):
    return {"name": nom, "amount": montant, "is_socially_taxed": soumise, "is_taxable": soumise}


def _mns(primes_non_soumises):
    return calcul_net.calculer_montant_net_social(CONTEXTE, BRUT, COTISATIONS, primes_non_soumises)


# --- Prêts : déjà fait (4c33415e, 03/11/2026), le test le prouve ; le prêt du
# module : `employee_loans/test_pret_hors_net_social.py` ------------------------


def test_un_pret_saisi_en_retenue_ne_baisse_pas_le_net_social():
    assert _mns([{"libelle": "Contrat de prêt", "montant": -100.0}]) == round(BRUT - COTISATIONS, 2)


# --- Cantine : déjà fait (même commit), le test le prouve --------------------


def test_la_retenue_de_cantine_ne_baisse_pas_le_net_social():
    saisie = _saisie("Cantine", -45.0)
    assert _is_cantine_input(saisie)
    retenue = {"libelle": "Cantine", "montant": -45.0, "soumise_a_cotisations": False, "soumise_a_impot": False}
    assert _mns([retenue]) == round(BRUT - COTISATIONS, 2)


# --- Frais : paniers, notes de frais, trajet --------------------------------


@pytest.mark.parametrize(
    "nom",
    [
        "Paniers jours non soumis",
        "Paniers nuits non soumis",
        "Indemnité de panier",
        "Rbst note de frais",
        "Remboursement note de frais",
        "Remboursement de notes de frais",
        "Indemnité forfaitaire dep.",
        "Indemnité de transport",
        "Indemnite de transport",
        "Remboursement transport",
        "Prime de transport (carburant / frais de trajet)",
        "Indemnités kms astreinte",
        "Indemnités kilométriques",
    ],
)
def test_un_frais_non_soumis_est_un_frais(nom):
    assert est_une_saisie_de_frais(_saisie(nom))
    assert _is_frais_pro_non_soumis_input(_saisie(nom))


@pytest.mark.parametrize(
    "nom",
    ["Prime de partage de la valeur (PPV)", "Indemnité activité partielle", "Participation 2025"],
)
def test_un_revenu_non_soumis_n_est_pas_un_frais(nom):
    assert not est_une_saisie_de_frais(_saisie(nom))


def test_une_saisie_soumise_ou_negative_n_est_jamais_un_frais():
    assert not est_une_saisie_de_frais(_saisie("Indemnité de transport", soumise=True))
    assert not est_une_saisie_de_frais(_saisie("Rbst note de frais", -20.0))


def test_un_frais_n_entre_pas_dans_le_net_social():
    panier = entree_de_frais_professionnels(_saisie("Paniers jours non soumis", 66.60))
    transport = entree_de_frais_professionnels(_saisie("Indemnité de transport", 125.0))
    assert _mns([panier, transport]) == round(BRUT - COTISATIONS, 2)


def test_le_panier_est_un_frais_meme_avec_l_ancien_reglage_de_societe():
    """Le réglage `paniers_non_soumis_dans_mns` remettait le panier dans le MNS
    pour suivre l'ancien logiciel : il n'est plus lu (verdict D 1c)."""
    import inspect

    from app.modules.payroll.documents import payslip_generator

    assert "paniers_non_soumis_dans_mns" not in inspect.getsource(payslip_generator)


@pytest.mark.parametrize(
    "nom, frais",
    [
        # Classement d'avant, gardé tel quel sous le réglage de la société.
        ("Remboursement de notes de frais", False),
        ("Indemnité de transport", False),
        ("Indemnite de transport", False),
        ("Prime de transport (carburant / frais de trajet)", False),
        ("Remboursement note de frais (participation)", True),
        ("Rbst note de frais", True),
        ("Indemnité forfaitaire dep.", True),
        ("Paniers jours non soumis", True),
    ],
)
def test_sous_le_reglage_de_la_societe_ses_frais_ne_bougent_pas(nom, frais):
    assert est_une_saisie_de_frais(_saisie(nom), frais_dans_mns=True) is frais
    assert _is_frais_pro_non_soumis_input(_saisie(nom), frais_dans_mns=True) is frais
