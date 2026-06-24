"""
Tests unitaires du moteur d'obligations médicales (dédoublonnage).
"""

from datetime import date
from typing import Any, Dict, List, Optional
from unittest.mock import patch
import uuid

from app.modules.medical_follow_up.infrastructure.obligation_engine import (
    _cancel_duplicate_obligations,
    _dedupe_key,
    _has_active_obligation,
    _obligation_dedupe_key_from_row,
    compute_obligations_for_employee,
)


class TestObligationDedupeKey:
    def test_vip_embauche_key_matches_insert_trigger(self):
        due = date(2031, 6, 4)
        assert _dedupe_key("vip", "embauche", due) == ("vip", "embauche", "2031-06-04")

    def test_row_key_uses_stored_trigger_type(self):
        row = {
            "visit_type": "vip",
            "trigger_type": "embauche",
            "due_date": "2031-06-04",
        }
        assert _obligation_dedupe_key_from_row(row) == ("vip", "embauche", "2031-06-04")


class TestHasActiveObligation:
    def test_detects_active_vip(self):
        existing = [
            {
                "visit_type": "vip",
                "trigger_type": "embauche",
                "status": "a_faire",
                "due_date": "2031-06-04",
            }
        ]
        assert _has_active_obligation(existing, "vip") is True
        assert _has_active_obligation(existing, "vip", "embauche") is True
        assert _has_active_obligation(existing, "sir") is False

    def test_ignores_completed(self):
        existing = [
            {
                "visit_type": "vip",
                "trigger_type": "embauche",
                "status": "realisee",
                "due_date": "2031-06-04",
            }
        ]
        assert _has_active_obligation(existing, "vip") is False


class TestCancelDuplicateObligations:
    def test_cancels_duplicate_active_rows(self):
        cancelled: list[str] = []

        class UpdateChain:
            def __init__(self, ob_id: str):
                self._ob_id = ob_id

            def eq(self, _field, value):
                cancelled.append(value)
                return self

            def execute(self):
                return None

        class Table:
            def update(self, payload):
                assert payload["status"] == "annulee"
                return UpdateChain("")

        class Supabase:
            def table(self, _name):
                return Table()

        existing = [
            {
                "id": "obl-1",
                "visit_type": "vip",
                "trigger_type": "embauche",
                "due_date": "2031-06-04",
                "status": "a_faire",
                "created_at": "2026-06-01T10:00:00",
            },
            {
                "id": "obl-2",
                "visit_type": "vip",
                "trigger_type": "embauche",
                "due_date": "2031-06-04",
                "status": "a_faire",
                "created_at": "2026-06-01T11:00:00",
            },
        ]

        result = _cancel_duplicate_obligations(Supabase(), existing)
        assert cancelled == ["obl-2"]
        assert len(result) == 1
        assert result[0]["id"] == "obl-1"


class _FakeResponse:
    def __init__(self, data: Any):
        self.data = data


