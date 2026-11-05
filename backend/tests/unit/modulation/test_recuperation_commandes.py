"""Choix du mois et paiement du solde (spec 2026-11-05 § 3.3 et 3.4)."""

from unittest.mock import patch

import pytest

from app.modules.modulation.application import hour_account_commands as cmd
from app.modules.modulation.domain.hour_account_rules import (
    heures_payees_du_mois,
    saisie_paiement_solde,
)

pytestmark = pytest.mark.unit

_VRAIE_GARDE = cmd._exiger_un_bulletin_qui_porte_le_compteur

_C = "app.modules.modulation.application.hour_account_commands"


@pytest.fixture(autouse=True)
def compteur_ouvert():
    with patch(f"{_C}._exiger_un_bulletin_qui_porte_le_compteur"):
        yield


def _mvt(t, h, annee, mois, statut="validated", source="manual_rh"):
    return {
        "movement_type": t,
        "hours": h,
        "year": annee,
        "month": mois,
        "status": statut,
        "source": source,
    }


def test_heures_payees_du_mois_ne_lit_que_les_paiements_actifs_du_mois():
    mvts = [
        _mvt("debit_payout", 2.0, 2027, 1),
        _mvt("debit_payout", 1.0, 2027, 1, statut="cancelled"),
        _mvt("debit_payout", 4.0, 2026, 12),
        _mvt("debit_recovery", 3.0, 2027, 1, source="absence"),
    ]
    assert heures_payees_du_mois(mvts, 2027, 1) == 2.0


def test_la_ligne_du_bulletin_est_une_prime_au_taux_de_base():
    saisie = saisie_paiement_solde(2.5, 12.0)
    assert saisie == {
        "prime_id": "paiement_solde_recuperation",
        "libelle": "Paiement solde heures de récupération",
        "montant": 30.0,
        "quantity": 2.5,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
    }


@patch(f"{_C}.sync_account_balance_cache")
@patch(f"{_C}.repo.insert_movement", return_value={"id": "m-1"})
@patch(f"{_C}.repo.list_movements_for_employee")
def test_payer_le_solde_pose_un_debit_du_mois(mock_list, mock_insert, _sync):
    mock_list.return_value = [_mvt("opening_balance", 2.0, 2026, 9)]
    cmd.payer_le_solde("soc", "emp", 2027, 1, 2.0)
    ligne = mock_insert.call_args[0][0]
    assert ligne["movement_type"] == "debit_payout"
    assert (ligne["year"], ligne["month"], ligne["hours"]) == (2027, 1, 2.0)
    assert ligne["status"] == "validated"


@patch(f"{_C}.repo.insert_movement")
@patch(f"{_C}.repo.list_movements_for_employee")
def test_payer_plus_que_le_solde_est_refuse(mock_list, mock_insert):
    mock_list.return_value = [_mvt("opening_balance", 2.0, 2026, 9)]
    with pytest.raises(ValueError, match="2 h"):
        cmd.payer_le_solde("soc", "emp", 2027, 1, 3.0)
    mock_insert.assert_not_called()


@patch(f"{_C}.otr_repo.upsert_decision")
def test_payer_ce_mois_enregistre_une_decision_toutes_heures_payees(mock_upsert):
    cmd.choisir_le_mois("soc", "emp", 2026, 10, choix="payer", heures_sup=4.0, par="rh-1")
    decision = mock_upsert.call_args[0][0]
    assert decision["hours_to_account"] == 0
    assert decision["hours_to_pay"] == 4.0
    assert decision["status"] == "validated"


@patch(f"{_C}.otr_repo.supprimer_decision")
def test_revenir_a_la_regle_supprime_la_decision(mock_suppr):
    cmd.choisir_le_mois("soc", "emp", 2026, 10, choix="regle", heures_sup=4.0, par="rh-1")
    mock_suppr.assert_called_once_with("emp", 2026, 10)


@patch(f"{_C}.repo.insert_movement")
@patch(f"{_C}.repo.list_movements_for_employee")
def test_le_credit_du_mois_ne_se_paie_pas_comme_un_solde(mock_list, mock_insert):
    """Sinon : prime + heures sup payées si la RH paie ensuite les heures du mois."""
    mock_list.return_value = [
        _mvt("opening_balance", 2.0, 2026, 9),
        _mvt("credit_hs", 5.0, 2026, 10, source="payroll_auto"),
    ]
    with pytest.raises(ValueError, match="2 h"):
        cmd.payer_le_solde("soc", "emp", 2026, 10, 7.0)
    mock_insert.assert_not_called()


