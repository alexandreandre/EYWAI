"""
Tests de validation des schémas promotions (création par type).
"""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.modules.promotions.schemas import PromotionCreate


def _future_date() -> date:
    return date.today() + timedelta(days=30)


class TestPromotionCreateSchemas:
    """PromotionCreate : chaque type doit accepter son champ 'nouveau' requis."""

    def test_statut_non_cadre_to_cadre(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="statut",
            new_statut="Cadre",
            effective_date=_future_date(),
        )
        assert body.promotion_type == "statut"
        assert body.new_statut == "Cadre"

    def test_statut_cadre_to_non_cadre(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="statut",
            new_statut="Non-Cadre",
            effective_date=_future_date(),
        )
        assert body.new_statut == "Non-Cadre"

    def test_poste_requires_new_job_title(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="poste",
            new_job_title="Chef de projet",
            effective_date=_future_date(),
        )
        assert body.new_job_title == "Chef de projet"

    def test_salaire_requires_new_salary(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="salaire",
            new_salary={"valeur": 4000, "devise": "EUR"},
            effective_date=_future_date(),
        )
        assert body.new_salary["valeur"] == 4000

    def test_classification_requires_new_classification(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="classification",
            new_classification={"coefficient": 250, "classe_emploi": 7},
            effective_date=_future_date(),
        )
        assert body.new_classification["coefficient"] == 250

    def test_mixte_accepts_multiple_new_fields(self):
        body = PromotionCreate(
            employee_id="emp-1",
            promotion_type="mixte",
            new_job_title="Manager",
            new_salary={"valeur": 5000, "devise": "EUR"},
            new_statut="Cadre",
            new_classification={"coefficient": 280},
            effective_date=_future_date(),
        )
        assert body.new_job_title == "Manager"
        assert body.new_statut == "Cadre"

    def test_rejects_when_no_new_field(self):
        with pytest.raises(ValidationError) as exc_info:
            PromotionCreate(
                employee_id="emp-1",
                promotion_type="statut",
                effective_date=_future_date(),
            )
        assert "Au moins un champ" in str(exc_info.value)

    def test_rejects_past_effective_date(self):
        with pytest.raises(ValidationError):
            PromotionCreate(
                employee_id="emp-1",
                promotion_type="statut",
                new_statut="Cadre",
                effective_date=date.today() - timedelta(days=1),
            )

    def test_grant_rh_access_requires_new_rh_access(self):
        with pytest.raises(ValidationError) as exc_info:
            PromotionCreate(
                employee_id="emp-1",
                promotion_type="salaire",
                new_salary={"valeur": 4000, "devise": "EUR"},
                effective_date=_future_date(),
                grant_rh_access=True,
            )
        assert "new_rh_access" in str(exc_info.value)
