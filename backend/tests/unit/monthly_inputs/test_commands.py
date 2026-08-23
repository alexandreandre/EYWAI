"""
Tests unitaires des commandes du module monthly_inputs (application/commands.py).

Repository mocké. Pas de DB ni HTTP.
"""

from unittest.mock import patch


from app.modules.monthly_inputs.application import commands
from app.modules.monthly_inputs.schemas.requests import MonthlyInput, MonthlyInputCreate


class TestCreateMonthlyInputsBatch:
    """Commande create_monthly_inputs_batch."""

    def test_creates_batch_and_returns_inserted_count(self):
        """Payload valide → insert_batch appelé, retourne CreateBatchResultDto avec inserted_count."""
        payload = [
            MonthlyInput(
                employee_id="550e8400-e29b-41d4-a716-446655440000",
                year=2025,
                month=3,
                name="Prime",
                amount=100.0,
            ),
            MonthlyInput(
                employee_id="550e8400-e29b-41d4-a716-446655440000",
                year=2025,
                month=3,
                name="Acompte",
                amount=50.0,
            ),
        ]
        inserted_rows = [
            {
                "id": "id-1",
                "employee_id": "550e8400-e29b-41d4-a716-446655440000",
                "year": 2025,
                "month": 3,
                "name": "Prime",
                "amount": 100.0,
            },
            {
                "id": "id-2",
                "employee_id": "550e8400-e29b-41d4-a716-446655440000",
                "year": 2025,
                "month": 3,
                "name": "Acompte",
                "amount": 50.0,
            },
        ]

        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_batch.return_value = inserted_rows
            result = commands.create_monthly_inputs_batch(payload, "11111111-1111-1111-1111-111111111111")

        assert result.inserted_count == 2
        repo.insert_batch.assert_called_once()
        call_arg = repo.insert_batch.call_args[0][0]
        assert len(call_arg) == 2
        assert call_arg[0]["name"] == "Prime"
        assert call_arg[0]["amount"] == 100.0
        assert call_arg[1]["name"] == "Acompte"

    def test_empty_payload_returns_zero_inserted(self):
        """Liste vide → insert_batch avec [], retourne inserted_count=0."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_batch.return_value = []
            result = commands.create_monthly_inputs_batch([], "11111111-1111-1111-1111-111111111111")

        assert result.inserted_count == 0
        repo.insert_batch.assert_called_once_with([])

    def test_single_item_batch(self):
        """Une seule saisie en batch."""
        payload = [
            MonthlyInput(
                employee_id="660e8400-e29b-41d4-a716-446655440001",
                year=2025,
                month=6,
                name="Prime unique",
                amount=200.0,
                description="Description",
            ),
        ]
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_batch.return_value = [{"id": "new-1", "name": "Prime unique"}]
            result = commands.create_monthly_inputs_batch(payload, "11111111-1111-1111-1111-111111111111")

        assert result.inserted_count == 1
        call_arg = repo.insert_batch.call_args[0][0]
        assert call_arg[0]["employee_id"] == "660e8400-e29b-41d4-a716-446655440001"
        assert call_arg[0]["year"] == 2025
        assert call_arg[0]["month"] == 6
        assert call_arg[0]["description"] == "Description"


class TestCreateEmployeeMonthlyInput:
    """Commande create_employee_monthly_input."""

    def test_creates_single_input_and_returns_result(self):
        """Données valides → insert_one avec employee_id injecté, retourne CreateSingleResultDto."""
        employee_id = "770e8400-e29b-41d4-a716-446655440002"
        prime_data = MonthlyInputCreate(
            year=2025,
            month=4,
            name="Prime employé",
            amount=150.0,
            is_socially_taxed=True,
            is_taxable=True,
        )
        inserted = {
            "id": "input-new",
            "employee_id": employee_id,
            "year": 2025,
            "month": 4,
            "name": "Prime employé",
            "amount": 150.0,
        }

        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_one.return_value = inserted
            result = commands.create_employee_monthly_input(employee_id, prime_data, "11111111-1111-1111-1111-111111111111")

        assert result.inserted_data == inserted
        repo.insert_one.assert_called_once()
        call_row = repo.insert_one.call_args[0][0]
        assert call_row["employee_id"] == employee_id
        assert call_row["year"] == 2025
        assert call_row["month"] == 4
        assert call_row["name"] == "Prime employé"
        assert call_row["amount"] == 150.0

    def test_create_with_optional_description(self):
        """MonthlyInputCreate avec description optionnelle."""
        prime_data = MonthlyInputCreate(
            year=2025,
            month=5,
            name="Acompte",
            amount=300.0,
            description="Acompte mai",
        )
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            repo.insert_one.return_value = {}
            commands.create_employee_monthly_input("emp-1", prime_data, "11111111-1111-1111-1111-111111111111")

        call_row = repo.insert_one.call_args[0][0]
        assert call_row["description"] == "Acompte mai"


class TestDeleteMonthlyInput:
    """Commande delete_monthly_input."""

    def test_calls_delete_by_id(self):
        """delete_monthly_input délègue au repository delete_by_id."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            commands.delete_monthly_input("input-id-123", "11111111-1111-1111-1111-111111111111")

        repo.delete_by_id.assert_called_once_with("input-id-123", "11111111-1111-1111-1111-111111111111")