@pytest.mark.parametrize(
    "ligne, attendu",
    [
        (None, None),
        ({"status": "brouillon", "origine": "genere", "year": 2026, "month": 10, "company_id": "c"}, None),
        ({"status": "valide", "origine": "genere", "year": 2026, "month": 10, "company_id": "c"}, "validé"),
        ({"status": "brouillon", "origine": "importe", "year": 2026, "month": 9, "company_id": "c"}, "repris"),
        ({"status": "brouillon", "origine": "calcule", "manually_edited": True, "year": 2026, "month": 10, "company_id": "c"}, "retouches"),
    ],
)
def test_un_bulletin_fige_refuse_le_geste(ligne, attendu):
    from app.modules.modulation.application import hour_account_queries as q

    with patch.object(q, "_bulletin_du_mois", return_value=ligne), patch(
        "app.modules.payslips.application.period_edit_lock.enrich_payslip_detail_with_edit_lock",
        side_effect=lambda d, **k: {**d, "manual_edit_locked": False},
    ):
        raison = q.raison_bulletin_fige("e", 2026, 10)
    if attendu is None:
        assert raison is None
    else:
        assert attendu in raison


@patch(f"{_C}.otr_repo.upsert_decision")
def test_mettre_au_compteur_enregistre_les_heures_au_compteur(mock_upsert):
    cmd.choisir_le_mois("soc", "emp", 2026, 10, choix="compteur", heures_sup=4.0, par="rh-1")
    decision = mock_upsert.call_args[0][0]
    assert decision["hours_to_account"] == 4.0
    assert decision["hours_to_pay"] == 0


@pytest.mark.parametrize(
    "ouvert, forfait, message",
    [(False, False, "pas ouvert"), (True, True, "forfait jours"), (True, False, None)],
)
def test_un_geste_que_le_bulletin_ne_porterait_pas_est_refuse(ouvert, forfait, message):
    from unittest.mock import MagicMock

    # La vraie garde, sous le patch de la fixture.
    vraie = _VRAIE_GARDE
    with patch(f"{_C}.repo.get_modulation_settings", return_value=MagicMock(hour_account_enabled=ouvert)), patch(
        f"{_C}.repo.est_au_forfait_jours", return_value=forfait
    ):
        if message:
            with pytest.raises(ValueError, match=message):
                vraie("soc", "emp")
        else:
            vraie("soc", "emp")


@patch(f"{_C}.sync_account_balance_cache")
@patch(f"{_C}.repo.insert_movements", return_value=[])
def test_les_debits_d_une_recuperation_partent_ensemble(mock_insert, _sync):
    cmd.create_debit_recovery_movements(
        "soc", "emp", {(2026, 8): {"2026-08-03": 7.0}, (2026, 7): {"2026-07-31": 7.0}},
        reference_id="r",
    )
    mock_insert.assert_called_once()
    lignes = mock_insert.call_args[0][0]
    assert [(l["month"], l["hours"], l["metadata"]) for l in lignes] == [
        (7, 7.0, {"jours": {"2026-07-31": 7.0}}),
        (8, 7.0, {"jours": {"2026-08-03": 7.0}}),
    ]


def test_le_solde_se_recale_sur_les_annees_suivantes():
    from app.modules.modulation.application import hour_account_queries as q

    Q = "app.modules.modulation.application.hour_account_queries"
    mvts = [_mvt("opening_balance", 2.0, 2026, 9), _mvt("debit_payout", 1.0, 2026, 12)]
    with patch(f"{Q}.repo.list_movements_for_employee", return_value=mvts), patch(
        f"{Q}.repo.annees_de_compteur", return_value=[2026, 2027]
    ), patch(f"{Q}.repo.list_employee_counters", return_value=[]), patch(
        f"{Q}.repo.upsert_employee_counter"
    ) as ecrire:
        assert q.sync_account_balance_cache("soc", "emp", 2026) == 1.0
    assert [(c.args[2], c.kwargs["account_balance_hours"]) for c in ecrire.call_args_list] == [
        (2026, 1.0),
        (2027, 1.0),
    ]
