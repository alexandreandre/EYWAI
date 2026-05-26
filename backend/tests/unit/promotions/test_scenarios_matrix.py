"""
Matrice paramétrée des scénarios promotions (catalogue SCENARIOS.md).

Chaque test ID du plan A–G a une couverture automatisée minimale.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.promotions.application import commands
from app.modules.promotions.domain import rules as domain_rules
from app.modules.promotions.infrastructure.providers import EmployeeUpdater
from app.modules.promotions.schemas import PromotionCreate


COMPANY_ID = "company-matrix"
REQUESTED_BY = "user-matrix"
EMPLOYEE_ID = "emp-matrix"


def _snapshot(
    statut: str = "Non-Cadre",
    rh_access: str | None = None,
) -> dict:
    return {
        "employee": {
            "job_title": "Technicien",
            "salaire_de_base": {"valeur": 2800, "devise": "EUR"},
            "statut": statut,
            "classification_conventionnelle": None,
        },
        "previous_rh_access": rh_access,
    }


def _promotion_read(**kwargs):
    from datetime import datetime

    from app.modules.promotions.schemas import PromotionRead

    defaults = {
        "id": "promo-matrix",
        "company_id": COMPANY_ID,
        "employee_id": EMPLOYEE_ID,
        "promotion_type": "salaire",
        "status": "draft",
        "effective_date": date.today() + timedelta(days=30),
        "request_date": date.today(),
        "new_salary": {"valeur": 3500, "devise": "EUR"},
        "requested_by": REQUESTED_BY,
        "created_at": datetime(2025, 1, 1, 10, 0),
        "updated_at": datetime(2025, 1, 1, 10, 0),
    }
    defaults.update(kwargs)
    return PromotionRead(**defaults)


# --- A : création par type ---

CREATE_TYPE_CASES = [
    pytest.param(
        "poste",
        {"new_job_title": "Chef de projet"},
        "job_title",
        id="A1-poste",
    ),
    pytest.param(
        "salaire",
        {"new_salary": {"valeur": 4000, "devise": "EUR"}},
        "salaire_de_base",
        id="A2-salaire",
    ),
    pytest.param(
        "statut",
        {"new_statut": "Cadre"},
        "statut",
        id="A3-statut",
    ),
    pytest.param(
        "classification",
        {"new_classification": {"coefficient": 250, "classe_emploi": 7}},
        "classification_conventionnelle",
        id="A4-classif",
    ),
    pytest.param(
        "mixte",
        {
            "new_job_title": "Manager",
            "new_salary": {"valeur": 5000, "devise": "EUR"},
            "new_statut": "Cadre",
        },
        "mixte",
        id="A5-mixte",
    ),
]


class TestScenarioCreateByType:
    @pytest.mark.parametrize(
        "promotion_type,extra_fields,expected_field",
        CREATE_TYPE_CASES,
    )
    @patch("app.modules.promotions.application.commands.apply_promotion_changes")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch(
        "app.modules.promotions.application.commands.get_employee_snapshot_for_promotion"
    )
    def test_create_future_is_draft(
        self,
        mock_snapshot,
        mock_get_repo,
        mock_apply,
        promotion_type,
        extra_fields,
        expected_field,
    ):
        mock_snapshot.return_value = _snapshot()
        mock_repo = MagicMock()
        mock_repo.create.return_value = "promo-new"
        mock_get_repo.return_value = mock_repo
        future = date.today() + timedelta(days=14)
        body = PromotionCreate(
            employee_id=EMPLOYEE_ID,
            promotion_type=promotion_type,
            effective_date=future,
            **extra_fields,
        )
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(
                id="promo-new",
                promotion_type=promotion_type,
                status="draft",
                **{k: v for k, v in extra_fields.items()},
            ),
        ):
            result = commands.create_promotion_cmd(body, COMPANY_ID, REQUESTED_BY)
        assert result.status == "draft"
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["status"] == "draft"
        assert call_data["promotion_type"] == promotion_type
        mock_apply.assert_not_called()

    @pytest.mark.parametrize(
        "promotion_type,extra_fields,expected_field",
        CREATE_TYPE_CASES,
    )
    @patch("app.modules.promotions.application.commands.apply_promotion_changes")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch(
        "app.modules.promotions.application.commands.get_employee_snapshot_for_promotion"
    )
    def test_create_today_is_effective_and_applies(
        self,
        mock_snapshot,
        mock_get_repo,
        mock_apply,
        promotion_type,
        extra_fields,
        expected_field,
    ):
        mock_snapshot.return_value = _snapshot()
        mock_repo = MagicMock()
        mock_repo.create.return_value = "promo-eff"
        mock_get_repo.return_value = mock_repo
        body = PromotionCreate(
            employee_id=EMPLOYEE_ID,
            promotion_type=promotion_type,
            effective_date=date.today(),
            **extra_fields,
        )
        read = _promotion_read(
            id="promo-eff",
            promotion_type=promotion_type,
            status="effective",
            effective_date=date.today(),
            **{k: v for k, v in extra_fields.items()},
        )
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=read,
        ):
            result = commands.create_promotion_cmd(body, COMPANY_ID, REQUESTED_BY)
        assert result.status == "effective"
        mock_apply.assert_called_once()


class TestScenarioStatutTransitions:
    @patch("app.modules.promotions.application.commands.apply_promotion_changes")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch(
        "app.modules.promotions.application.commands.get_employee_snapshot_for_promotion"
    )
    def test_a3a_non_cadre_to_cadre_snapshot(self, mock_snapshot, mock_get_repo, mock_apply):
        mock_snapshot.return_value = _snapshot(statut="Non-Cadre")
        mock_repo = MagicMock()
        mock_repo.create.return_value = "p-a3a"
        mock_get_repo.return_value = mock_repo
        body = PromotionCreate(
            employee_id=EMPLOYEE_ID,
            promotion_type="statut",
            new_statut="Cadre",
            effective_date=date.today(),
        )
        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read(
                id="p-a3a",
                promotion_type="statut",
                status="effective",
                previous_statut="Non-Cadre",
                new_statut="Cadre",
            ),
        ):
            commands.create_promotion_cmd(body, COMPANY_ID, REQUESTED_BY)
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["previous_statut"] == "Non-Cadre"
        assert call_data["new_statut"] == "Cadre"


# --- B : validations ---

class TestScenarioValidation:
    def test_b1_no_new_field(self):
        with pytest.raises(ValidationError):
            PromotionCreate(
                employee_id=EMPLOYEE_ID,
                promotion_type="statut",
                effective_date=date.today() + timedelta(days=1),
            )

    def test_b2_past_effective_date(self):
        with pytest.raises(ValidationError):
            PromotionCreate(
                employee_id=EMPLOYEE_ID,
                promotion_type="statut",
                new_statut="Cadre",
                effective_date=date.today() - timedelta(days=1),
            )

    def test_b3_grant_rh_without_role(self):
        with pytest.raises(ValidationError):
            PromotionCreate(
                employee_id=EMPLOYEE_ID,
                promotion_type="salaire",
                new_salary={"valeur": 3000, "devise": "EUR"},
                effective_date=date.today(),
                grant_rh_access=True,
            )

    def test_b7_free_text_statut_accepted(self):
        body = PromotionCreate(
            employee_id=EMPLOYEE_ID,
            promotion_type="statut",
            new_statut="cadre",
            effective_date=date.today() + timedelta(days=1),
        )
        assert body.new_statut == "cadre"


# --- A-RH : transitions ---

RH_TRANSITION_CASES = [
    (None, "collaborateur_rh", True, "A-RH1"),
    (None, "rh", True, "A-RH2"),
    (None, "admin", False, "A-RH3"),
    ("collaborateur_rh", "rh", True, "A-RH4-rh"),
    ("rh", "admin", True, "A-RH5"),
    ("rh", "collaborateur_rh", False, "A-RH6"),
]


class TestScenarioRhTransitions:
    @pytest.mark.parametrize(
        "current,new_role,allowed,scenario_id",
        RH_TRANSITION_CASES,
    )
    def test_domain_rh_rules(self, current, new_role, allowed, scenario_id):
        assert domain_rules.validate_rh_access_transition(current, new_role) is allowed

    @pytest.mark.parametrize("new_role", ["admin"])
    def test_b4_create_invalid_rh_raises_400(self, new_role):
        with (
            patch(
                "app.modules.promotions.application.commands.get_employee_snapshot_for_promotion",
                return_value=_snapshot(),
            ),
            patch(
                "app.modules.promotions.application.commands.get_promotion_repository"
            ) as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            body = PromotionCreate(
                employee_id=EMPLOYEE_ID,
                promotion_type="salaire",
                new_salary={"valeur": 4000, "devise": "EUR"},
                effective_date=date.today(),
                grant_rh_access=True,
                new_rh_access=new_role,
            )
            with pytest.raises(HTTPException) as exc:
                commands.create_promotion_cmd(body, COMPANY_ID, REQUESTED_BY)
            assert exc.value.status_code == 400


# --- C : workflow ---

class TestScenarioWorkflow:
    @patch("app.modules.promotions.application.commands.apply_promotion_changes")
    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_c5_approved_to_effective(self, mock_get_repo, mock_get_by_id, mock_apply):
        approved = _promotion_read(status="approved", new_statut="Cadre")
        effective = _promotion_read(status="effective", new_statut="Cadre")
        mock_get_by_id.side_effect = [approved, effective]
        mock_get_repo.return_value = MagicMock()

        result = commands.mark_effective_promotion_cmd("promo-matrix", COMPANY_ID)

        assert result.status == "effective"
        mock_apply.assert_called_once_with(approved, COMPANY_ID)

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    def test_c8_rejected_to_effective_raises_400(self, mock_get_by_id):
        mock_get_by_id.return_value = _promotion_read(status="rejected")
        with pytest.raises(HTTPException) as exc:
            commands.mark_effective_promotion_cmd("promo-matrix", COMPANY_ID)
        assert exc.value.status_code == 400

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    def test_c9_cancelled_raises_400(self, mock_get_by_id):
        mock_get_by_id.return_value = _promotion_read(status="cancelled")
        with pytest.raises(HTTPException) as exc:
            commands.mark_effective_promotion_cmd("promo-matrix", COMPANY_ID)
        assert exc.value.status_code == 400

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_c11_update_pending_approval(self, mock_get_repo, mock_get_by_id):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read(status="pending_approval")
        mock_get_repo.return_value = mock_repo
        mock_get_by_id.return_value = _promotion_read(
            status="pending_approval", new_job_title="Lead"
        )
        from app.modules.promotions.schemas import PromotionUpdate

        result = commands.update_promotion_cmd(
            "promo-matrix",
            PromotionUpdate(new_job_title="Lead"),
            COMPANY_ID,
        )
        assert result.new_job_title == "Lead"
        mock_repo.update.assert_called_once()

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_c13_delete_pending_approval(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read(status="pending_approval")
        mock_get_repo.return_value = mock_repo
        commands.delete_promotion_cmd("promo-matrix", COMPANY_ID)
        mock_repo.delete.assert_called_once()

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_c15_submit_without_new_field_raises_400(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read(
            status="draft",
            new_salary=None,
            new_job_title=None,
            new_statut=None,
        )
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc:
            commands.submit_promotion_cmd("promo-matrix", COMPANY_ID)
        assert exc.value.status_code == 400


# --- G : limites ---

class TestScenarioEdgeCases:
    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_g3_classification_partial(self, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )
        promo = MagicMock()
        promo.id = "p1"
        promo.employee_id = EMPLOYEE_ID
        promo.new_job_title = None
        promo.new_salary = None
        promo.new_statut = None
        promo.new_classification = {"coefficient": 200}
        promo.grant_rh_access = False
        promo.new_rh_access = None
        EmployeeUpdater().apply_promotion_changes(promo, COMPANY_ID)
        assert mock_table.update.call_args[0][0]["classification_conventionnelle"] == {
            "coefficient": 200
        }
