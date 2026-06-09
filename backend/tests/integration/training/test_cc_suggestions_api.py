"""Wiring API propositions formation CC côté training."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.training.api.router import (
    route_cc_suggestions,
    route_create_from_recommendation,
)
from app.modules.training.schemas.responses import CcTrainingSuggestion, TrainingCatalog
from app.modules.users.schemas.responses import User


pytestmark = pytest.mark.integration


def _rh_user() -> User:
    user = MagicMock(spec=User)
    user.id = "user-1"
    user.active_company_id = "company-1"
    user.has_rh_access_in_company.return_value = True
    return user


class TestCcSuggestionsRoutes:
    @patch("app.modules.training.api.router.is_platform_admin", return_value=False)
    @patch("app.modules.training.api.router.queries.get_cc_training_suggestions")
    def test_cc_suggestions_rh(self, mock_get, _mock_admin):
        mock_get.return_value = [
            CcTrainingSuggestion(
                id="reco-1",
                idcc="1234",
                title="SST",
                obligation_level="obligatoire",
                already_in_catalog=False,
            )
        ]
        out = route_cc_suggestions(current_user=_rh_user())
        assert len(out) == 1
        mock_get.assert_called_once_with("company-1")

    @patch("app.modules.training.api.router.is_platform_admin", return_value=False)
    @patch("app.modules.training.api.router.queries.get_cc_training_suggestions")
    def test_cc_suggestions_refuse_non_rh(self, mock_get, _mock_admin):
        user = MagicMock(spec=User)
        user.active_company_id = "company-1"
        user.has_rh_access_in_company.return_value = False
        with pytest.raises(HTTPException) as exc:
            route_cc_suggestions(current_user=user)
        assert exc.value.status_code == 403
        mock_get.assert_not_called()

    @patch("app.modules.training.api.router.is_platform_admin", return_value=False)
    @patch("app.modules.training.api.router.commands.create_training_from_cc_recommendation")
    def test_create_from_recommendation(self, mock_create, _mock_admin):
        mock_create.return_value = TrainingCatalog(
            id="t1",
            company_id="company-1",
            title="SST",
            training_type="presentiel",
            status="active",
        )
        out = route_create_from_recommendation(
            "reco-1", current_user=_rh_user()
        )
        assert out.id == "t1"
        mock_create.assert_called_once_with("company-1", "reco-1")
