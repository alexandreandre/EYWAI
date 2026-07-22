"""Tests : résolution salarié par NIR tolérante à la clé (base 15 ↔ DSN 13).

Empêche, à un ré-import mensuel, la création de doublons et l'échec de rattachement
des arrêts/sorties quand la DSN émet le NIR à 13 chiffres.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.dsn_import.infrastructure import repository as repo

pytestmark = pytest.mark.unit

# Salarié stocké en base avec un NIR à 15 chiffres (13 + clé).
DB_EMPLOYEE = {"id": "emp-osmani2", "company_id": "mbc", "nir": "187059935222362"}
NIR_13 = "1870599352223"   # forme DSN (sans clé)
NIR_15 = "187059935222362"  # forme base


class _FakeTable:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self._limit = None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self.filters.append(("neq", col, val))
        return self

    @property
    def not_(self):
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def ilike(self, col, val):
        self.filters.append(("ilike", col, val))
        return self

    def like(self, col, val):
        self.filters.append(("like", col, val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        out = []
        for row in self.rows:
            keep = True
            for op, col, val in self.filters:
                cv = row.get(col)
                if op == "eq" and cv != val:
                    keep = False
                elif op == "neq" and cv == val:
                    keep = False
                elif op in ("ilike", "like"):
                    prefix = val[:-1] if str(val).endswith("%") else val
                    hay = str(cv or "")
                    needle = str(prefix)
                    if op == "ilike":
                        hay, needle = hay.upper(), needle.upper()
                    if not hay.startswith(needle):
                        keep = False
            if keep:
                out.append(row)
        if self._limit is not None:
            out = out[: self._limit]
        return SimpleNamespace(data=out)


class _FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return _FakeTable(list(self.rows))


def _patch_client(rows):
    return patch.object(repo, "get_supabase_admin_client", return_value=_FakeClient(rows))


def test_find_by_nir_matches_dsn_13_to_db_15():
    with _patch_client([DB_EMPLOYEE]):
        found = repo.find_employee_by_nir("mbc", NIR_13)
    assert found is not None
    assert found["id"] == "emp-osmani2"


def test_find_by_nir_exact_15_still_works():
    with _patch_client([DB_EMPLOYEE]):
        found = repo.find_employee_by_nir("mbc", NIR_15)
    assert found is not None and found["id"] == "emp-osmani2"


def test_find_by_nir_global_matches_dsn_13_to_db_15():
    with _patch_client([DB_EMPLOYEE]):
        found = repo.find_employee_by_nir_global(NIR_13)
    assert found is not None and found["id"] == "emp-osmani2"


def test_find_by_nir_respects_company_scope():
    with _patch_client([DB_EMPLOYEE]):
        found = repo.find_employee_by_nir("other-co", NIR_13)
    assert found is None


def test_find_by_nir_no_false_match_on_different_person():
    with _patch_client([DB_EMPLOYEE]):
        found = repo.find_employee_by_nir("mbc", "2990599352223")
    assert found is None


def test_find_by_nir_db_stores_13_dsn_15():
    # Cas inverse : base à 13, DSN à 15.
    with _patch_client([{"id": "e13", "company_id": "mbc", "nir": NIR_13}]):
        found = repo.find_employee_by_nir("mbc", NIR_15)
    assert found is not None and found["id"] == "e13"


def test_dsn_absence_item_resolves_to_15_digit_employee():
    """B : un arrêt DSN (NIR 13) se rattache bien au salarié en base (NIR 15).

    Sans le fix, `_resolve_employee_for_dsn_item` lève « Salarié NIR introuvable »
    et l'arrêt ne serait jamais appliqué à la fiche (bulletin resté faux).
    """
    from app.modules.dsn_import.application.commit import _resolve_employee_for_dsn_item

    payload = {
        "siret": "75116833700028",
        "nir": NIR_13,
        "absence_type": "arret_maladie",
        "selected_days": ["2026-03-02", "2026-03-03"],
    }
    with _patch_client([DB_EMPLOYEE]):
        employee_id, company_id = _resolve_employee_for_dsn_item(
            payload,
            company_by_siret={"75116833700028": "mbc"},
            employee_by_ref={},
        )
    assert employee_id == "emp-osmani2"
    assert company_id == "mbc"
