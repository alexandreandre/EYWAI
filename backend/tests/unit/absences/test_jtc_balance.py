"""Solde JTC — droit de l'année figé moins jours posés, jamais mêlé aux CP."""

from datetime import date

from app.modules.absences.application.balance_display import balances_to_api_list
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    compute_absence_balances,
    compute_jtc_balance,
)


ACTIVE = LeavePolicySettings(jtc_enabled=True)
REF = date(2026, 6, 30)


def _jtc_request(*days: str) -> dict:
    # `selected_days` est un tableau de dates en base : une liste de chaînes ISO
    # côté Python, pas des dictionnaires (cf. `_parse_absence_day` dans rules.py).
    return {
        "type": "jtc",
        "status": "validated",
        "selected_days": list(days),
    }


def test_sans_activation_le_solde_jtc_est_nul():
    solde = compute_jtc_balance(
        [],
        REF,
        policy=LeavePolicySettings(),
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["acquis"] == 0
    assert solde["solde"] == 0


def test_le_droit_de_lannee_est_le_solde_douverture():
    solde = compute_jtc_balance(
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["acquis"] == 3
    assert solde["pris"] == 0
    assert solde["solde"] == 3


def test_les_jours_poses_sont_decomptes():
    solde = compute_jtc_balance(
        [_jtc_request("2026-03-10")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["pris"] == 1
    assert solde["solde"] == 2


def test_les_jours_poses_une_autre_annee_ne_comptent_pas():
    """Le JTC se pose sur l'année civile N : un jour de 2025 ne touche pas 2026."""
    solde = compute_jtc_balance(
        [_jtc_request("2025-03-10")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["pris"] == 0
    assert solde["solde"] == 3


def test_le_solde_ne_devient_jamais_negatif():
    solde = compute_jtc_balance(
        [_jtc_request("2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["solde"] == 0


def test_le_jtc_nest_pas_ajoute_au_total_des_conges_payes():
    """Exigence explicite de la note : deux compteurs séparés."""
    soldes = compute_absence_balances(
        date(2015, 3, 1),
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert soldes["jtc"]["solde"] == 3
    assert soldes["conges_payes"]["acquis"] == soldes["cp_legal_days"]


def test_la_ligne_jtc_apparait_quand_le_compteur_est_actif():
    soldes = compute_absence_balances(
        date(2015, 3, 1),
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=2),
    )
    lignes = balances_to_api_list(soldes, policy=ACTIVE)
    jtc = [ligne for ligne in lignes if ligne["type"] == "JTC"]
    assert len(jtc) == 1
    assert jtc[0]["remaining"] == 2


def test_aucune_ligne_jtc_pour_une_societe_non_concernee():
    """Les six autres sociétés ne doivent pas voir le compteur du tout."""
    policy = LeavePolicySettings()
    soldes = compute_absence_balances(date(2015, 3, 1), [], REF, policy=policy)
    lignes = balances_to_api_list(soldes, policy=policy)
    assert not [ligne for ligne in lignes if ligne["type"] == "JTC"]
