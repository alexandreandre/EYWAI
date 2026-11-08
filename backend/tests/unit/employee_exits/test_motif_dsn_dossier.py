"""Le motif DSN sur le dossier de sortie : enregistré, refusé, relu (R-449)."""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_export.domain.motif_rupture import resume_du_dossier
from app.modules.employee_exits.application.commands import update_employee_exit
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError

CDD = {"contract_type": "CDD", "contract_end_date": "2026-09-30"}


def _dossier(**extra):
    return {
        "id": "x1",
        "employee_id": "e1",
        "company_id": "c1",
        "exit_type": "fin_cdd",
        "status": "demission_recue",
        "last_working_day": "2026-09-15",
        "exit_request_date": "2026-09-01",
        "exit_notes": {},
        **extra,
    }


@pytest.fixture
def repo():
    with patch(
        "app.modules.employee_exits.application.commands.EmployeeExitRepository"
    ) as classe, patch(
        "app.modules.employee_exits.application.commands.get_employee_full", return_value=CDD
    ):
        depot = MagicMock()
        classe.return_value = depot
        depot.update.side_effect = lambda _id, _c, data: data
        yield depot


def test_le_motif_choisi_est_range_dans_les_notes(repo):
    repo.get_by_id.return_value = _dossier()
    update_employee_exit("x1", "c1", {"motif_dsn": "037"}, supabase_client=MagicMock())
    assert repo.update.call_args.args[2]["exit_notes"]["motif_dsn"] == "037"


def test_le_motif_incompatible_est_refuse_et_dit_quoi_faire(repo):
    repo.get_by_id.return_value = _dossier()
    with pytest.raises(EmployeeExitApplicationError) as refus:
        update_employee_exit("x1", "c1", {"motif_dsn": "020"}, supabase_client=MagicMock())
    assert refus.value.status_code == 400
    assert "Choisissez" in refus.value.detail
    repo.update.assert_not_called()


def test_retirer_le_motif_revient_a_la_proposition(repo):
    repo.get_by_id.return_value = _dossier(exit_notes={"motif_dsn": "037"})
    update_employee_exit("x1", "c1", {"motif_dsn": None}, supabase_client=MagicMock())
    assert "motif_dsn" not in repo.update.call_args.args[2]["exit_notes"]


def test_un_changement_de_type_qui_casse_le_motif_est_refuse(repo):
    repo.get_by_id.return_value = _dossier(exit_notes={"motif_dsn": "037"})
    with pytest.raises(EmployeeExitApplicationError, match="motif"):
        update_employee_exit(
            "x1", "c1", {"exit_type": "rupture_conventionnelle", "exit_notes": {"motif_dsn": "037"}},
            supabase_client=MagicMock(),
        )


def test_le_dossier_dit_le_motif_propose_et_ce_qu_il_faut_faire():
    resume = resume_du_dossier(_dossier(), CDD)
    assert resume["choisi"] is None and resume["retenu"] is None
    assert "terme" in resume["alerte"]
    assert [o["code"] for o in resume["options"]] == ["031", "036", "037", "084", "033", "083", "095", "096", "097"]
