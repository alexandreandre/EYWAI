"""Suppression définitive des objectifs."""

from app.modules.objectives.infrastructure import repository as repo_module
from app.modules.objectives.infrastructure.repository import SupabaseObjectivesRepository


class _TableStub:
    def __init__(self, table_name: str, calls: list[tuple[str, tuple]]):
        self.table_name = table_name
        self.calls = calls
        self.mode = "select"
        self.data = [{"id": "obj-1"}]

    def select(self, *args):
        self.mode = "select"
        self.calls.append((f"{self.table_name}.select", args))
        return self

    def delete(self):
        self.mode = "delete"
        self.calls.append((f"{self.table_name}.delete", ()))
        return self

    def eq(self, *args):
        self.calls.append((f"{self.table_name}.eq", args))
        return self

    def maybe_single(self):
        self.calls.append((f"{self.table_name}.maybe_single", ()))
        return self

    def execute(self):
        self.calls.append((f"{self.table_name}.execute", (self.mode,)))
        return self


class _SupabaseStub:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def table(self, name: str):
        self.calls.append(("table", (name,)))
        return _TableStub(name, self.calls)


def test_delete_objective_deletes_company_scoped_row(monkeypatch):
    stub = _SupabaseStub()
    monkeypatch.setattr(repo_module, "supabase", stub)

    SupabaseObjectivesRepository().delete("obj-1", "co-1")

    assert ("employee_objectives.delete", ()) in stub.calls
    assert ("employee_objectives.eq", ("id", "obj-1")) in stub.calls
    assert ("employee_objectives.eq", ("company_id", "co-1")) in stub.calls