class TestDeleteEmployeeMonthlyInput:
    """Commande delete_employee_monthly_input."""

    def test_calls_delete_by_id_and_employee(self):
        """delete_employee_monthly_input délègue au repository delete_by_id_and_employee."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            commands.delete_employee_monthly_input("emp-456", "input-id-789", "11111111-1111-1111-1111-111111111111")

        repo.delete_by_id_and_employee.assert_called_once_with("input-id-789", "emp-456", "11111111-1111-1111-1111-111111111111")


class TestUpdateMonthlyInput:
    """Commande update_monthly_input (correction manuelle d'une saisie)."""

    def test_marks_the_row_as_manually_overridden(self):
        """La correction doit poser manual_override, sinon la génération
        mensuelle suivante écraserait le choix de la RH."""
        from app.modules.monthly_inputs.schemas.requests import MonthlyInputUpdate

        with patch.object(commands, "monthly_inputs_repository") as repo:
            repo.update_by_id.return_value = {"id": "abc", "amount": 200.0}
            result = commands.update_monthly_input("abc", MonthlyInputUpdate(amount=200.0), "11111111-1111-1111-1111-111111111111")

        repo.update_by_id.assert_called_once()
        input_id, changes, company_id = repo.update_by_id.call_args[0]
        assert input_id == "abc"
        assert changes["amount"] == 200.0
        assert changes["manual_override"] is True
        assert result == {"id": "abc", "amount": 200.0}

    def test_omitted_fields_are_not_sent(self):
        """Champs omis = inchangés : ils ne doivent pas partir en base à None."""
        from app.modules.monthly_inputs.schemas.requests import MonthlyInputUpdate

        with patch.object(commands, "monthly_inputs_repository") as repo:
            repo.update_by_id.return_value = {"id": "abc"}
            commands.update_monthly_input("abc", MonthlyInputUpdate(amount=50.0), "11111111-1111-1111-1111-111111111111")

        _, changes, _company = repo.update_by_id.call_args[0]
        assert set(changes) == {"amount", "manual_override"}

    def test_empty_payload_is_rejected(self):
        from app.modules.monthly_inputs.schemas.requests import MonthlyInputUpdate

        with patch.object(commands, "monthly_inputs_repository"):
            try:
                commands.update_monthly_input("abc", MonthlyInputUpdate(), "11111111-1111-1111-1111-111111111111")
            except ValueError as e:
                assert "Aucun champ" in str(e)
            else:
                raise AssertionError("un payload vide doit lever ValueError")

    def test_missing_row_raises(self):
        from app.modules.monthly_inputs.schemas.requests import MonthlyInputUpdate

        with patch.object(commands, "monthly_inputs_repository") as repo:
            repo.update_by_id.return_value = None
            try:
                commands.update_monthly_input("zzz", MonthlyInputUpdate(amount=1.0), "11111111-1111-1111-1111-111111111111")
            except ValueError as e:
                assert "introuvable" in str(e)
            else:
                raise AssertionError("une saisie absente doit lever ValueError")