class _FakeQuery:
    def __init__(self, store: "_FakeSupabase", table: str):
        self._store = store
        self._table = table
        self._filters: List[tuple] = []
        self._order_cols: List[tuple] = []
        self._limit_n: Optional[int] = None
        self._payload: Optional[Dict[str, Any]] = None
        self._update_id: Optional[str] = None
        self._maybe_single = False
        self._mode: Optional[str] = None

    def select(self, cols: str):
        return self

    def eq(self, field: str, value: Any):
        if self._mode == "update" and field == "id":
            self._update_id = value
            return self
        self._filters.append(("eq", field, value))
        return self

    def neq(self, field: str, value: Any):
        self._filters.append(("neq", field, value))
        return self

    def in_(self, field: str, values: List[Any]):
        self._filters.append(("in", field, values))
        return self

    def order(self, field: str, desc: bool = False):
        self._order_cols.append((field, desc))
        return self

    def limit(self, n: int):
        self._limit_n = n
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def single(self):
        self._maybe_single = True
        return self

    def insert(self, payload: Dict[str, Any]):
        self._mode = "insert"
        self._payload = payload
        return self

    def update(self, payload: Dict[str, Any]):
        self._mode = "update"
        self._payload = payload
        return self

    def _match(self, row: Dict[str, Any]) -> bool:
        for op, field, value in self._filters:
            cell = row.get(field)
            if op == "eq" and cell != value:
                return False
            if op == "neq" and cell == value:
                return False
            if op == "in" and cell not in value:
                return False
        return True

    def _rows(self) -> List[Dict[str, Any]]:
        if self._table == "employees":
            rows = list(self._store.employees.values())
        elif self._table == "medical_follow_up_obligations":
            rows = list(self._store.obligations)
        elif self._table == "absence_requests":
            rows = list(self._store.absence_requests)
        else:
            rows = []
        return [r for r in rows if self._match(r)]

    def execute(self):
        if self._mode == "insert" and self._payload is not None:
            if self._table == "medical_follow_up_obligations":
                row = {
                    **self._payload,
                    "id": f"obl-{uuid.uuid4().hex[:8]}",
                    "created_at": "2026-06-01T10:00:00",
                }
                self._store.obligations.append(row)
                return _FakeResponse([row])
            return _FakeResponse([])

        if self._mode == "update" and self._payload is not None:
            for row in self._store.obligations:
                if row.get("id") == self._update_id:
                    row.update(self._payload)
            return _FakeResponse([])

        rows = self._rows()
        for field, desc in self._order_cols:
            rows.sort(key=lambda r: str(r.get(field) or ""), reverse=desc)
        if self._limit_n is not None:
            rows = rows[: self._limit_n]
        if self._maybe_single:
            return _FakeResponse(rows[0] if rows else None)
        return _FakeResponse(rows)


class _FakeSupabase:
    def __init__(
        self,
        employee: Dict[str, Any],
        obligations: Optional[List[Dict[str, Any]]] = None,
    ):
        self.employees = {employee["id"]: employee}
        self.obligations: List[Dict[str, Any]] = list(obligations or [])
        self.absence_requests: List[Dict[str, Any]] = []

    def table(self, name: str):
        return _FakeQuery(self, name)


def _active_obligations(result: List[Dict[str, Any]], visit_type: str) -> List[Dict]:
    return [
        o
        for o in result
        if o.get("visit_type") == visit_type
        and o.get("status") in ("a_faire", "planifiee")
    ]


