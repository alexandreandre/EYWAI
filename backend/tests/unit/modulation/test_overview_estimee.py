"""Le tableau « Effectif » dit quand ses chiffres sont des valeurs de repli."""

from types import SimpleNamespace

from app.modules.modulation.application import queries


class _Requete:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def in_(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _Supabase:
    def __init__(self, data):
        self._data = data

    def table(self, _nom):
        return _Requete(self._data)


def test_sans_compteur_les_lignes_sont_marquees_estimees(monkeypatch):
    monkeypatch.setattr(queries.repo, "list_employee_counters", lambda *_a: [])
    monkeypatch.setattr(
        queries.repo,
        "get_modulation_settings",
        lambda *_a: SimpleNamespace(average_weekly_hours=35.0),
    )
    monkeypatch.setattr(
        queries,
        "supabase",
        _Supabase(
            [{"id": "e1", "first_name": "A", "last_name": "B", "duree_hebdomadaire": 35}]
        ),
    )
    rows = queries.get_modulation_overview("c1", 2026)
    assert rows[0].estimated is True


def test_avec_compteur_les_lignes_ne_sont_pas_estimees(monkeypatch):
    monkeypatch.setattr(
        queries.repo,
        "list_employee_counters",
        lambda *_a: [
            {
                "employee_id": "e1",
                "employees": {"first_name": "A", "last_name": "B"},
                "theoretical_hours": 1820,
                "actual_hours": 1800,
                "balance_hours": -20,
            }
        ],
    )
    rows = queries.get_modulation_overview("c1", 2026)
    assert rows[0].estimated is False
