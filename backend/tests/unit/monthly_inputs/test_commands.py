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
            result = commands.create_monthly_inputs_batch(payload)

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
            result = commands.create_monthly_inputs_batch([])

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
            result = commands.create_monthly_inputs_batch(payload)

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
            result = commands.create_employee_monthly_input(employee_id, prime_data)

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
            commands.create_employee_monthly_input("emp-1", prime_data)

        call_row = repo.insert_one.call_args[0][0]
        assert call_row["description"] == "Acompte mai"


class TestDeleteMonthlyInput:
    """Commande delete_monthly_input."""

    def test_calls_delete_by_id(self):
        """delete_monthly_input délègue au repository delete_by_id."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            commands.delete_monthly_input("input-id-123")

        repo.delete_by_id.assert_called_once_with("input-id-123")


class TestDeleteEmployeeMonthlyInput:
    """Commande delete_employee_monthly_input."""

    def test_calls_delete_by_id_and_employee(self):
        """delete_employee_monthly_input délègue au repository delete_by_id_and_employee."""
        with patch(
            "app.modules.monthly_inputs.application.commands.monthly_inputs_repository"
        ) as repo:
            commands.delete_employee_monthly_input("emp-456", "input-id-789")

        repo.delete_by_id_and_employee.assert_called_once_with(
            "input-id-789", "emp-456"
        )
