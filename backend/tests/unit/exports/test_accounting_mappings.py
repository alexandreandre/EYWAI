"""Tests unitaires — mappings comptables PCG paie."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.exports.application import accounting_mappings as svc
from app.modules.exports.schemas.accounting_mappings import AccountingMappingUpsert

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _global_row():
    return {
        "id": "global-1",
        "company_id": None,
        "rubrique_code": "salaire_brut",
        "rubrique_libelle": "Salaire brut",
        "compte_comptable": "641000",
        "journal": "OD",
        "sens": "debit",
        "type_rubrique": "salaire",
        "analytique": None,
        "is_active": True,
    }


def _override_row():
    return {
        **_global_row(),
        "id": "company-1",
        "company_id": COMPANY_ID,
        "compte_comptable": "641100",
    }


def _mock_table_responses(*, globals_list=None, company_list=None, existing=None, upsert_row=None):
    globals_execute = MagicMock(data=globals_list or [])
    company_execute = MagicMock(data=company_list or [])
    existing_execute = MagicMock(data=existing)

    global_chain = MagicMock()
    global_chain.select.return_value.is_.return_value.eq.return_value.execute.return_value = (
        globals_execute
    )

    company_chain = MagicMock()
    company_chain.select.return_value.eq.return_value.execute.return_value = company_execute

    upsert_chain = MagicMock()
    upsert_chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        existing_execute
    )
    if existing:
        upsert_chain.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=upsert_row or existing
        )
    else:
        upsert_chain.insert.return_value.execute.return_value = MagicMock(
            data=upsert_row or [_override_row()]
        )

    delete_chain = MagicMock()
    delete_chain.delete.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    def table(name):
        if name == "accounting_mappings":
            chain = MagicMock()
            chain.select = global_chain.select
            chain.is_ = global_chain.is_
            chain.eq = MagicMock(side_effect=lambda *a, **k: company_chain.eq(*a, **k) if k or (a and a[0] == "company_id") else global_chain.eq(*a, **k))
            # Simpler: return different chains based on call pattern
            return _AccountingMappingsTable(
                globals_list=globals_list or [],
                company_list=company_list or [],
                existing=existing,
                upsert_row=upsert_row,
            )
        raise AssertionError(f"unexpected table {name}")

    return table


class _AccountingMappingsTable:
    """Chaîne Supabase mockée pour accounting_mappings."""

    def __init__(self, *, globals_list, company_list, existing, upsert_row):
        self._globals_list = globals_list
        self._company_list = company_list
        self._existing = existing
        self._upsert_row = upsert_row

    def select(self, *_args, **_kwargs):
        return self

    def is_(self, _col, val):
        assert val == "null"
        self._mode = "global"
        return self

    def eq(self, col, val):
        if col == "is_active":
            return self
        if col == "company_id":
            self._mode = "company"
            self._company_id = val
            return self
        if col == "rubrique_code":
            self._rubrique_code = val
            return self
        if col == "id":
            return self
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if getattr(self, "_mode", None) == "global":
            return MagicMock(data=self._globals_list)
        if getattr(self, "_mode", None) == "company" and not hasattr(self, "_rubrique_code"):
            return MagicMock(data=self._company_list)
        if hasattr(self, "_rubrique_code"):
            if self._existing and getattr(self, "_last_payload", None) is not None:
                return MagicMock(data=[self._resolve_update_row()])
            return MagicMock(data=self._existing)
        return MagicMock(data=[])

    def update(self, payload):
        self._last_payload = payload
        return self

    def insert(self, _payload):
        row = self._upsert_row
        if isinstance(row, list):
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=row)))
        return MagicMock(execute=MagicMock(return_value=MagicMock(data=[row])))

    def _resolve_update_row(self):
        if self._upsert_row:
            return self._upsert_row if isinstance(self._upsert_row, dict) else self._upsert_row[0]
        payload = getattr(self, "_last_payload", {})
        return {**_override_row(), **payload, "id": "company-1"}

    def delete(self):
        return self


pytestmark = pytest.mark.unit


class TestListAccountingMappings:
    def test_merges_global_defaults_with_company_override(self):
        table = _AccountingMappingsTable(
            globals_list=[_global_row()],
            company_list=[_override_row()],
            existing=None,
            upsert_row=None,
        )

        with patch.object(svc, "supabase") as mock_sb:
            mock_sb.table.return_value = table
            result = svc.list_accounting_mappings(COMPANY_ID)

        assert result.company_overrides_count == 1
        assert len(result.mappings) == 1
        assert result.mappings[0].compte_comptable == "641100"
        assert result.mappings[0].is_global_default is False

    def test_returns_only_globals_when_no_override(self):
        table = _AccountingMappingsTable(
            globals_list=[_global_row()],
            company_list=[],
            existing=None,
            upsert_row=None,
        )

        with patch.object(svc, "supabase") as mock_sb:
            mock_sb.table.return_value = table
            result = svc.list_accounting_mappings(COMPANY_ID)

        assert result.company_overrides_count == 0
        assert result.mappings[0].is_global_default is True


class TestUpsertCompanyMapping:
    def test_inserts_when_no_existing_override(self):
        new_row = _override_row()
        table = _AccountingMappingsTable(
            globals_list=[],
            company_list=[],
            existing=None,
            upsert_row=new_row,
        )

        with patch.object(svc, "supabase") as mock_sb:
            mock_sb.table.return_value = table
            out = svc.upsert_company_mapping(
                COMPANY_ID,
                AccountingMappingUpsert(
                    rubrique_code="salaire_brut",
                    rubrique_libelle="Salaire brut",
                    compte_comptable="641200",
                ),
            )

        assert out.compte_comptable == "641100"

    def test_updates_when_override_exists(self):
        existing = {"id": "company-1"}
        updated = _override_row()
        table = _AccountingMappingsTable(
            globals_list=[],
            company_list=[],
            existing=existing,
            upsert_row=updated,
        )

        with patch.object(svc, "supabase") as mock_sb:
            mock_sb.table.return_value = table
            out = svc.upsert_company_mapping(
                COMPANY_ID,
                AccountingMappingUpsert(
                    rubrique_code="salaire_brut",
                    rubrique_libelle="Salaire brut",
                    compte_comptable="641300",
                ),
            )

        assert out.rubrique_code == "salaire_brut"


class TestDeleteCompanyMapping:
    def test_deletes_company_override(self):
        table = _AccountingMappingsTable(
            globals_list=[],
            company_list=[],
            existing=None,
            upsert_row=None,
        )

        with patch.object(svc, "supabase") as mock_sb:
            mock_sb.table.return_value = table
            svc.delete_company_mapping(COMPANY_ID, "salaire_brut")

        # Pas d'exception = succès avec le mock actuel


class TestChampsOrganisme:
    def test_row_to_out_expose_les_deux_comptes(self):
        from app.modules.exports.application.accounting_mappings import _row_to_out

        row = {
            "id": "map-1",
            "company_id": "co-1",
            "rubrique_code": "organisme_mutuelle",
            "rubrique_libelle": "Mutuelle",
            "compte_comptable": "64524200",
            "compte_charge": "64524200",
            "compte_tiers": "43702000",
            "organisme": "MUTUELLE",
            "coti_id": None,
            "journal": "PAI",
            "sens": "debit",
            "type_rubrique": "charge_patronale",
            "analytique": None,
            "is_active": True,
        }
        out = _row_to_out(row)
        assert out.compte_charge == "64524200"
        assert out.compte_tiers == "43702000"
        assert out.organisme == "MUTUELLE"
        assert out.is_global_default is False

    def test_champs_absents_toleres(self):
        """Les lignes créées avant la migration n'ont pas les nouvelles colonnes."""
        from app.modules.exports.application.accounting_mappings import _row_to_out

        row = {
            "id": "map-2",
            "company_id": None,
            "rubrique_code": "salaire_brut",
            "rubrique_libelle": "Salaire brut",
            "compte_comptable": "641000",
            "journal": "OD",
            "sens": "debit",
            "type_rubrique": "salaire",
            "is_active": True,
        }
        out = _row_to_out(row)
        assert out.compte_charge is None
        assert out.compte_tiers is None
        assert out.organisme is None
        assert out.is_global_default is True
