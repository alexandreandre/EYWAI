"""Classement des saisies mensuelles hors assiette : acompte, avance sur
salaire, frais professionnels (cf. bulletins du cabinet MAJI / ZONE 404 2026)."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.payslip_generator import (
    _is_frais_pro_non_soumis_input,
    _is_net_a_payer_only_correction_input,
)

pytestmark = pytest.mark.unit


def test_acompte_negatif_est_une_retenue_nette():
    assert _is_net_a_payer_only_correction_input({"name": "Acompte 01/2026", "amount": -2000.0})


def test_acompte_positif_n_est_pas_une_correction_nette():
    assert not _is_net_a_payer_only_correction_input({"name": "Acompte 01/2026", "amount": 2000.0})


def test_avance_sur_salaire_versee_est_un_ajout_net():
    # ANDRE MAJI 02/2026 : 3 819,33 versés pendant un arrêt non maintenu, hors
    # net social et net imposable, récupérés ensuite en « Acomptes ».
    assert _is_net_a_payer_only_correction_input({"name": "Avance sur salaire", "amount": 3819.33})


def test_avance_sur_salaire_recuperee_reste_nette():
    assert _is_net_a_payer_only_correction_input({"name": "Avance sur salaire", "amount": -500.0})


def test_note_de_frais_sndf_hors_net_social():
    # « Rbst note de frais » (SNDF) : au net à payer, hors MNS — mais pas
    # « Remboursement de notes de frais » (Colorplast), qui reste dans le MNS.
    assert _is_frais_pro_non_soumis_input(
        {"name": "Rbst note de frais", "amount": 566.58, "is_socially_taxed": False}
    )
    assert not _is_frais_pro_non_soumis_input(
        {"name": "Remboursement de notes de frais", "amount": 84.59, "is_socially_taxed": False}
    )


def test_prime_non_soumise_ordinaire_n_est_ni_nette_ni_frais_pro():
    row = {"name": "Remboursement transport", "amount": 11.25, "is_socially_taxed": False}
    assert not _is_net_a_payer_only_correction_input(row)
    assert not _is_frais_pro_non_soumis_input(row)
