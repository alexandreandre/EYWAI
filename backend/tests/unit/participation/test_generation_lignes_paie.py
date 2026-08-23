"""
Génération des lignes de paie d'une campagne de participation.

Le 23/08, l'ajout d'un `company_id` obligatoire sur
`create_monthly_inputs_batch` a laissé cet appelant avec l'ancienne
signature : la route renvoyait 500 en production. Aucun test ne couvrait
ce chemin — d'où ce fichier, qui exerce la VRAIE fonction (seules les
frontières repository et saisies mensuelles sont simulées, cette dernière
avec `autospec` pour qu'un appel sous-alimenté lève, comme en production).
"""

from __future__ import annotations

from unittest.mock import patch

CAMPAGNE = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE = "bbbbbbbb-2222-2222-2222-222222222222"
SALARIE = "cccccccc-3333-3333-3333-333333333333"


def _bulletin() -> dict:
    return {
        "id": "dddddddd-4444-4444-4444-444444444444",
        "employee_id": SALARIE,
        "status": "responded",
        "choice_type": "cash",
        "dispositif_type": "participation",
        "cash_amount": 500.0,
        "pee_amount": 0.0,
        "gross_amount": 550.0,
    }


class TestLignesDePaieCampagne:
    def test_la_societe_de_la_campagne_est_transmise_aux_saisies(self):
        from app.modules.participation.application import campaign_service
        from app.modules.participation.schemas.campaign_requests import (
            GeneratePayrollLinesRequest,
        )

        with (
            patch.object(campaign_service, "campaign_repository") as repo,
            patch.object(
                campaign_service, "_employment_statuses", return_value={}
            ),
            patch.object(
                campaign_service,
                "create_monthly_inputs_batch",
                autospec=True,
            ) as lot,
            patch.object(campaign_service, "_tag_campaign_inputs"),
            patch.object(
                campaign_service, "_campaign_detail", return_value=None
            ),
        ):
            repo.get_campaign.return_value = {
                "id": CAMPAGNE,
                "company_id": SOCIETE,
                "year": 2026,
                "status": "responded",
            }
            repo.list_bulletins.return_value = [_bulletin()]
            repo.update_campaign.return_value = {"id": CAMPAGNE}
            lot.return_value = type(
                "R", (), {"inserted_count": 1, "inserted_ids": ["mi-1"]}
            )()

            campaign_service.generate_payroll_lines(
                CAMPAGNE,
                SOCIETE,
                GeneratePayrollLinesRequest(payroll_year=2026, payroll_month=7),
            )

        lot.assert_called_once()
        appel = lot.call_args
        societe_transmise = (
            appel.kwargs.get("company_id")
            if "company_id" in appel.kwargs
            else appel.args[1]
        )
        assert societe_transmise == SOCIETE
