"""Bulletin remis (D4, D5) : ce que voit le salarié, et ce qui ne se modifie plus."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import commands as cmds
from app.modules.payslips.application import comparison_service as svc
from app.modules.payslips.application import period_edit_lock as verrou
from app.modules.payslips.application import remise, service
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipForbiddenError,
    UserContext,
)
from app.modules.payslips.application.period_edit_lock import (
    assert_payslip_manual_edit_allowed,
    enrich_payslip_detail_with_edit_lock,
)
from app.modules.payslips.infrastructure import queries as q

pytestmark = pytest.mark.unit


def _ligne(month: int, validated_at: str) -> dict:
    return {
        "id": f"p-{month}",
        "company_id": "co-1",
        "month": month,
        "year": 2026,
        "status": "valide",
        "validated_at": validated_at,
        "pdf_storage_path": f"co-1/emp-1/{month}.pdf",
        "payslip_data": {"net_a_payer": 1500},
    }


def test_le_salarie_ne_voit_pas_un_bulletin_valide_avant_sa_remise():
    lignes = [_ligne(10, "2026-10-28T16:00:00+00:00"), _ligne(9, "2026-10-03T08:00:00+00:00")]
    fake = MagicMock()
    table = fake.table.return_value
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=lignes)
    chemins = {ligne["pdf_storage_path"]: "https://signe" for ligne in lignes}

    with (
        patch.object(q, "supabase", fake),
        patch.object(q, "jour_de_la_societe", return_value=1),
        patch.object(q, "aujourd_hui_local", return_value=date(2026, 10, 31)),
        patch.object(q, "create_payslip_url_maps", return_value=(chemins, chemins)) as signer,
    ):
        resultat = q.get_my_payslips("emp-1")

    assert [b["month"] for b in resultat] == [9]
    signer.assert_called_once_with(["co-1/emp-1/9.pdf"], 3600)


# --- Gel du bulletin remis (D4) ---

REMIS = {
    "id": "p-10",
    "company_id": "co-1",
    "employee_id": "emp-1",
    "year": 2026,
    "month": 10,
    "status": "valide",
    "validated_at": "2026-10-28T16:00:00+00:00",
    "payslip_data": {},
}
APRES = date(2026, 11, 2)
AVANT = date(2026, 10, 30)


def _guard(existant, *, modifier_bulletin_remis=False, aujourd_hui=APRES):
    commande = GeneratePayslipInput(
        employee_id="emp-1",
        year=2026,
        month=10,
        regenerer_bulletin_valide=True,
        modifier_bulletin_remis=modifier_bulletin_remis,
    )
    with (
        patch.object(cmds, "_fetch_existing_payslip", return_value=existant),
        patch.object(cmds, "jour_de_la_societe", return_value=1),
        patch.object(cmds, "aujourd_hui_local", return_value=aujourd_hui),
    ):
        return cmds._check_validated_guard(commande)


def test_regenerer_un_bulletin_remis_est_refuse():
    with pytest.raises(PayslipBadRequestError, match="remis au salarié le 01/11/2026"):
        _guard(REMIS)


def test_regenerer_un_bulletin_valide_pas_encore_remis_reste_possible():
    assert _guard(REMIS, aujourd_hui=AVANT) == REMIS


def test_l_administrateur_peut_regenerer_un_bulletin_remis():
    assert _guard(REMIS, modifier_bulletin_remis=True) == REMIS


def test_corriger_un_bulletin_remis_est_refuse_avant_toute_ecriture():
    with pytest.raises(ValueError, match="il ne se modifie plus"):
        assert_payslip_manual_edit_allowed(
            REMIS, today=APRES, cutoff_day=15, lock_enabled=True, jour_remise=1
        )
    assert_payslip_manual_edit_allowed(
        REMIS, today=AVANT, cutoff_day=15, lock_enabled=True, jour_remise=1
    )
    assert_payslip_manual_edit_allowed(
        REMIS, bypass_lock=True, today=APRES, cutoff_day=15, lock_enabled=True, jour_remise=1
    )


def test_le_gel_tient_meme_verrou_de_periode_coupe():
    with pytest.raises(ValueError, match="il ne se modifie plus"):
        assert_payslip_manual_edit_allowed(
            REMIS, today=APRES, cutoff_day=15, lock_enabled=False, jour_remise=1
        )


def test_l_ecran_rh_dit_la_remise_et_le_verrou():
    avant = enrich_payslip_detail_with_edit_lock(
        REMIS, today=AVANT, cutoff_day=15, lock_enabled=True, jour_remise=1
    )
    assert avant["remis_le"] == "2026-11-01"
    assert avant["bulletin_remis"] is False
    assert avant["manual_edit_locked"] is False
    # Le verrou de période dirait le 14/11 : la remise du 01/11 vient avant.
    assert avant["manual_edit_lock_until"] == "2026-10-31"

    apres = enrich_payslip_detail_with_edit_lock(
        REMIS, today=APRES, cutoff_day=15, lock_enabled=True, jour_remise=1
    )
    assert apres["bulletin_remis"] is True
    assert apres["manual_edit_locked"] is True
    assert "remis au salarié le 01/11/2026" in apres["manual_edit_lock_reason"]

    brouillon = enrich_payslip_detail_with_edit_lock(
        {**REMIS, "status": "brouillon"}, today=APRES, cutoff_day=28, lock_enabled=True, jour_remise=1
    )
    assert brouillon["remis_le"] is None
    assert brouillon["bulletin_remis"] is False


# --- Détail ouvert par le salarié ---


def _detail_salarie(aujourd_hui):
    salarie = UserContext(
        user_id="emp-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _c: False,
        active_company_id="co-1",
        resolved_employee_id="emp-1",
    )
    with (
        patch.object(service, "get_payslip_details", return_value=dict(REMIS)),
        patch.object(service, "_comparaison_du_bulletin", return_value=None),
        patch.object(verrou, "jour_de_la_societe", return_value=1),
        patch.object(verrou, "aujourd_hui_local", return_value=aujourd_hui),
        patch.object(verrou, "get_payslip_edit_lock_config", return_value={"cutoff_day_of_next_month": 15, "enabled": True}),
    ):
        return service.get_payslip_details_for_user("p-10", salarie)


def test_le_salarie_n_ouvre_pas_un_bulletin_avant_sa_remise():
    with pytest.raises(PayslipForbiddenError, match="disponible le 01/11/2026"):
        _detail_salarie(AVANT)
    assert _detail_salarie(APRES)["id"] == "p-10"


# --- Notification au jour de la remise ---


def _valider_octobre(aujourd_hui, payslip_data=None):
    detail = {
        "id": "p-10", "employee_id": "emp-1", "company_id": "co-1",
        "year": 2026, "month": 10, "status": "brouillon",
        "payslip_data": payslip_data or {"net_a_payer": 1500},
    }
    resultat = MagicMock()
    resultat.alerts = []
    with (
        patch.object(svc, "payslip_meta_reader"),
        patch.object(svc, "_ensure_edit_meta"),
        patch.object(svc, "get_payslip_details", return_value=detail),
        patch.object(svc, "fetch_previous_validated_payslip", return_value=None),
        patch.object(svc, "fetch_employee_statut", return_value="Non-Cadre"),
        patch.object(svc, "fetch_recent_nets_asc_for_r10", return_value=[]),
        patch.object(svc, "compute_comparison", return_value=resultat),
        patch.object(svc, "mark_payslip_validated", return_value={}),
        patch.object(svc, "jour_de_la_societe", return_value=1),
        patch.object(svc, "aujourd_hui_local", return_value=aujourd_hui),
        patch.object(svc, "_notify_payslip_available", return_value=True) as notifier,
        patch.object(svc, "_persist_salarie_notifie_le") as marquer,
    ):
        ctx = MagicMock()
        ctx.user_id = "rh-1"
        svc.validate_payslip_for_user("p-10", ctx)
    return notifier, marquer


def test_valide_avant_sa_remise_le_salarie_n_est_pas_encore_notifie():
    notifier, marquer = _valider_octobre(date(2026, 10, 28))
    notifier.assert_not_called()
    marquer.assert_not_called()


def test_valide_apres_la_date_le_salarie_est_notifie_tout_de_suite():
    notifier, marquer = _valider_octobre(date(2026, 11, 3))
    notifier.assert_called_once()
    marquer.assert_called_once()


def test_le_bulletin_de_sortie_est_notifie_a_sa_validation():
    notifier, _ = _valider_octobre(
        date(2026, 10, 18), payslip_data={"net_a_payer": 900, "bulletin_de_sortie": True}
    )
    notifier.assert_called_once()


# --- Tâche quotidienne ---


def test_la_tache_previent_les_salaries_dont_le_bulletin_est_remis_ce_jour():
    lignes = [{**REMIS, "payslip_data": {"net_a_payer": 1500}}]
    fake = MagicMock()
    table = fake.table.return_value
    table.select.return_value = table
    table.eq.return_value = table
    table.gte.return_value = table
    table.execute.return_value = MagicMock(data=lignes)
    with (
        patch.object(remise, "supabase", fake),
        patch.object(remise, "jour_de_la_societe", return_value=1),
        patch.object(remise, "_notify_payslip_available", return_value=True) as notifier,
        patch.object(remise, "_persist_salarie_notifie_le") as marquer,
    ):
        bilan = remise.notifier_bulletins_remis("co-1", aujourd_hui=date(2026, 11, 1))

    notifier.assert_called_once_with("emp-1", "co-1", 2026, 10)
    marquer.assert_called_once_with("p-10", {"net_a_payer": 1500})
    assert bilan == {"notifies": 1, "echecs": 0}


def test_un_echec_d_envoi_ne_pose_pas_la_marque():
    lignes = [dict(REMIS)]
    fake = MagicMock()
    table = fake.table.return_value
    table.select.return_value = table
    table.eq.return_value = table
    table.gte.return_value = table
    table.execute.return_value = MagicMock(data=lignes)
    with (
        patch.object(remise, "supabase", fake),
        patch.object(remise, "jour_de_la_societe", return_value=1),
        patch.object(remise, "_notify_payslip_available", return_value=False),
        patch.object(remise, "_persist_salarie_notifie_le") as marquer,
    ):
        bilan = remise.notifier_bulletins_remis("co-1", aujourd_hui=date(2026, 11, 1))

    marquer.assert_not_called()
    assert bilan == {"notifies": 0, "echecs": 1}


def test_le_salarie_n_a_pas_la_courbe_d_un_bulletin_avant_sa_remise():
    salarie = UserContext(
        user_id="emp-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _c: False,
        active_company_id="co-1",
    )
    with (
        patch.object(svc, "get_payslip_details", return_value=dict(REMIS)),
        patch.object(svc, "fetch_validated_payslips_strictly_before", return_value=[]),
        patch.object(svc, "fetch_employee_statut", return_value=None),
        patch.object(verrou, "jour_de_la_societe", return_value=1),
        patch.object(verrou, "aujourd_hui_local", return_value=AVANT),
        pytest.raises(PayslipForbiddenError, match="disponible le 01/11/2026"),
    ):
        svc.get_payslip_trend_for_user("p-10", salarie)