class TestComputeObligationsHistoricalRegistry:
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine._get_employee_collective_agreement_idcc",
        return_value=None,
    )
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine.get_supabase"
    )
    def test_sir_veteran_no_aptitude_sir(self, mock_get_supabase, _mock_idcc):
        company_id = "co-test"
        employee_id = "emp-bouveyron"
        employee = {
            "id": employee_id,
            "company_id": company_id,
            "hire_date": "1996-10-01",
            "date_naissance": "1973-04-20",
            "employment_status": "actif",
            "is_poste_sir": True,
            "is_travail_nuit": False,
            "collective_agreement_id": None,
        }
        fake = _FakeSupabase(
            employee,
            obligations=[
                {
                    "id": "obl-sir-done",
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "sir",
                    "trigger_type": "periodicite_sir",
                    "due_date": "2025-06-10",
                    "status": "realisee",
                    "completed_date": "2025-06-10",
                }
            ],
        )
        mock_get_supabase.return_value = fake

        result = compute_obligations_for_employee(company_id, employee_id)
        assert _active_obligations(result, "aptitude_sir_avant_affectation") == []
        assert _active_obligations(result, "mi_carriere_45") == []
        assert _active_obligations(result, "vip") == []

    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine._get_employee_collective_agreement_idcc",
        return_value=None,
    )
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine.get_supabase"
    )
    def test_reconcile_cancels_existing_phantom(self, mock_get_supabase, _mock_idcc):
        company_id = "co-test"
        employee_id = "emp-jean"
        employee = {
            "id": employee_id,
            "company_id": company_id,
            "hire_date": "2025-05-28",
            "date_naissance": None,
            "employment_status": "actif",
            "is_poste_sir": True,
            "is_travail_nuit": False,
            "collective_agreement_id": None,
        }
        fake = _FakeSupabase(
            employee,
            obligations=[
                {
                    "id": "obl-aptitude",
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "aptitude_sir_avant_affectation",
                    "trigger_type": "poste_sir",
                    "due_date": "2025-05-28",
                    "status": "a_faire",
                },
                {
                    "id": "obl-sir-done",
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "sir",
                    "trigger_type": "periodicite_sir",
                    "due_date": "2025-09-25",
                    "status": "realisee",
                    "completed_date": "2025-09-25",
                },
            ],
        )
        mock_get_supabase.return_value = fake

        result = compute_obligations_for_employee(company_id, employee_id)
        assert _active_obligations(result, "aptitude_sir_avant_affectation") == []
        aptitude_row = next(
            o for o in fake.obligations if o.get("id") == "obl-aptitude"
        )
        assert aptitude_row["status"] == "annulee"

    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine._get_employee_collective_agreement_idcc",
        return_value=None,
    )
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine.get_supabase"
    )
    def test_new_hire_still_gets_vip(self, mock_get_supabase, _mock_idcc):
        company_id = "co-test"
        employee_id = "emp-new"
        hire = date.today().isoformat()
        employee = {
            "id": employee_id,
            "company_id": company_id,
            "hire_date": hire,
            "date_naissance": None,
            "employment_status": "actif",
            "is_poste_sir": False,
            "is_travail_nuit": False,
            "collective_agreement_id": None,
        }
        fake = _FakeSupabase(employee)
        mock_get_supabase.return_value = fake

        result = compute_obligations_for_employee(company_id, employee_id)
        vip_active = _active_obligations(result, "vip")
        assert len(vip_active) == 1
        assert vip_active[0]["trigger_type"] == "embauche"

    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine._get_employee_collective_agreement_idcc",
        return_value=None,
    )
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine.get_supabase"
    )
    def test_vallat_overdue_sir_preserved(self, mock_get_supabase, _mock_idcc):
        company_id = "co-test"
        employee_id = "emp-vallat"
        employee = {
            "id": employee_id,
            "company_id": company_id,
            "hire_date": "2022-11-21",
            "date_naissance": None,
            "employment_status": "actif",
            "is_poste_sir": True,
            "is_travail_nuit": False,
            "collective_agreement_id": None,
        }
        fake = _FakeSupabase(
            employee,
            obligations=[
                {
                    "id": "obl-sir-done",
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "sir",
                    "trigger_type": "periodicite_sir",
                    "due_date": "2023-01-09",
                    "status": "realisee",
                    "completed_date": "2023-01-09",
                },
                {
                    "id": "obl-sir-due",
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "visit_type": "sir",
                    "trigger_type": "periodicite_sir",
                    "due_date": "2025-01-09",
                    "status": "a_faire",
                },
            ],
        )
        mock_get_supabase.return_value = fake

        result = compute_obligations_for_employee(company_id, employee_id)
        sir_active = _active_obligations(result, "sir")
        assert len(sir_active) == 1
        assert sir_active[0]["due_date"] == "2025-01-09"
        assert _active_obligations(result, "vip") == []


class TestComputeObligationsIdempotence:
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine._get_employee_collective_agreement_idcc",
        return_value=None,
    )
    @patch(
        "app.modules.medical_follow_up.infrastructure.obligation_engine.get_supabase"
    )
    def test_three_compute_calls_keep_single_vip_embauche(
        self, mock_get_supabase, _mock_idcc
    ):
        company_id = "co-test"
        employee_id = "emp-camille"
        hire_date = date.today().isoformat()
        employee = {
            "id": employee_id,
            "company_id": company_id,
            "hire_date": hire_date,
            "date_naissance": None,
            "job_title": "Opérateur",
            "employment_status": "actif",
            "is_poste_sir": False,
            "is_travail_nuit": False,
            "collective_agreement_id": None,
        }
        fake = _FakeSupabase(employee)
        mock_get_supabase.return_value = fake

        for _ in range(3):
            result = compute_obligations_for_employee(company_id, employee_id)
            active_vip = [
                o
                for o in result
                if o.get("visit_type") == "vip"
                and o.get("trigger_type") == "embauche"
                and o.get("status") != "annulee"
            ]
            assert len(active_vip) == 1

        assert len(fake.obligations) == 1
        assert fake.obligations[0]["trigger_type"] == "embauche"
