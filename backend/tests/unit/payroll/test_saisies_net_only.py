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
    # « Rbst note de frais » (SNDF) : au net à payer, hors MNS. « Remboursement de
    # notes de frais » aussi depuis l'audit du 03/11/2026 (verdict D 1c), sauf
    # dans la société qui garde ses frais dans le MNS par réglage (S27).
    assert _is_frais_pro_non_soumis_input(
        {"name": "Rbst note de frais", "amount": 566.58, "is_socially_taxed": False}
    )
    remboursement = {"name": "Remboursement de notes de frais", "amount": 84.59, "is_socially_taxed": False}
    assert _is_frais_pro_non_soumis_input(remboursement)
    assert not _is_frais_pro_non_soumis_input(remboursement, frais_dans_mns=True)


def test_prime_non_soumise_ordinaire_n_est_ni_nette_ni_frais_pro():
    row = {"name": "Prime exceptionnelle exonérée", "amount": 11.25, "is_socially_taxed": False}
    assert not _is_net_a_payer_only_correction_input(row)
    assert not _is_frais_pro_non_soumis_input(row)


def test_le_remboursement_de_transport_est_un_frais_pas_un_revenu():
    """Trajet domicile-travail : un frais, hors MNS (BOSS, Montant net social,
    II.A.1 ; audit du 03/11/2026, verdict D 1c). Il restait une prime non soumise
    ordinaire, dans le MNS, comme chez l'ancien logiciel."""
    row = {"name": "Remboursement transport", "amount": 11.25, "is_socially_taxed": False}
    assert not _is_net_a_payer_only_correction_input(row)
    assert _is_frais_pro_non_soumis_input(row)


class TestSaisieMarqueeSurLeNet:
    """La case « sur le net » de la saisie décide, pas son libellé (29/09/2026)."""

    def test_une_retenue_marquee_sur_le_net_ne_touche_que_le_net(self):
        from app.modules.payroll.documents.payslip_generator import (
            _is_net_a_payer_only_correction_input,
        )

        ligne = {"name": "Net négatif de juillet", "amount": -419.75, "sur_le_net": True}
        assert _is_net_a_payer_only_correction_input(ligne) is True

    def test_un_versement_marque_sur_le_net_aussi(self):
        from app.modules.payroll.documents.payslip_generator import (
            _is_net_a_payer_only_correction_input,
        )

        assert _is_net_a_payer_only_correction_input({"name": "Avance", "amount": 300.0, "sur_le_net": True})

    def test_sans_la_case_une_prime_reste_une_prime(self):
        from app.modules.payroll.documents.payslip_generator import (
            _is_net_a_payer_only_correction_input,
        )

        assert not _is_net_a_payer_only_correction_input({"name": "Net négatif de juillet", "amount": -419.75})
        # Les anciens libellés restent reconnus.
        assert _is_net_a_payer_only_correction_input({"name": "Report NAP négatif", "amount": -419.75})


def test_remboursement_de_pret_saisi_a_la_main_est_une_retenue_nette():
    # « Contrat de prêt <nom> » (Mont Blanc 2026, saisies d'avant la case) : le
    # salarié rembourse un prêt sur son net, comme une saisie sur salaire ; le
    # montant net social compte les revenus « même en cas de saisies sur
    # salaire » (BOSS, Montant net social, II.A.1). Les prêts du module sont
    # déjà retenus après le calcul, hors montant net social.
    assert _is_net_a_payer_only_correction_input({"name": "Contrat de prêt X", "amount": -250.0})
    assert _is_net_a_payer_only_correction_input({"name": "Contrat de pret Y", "amount": -90.0})


def test_pret_verse_au_salarie_n_est_pas_une_retenue():
    # Un prêt versé (montant positif) n'est pas classé par le libellé.
    assert not _is_net_a_payer_only_correction_input({"name": "Contrat de prêt X", "amount": 250.0})


def test_avance_de_participation_reste_hors_du_canal_net():
    # Acompte ou avance sur participation : suit le mécanisme de la participation.
    assert not _is_net_a_payer_only_correction_input(
        {"name": "Avance participation 2025 (déjà versée)", "amount": -500.0}
    )
