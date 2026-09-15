"""Un trop-perçu repris se retient sur le net, pas sur le montant net social.

Le montant net social se définit comme les sommes versées au salarié diminuées
des seules cotisations sociales obligatoires : les retenues sur salaire —
acomptes, saisies, reprises d'un trop-versé — en sont exclues. Elles ne touchent
que le net à payer.

Référence : bulletin d'avril 2026 de Girerd (Colorplast). Une ligne « trop
perçu mars 2026 » de 1,25 € : le montant net social reste à 3 150,85 et le net
à payer descend à 3 051,48, soit 3 150,85 − 98,12 de mutuelle famille − 1,25.

Le moteur route ces lignes par leur libellé, comme il le fait déjà pour les
acomptes et les saisies-arrêts.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.payslip_generator import _is_net_a_payer_only_correction_input

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("libelle", [
    "Trop-perçu mars 2026",
    "TROP PERCU MARS 2026",
    "Régularisation trop perçu",
])
def test_un_trop_percu_ne_touche_que_le_net(libelle):
    assert _is_net_a_payer_only_correction_input({"name": libelle, "amount": -1.25}) is True


@pytest.mark.parametrize("libelle", [
    "Acompte 04/2026",
    "Saisie sur salaire",
    "GAN Mutuelle famille",
])
def test_les_retenues_deja_connues_restent_reconnues(libelle):
    assert _is_net_a_payer_only_correction_input({"name": libelle, "amount": -100.0}) is True


@pytest.mark.parametrize("libelle", [
    "Prime exceptionnelle",
    "Indemnité de transport",
    "Remboursement de notes de frais",
])
def test_un_versement_ordinaire_n_est_pas_une_retenue_nette(libelle):
    assert _is_net_a_payer_only_correction_input({"name": libelle, "amount": 150.0}) is not True
