"""
Tests de l'adaptateur de requêtes sécurisées Copilot (infrastructure/secure_queries.py).

Garanties vérifiées :
- chaque fonction publique exige un company_id serveur non vide ;
- chaque requête directe est filtrée sur company_id (jamais de requête sans filtre) ;
- les agrégats paie / indicateurs RH délèguent aux services scopés par entreprise ;
- aucun appel réel à la base : le client Supabase et les services sont mockés.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.copilot.infrastructure import secure_queries


pytestmark = pytest.mark.unit


# --- Faux client Supabase (enregistre les filtres appliqués) ---


class FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    def __init__(self, response):
        self._response = response
        self.eq_calls = []
        self.in_calls = []
        self.gte_calls = []
        self.lte_calls = []
        self.select_args = None

    def select(self, *args, **kwargs):
        self.select_args = (args, kwargs)
        return self

    def eq(self, column, value):
        self.eq_calls.append((column, value))
        return self

    def in_(self, column, values):
        self.in_calls.append((column, list(values)))
        return self

    def gte(self, column, value):
        self.gte_calls.append((column, value))
        return self

    def lte(self, column, value):
        self.lte_calls.append((column, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        return self._response


class FakeClient:
    def __init__(self, response):
        self.query = FakeQuery(response)
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return self.query


def _patch_client(response):
    client = FakeClient(response)
    patcher = patch.object(
        secure_queries, "get_supabase_client", return_value=client
    )
    return patcher, client


ALL_DIRECT_TOOLS = [
    "count_employees",
    "search_employees",
    "absence_summary",
    "planning_summary",
]


class TestCompanyIdRequired:
    @pytest.mark.parametrize(
        "func_name",
        [
            "count_employees",
            "search_employees",
            "payroll_summary",
            "absence_summary",
            "planning_summary",
            "hr_indicators",
        ],
    )
    @pytest.mark.parametrize("bad_company", ["", "   ", None])
    def test_blank_company_id_is_rejected(self, func_name, bad_company):
        func = getattr(secure_queries, func_name)
        with pytest.raises(ValueError):
            func(bad_company, {})


class TestCountEmployees:
    def test_scopes_on_company_and_returns_count(self):
        patcher, client = _patch_client(FakeResponse(count=7))
        with patcher:
            result = secure_queries.count_employees("c1", {})
        assert result == {"count": 7}
        assert client.tables == ["employees"]
        assert ("company_id", "c1") in client.query.eq_calls

    def test_applies_employment_status_filter(self):
        patcher, client = _patch_client(FakeResponse(count=3))
        with patcher:
            secure_queries.count_employees("c1", {"employment_status": "actif"})
        assert ("company_id", "c1") in client.query.eq_calls
        assert ("employment_status", "actif") in client.query.eq_calls

    def test_null_count_becomes_zero(self):
        patcher, _ = _patch_client(FakeResponse(count=None))
        with patcher:
            assert secure_queries.count_employees("c1", {}) == {"count": 0}


class TestSearchEmployees:
    def test_scopes_on_company(self):
        rows = [
            {"id": "1", "first_name": "Jean", "last_name": "Dupont"},
            {"id": "2", "first_name": "Marie", "last_name": "Martin"},
        ]
        patcher, client = _patch_client(FakeResponse(data=rows))
        with patcher:
            result = secure_queries.search_employees("c1", {"name": "Dupont"})
        assert client.tables == ["employees"]
        assert ("company_id", "c1") in client.query.eq_calls
        assert result["count"] >= 1
        assert result["employees"][0]["last_name"] == "Dupont"

    def test_never_returns_unfiltered_ids(self):
        # La fonction ne doit jamais renvoyer un employee_id externe : les
        # arguments LLM ne peuvent pas injecter de périmètre.
        rows = [{"id": "1", "first_name": "Jean", "last_name": "Dupont"}]
        patcher, client = _patch_client(FakeResponse(data=rows))
        with patcher:
            secure_queries.search_employees("c1", {"name": "x", "limit": 3})
        assert ("company_id", "c1") in client.query.eq_calls


class TestAbsenceSummary:
    def test_scopes_on_company_and_aggregates(self):
        rows = [
            {"id": "1", "type": "conges_payes", "status": "validated", "selected_days": ["2026-01-05"]},
            {"id": "2", "type": "maladie", "status": "pending", "selected_days": ["2026-01-06", "2026-01-07"]},
            {"id": "3", "type": "conges_payes", "status": "validated", "selected_days": []},
        ]
        patcher, client = _patch_client(FakeResponse(data=rows))
        with patcher:
            result = secure_queries.absence_summary("c1", {})
        assert client.tables == ["absence_requests"]
        assert ("company_id", "c1") in client.query.eq_calls
        assert result["total_requests"] == 3
        assert result["by_status"]["validated"] == 2
        assert result["by_type"]["conges_payes"] == 2

    def test_applies_status_and_type_filters(self):
        patcher, client = _patch_client(FakeResponse(data=[]))
        with patcher:
            secure_queries.absence_summary(
                "c1", {"status": "validated", "type": "maladie"}
            )
        assert ("company_id", "c1") in client.query.eq_calls
        assert ("status", "validated") in client.query.eq_calls
        assert ("type", "maladie") in client.query.eq_calls


class TestPlanningSummary:
    def test_scopes_on_company_and_date_range(self):
        rows = [
            {"id": "s1", "employee_id": "e1", "is_locked": True},
            {"id": "s2", "employee_id": "e1", "is_locked": False},
            {"id": "s3", "employee_id": "e2", "is_locked": True},
        ]
        patcher, client = _patch_client(FakeResponse(data=rows))
        with patcher:
            result = secure_queries.planning_summary(
                "c1", {"date_start": "2026-01-05", "date_end": "2026-01-11"}
            )
        assert client.tables == ["shifts"]
        assert ("company_id", "c1") in client.query.eq_calls
        assert client.query.gte_calls == [("shift_date", "2026-01-05")]
        assert client.query.lte_calls == [("shift_date", "2026-01-11")]
        assert result["total_shifts"] == 3
        assert result["employees_scheduled"] == 2
        assert result["locked_shifts"] == 2

    def test_defaults_date_range_when_absent(self):
        patcher, client = _patch_client(FakeResponse(data=[]))
        with patcher:
            result = secure_queries.planning_summary("c1", {})
        assert ("company_id", "c1") in client.query.eq_calls
        # Une plage de dates est toujours appliquée (jamais de requête sans filtre temporel).
        assert len(client.query.gte_calls) == 1
        assert len(client.query.lte_calls) == 1
        assert result["date_start"] <= result["date_end"]


class TestPayrollSummary:
    def test_delegates_to_scoped_analytics(self):
        fake = MagicMock(return_value={"period": "2026-01", "masse_brute": 100.0})
        with patch.object(secure_queries, "get_payroll_analytics_summary", fake):
            result = secure_queries.payroll_summary("c1", {"period": "2026-01"})
        assert result["period"] == "2026-01"
        fake.assert_called_once_with(
            company_id="c1", period="2026-01", team_ids=None
        )

    def test_defaults_period_to_current_month(self):
        fake = MagicMock(return_value={})
        with patch.object(secure_queries, "get_payroll_analytics_summary", fake):
            secure_queries.payroll_summary("c1", {})
        kwargs = fake.call_args.kwargs
        assert kwargs["company_id"] == "c1"
        assert kwargs["team_ids"] is None
        # Période YYYY-MM valide générée côté serveur.
        assert len(kwargs["period"]) == 7 and kwargs["period"][4] == "-"

    def test_invalid_period_is_replaced_by_server_default(self):
        fake = MagicMock(return_value={})
        with patch.object(secure_queries, "get_payroll_analytics_summary", fake):
            secure_queries.payroll_summary("c1", {"period": "DROP TABLE"})
        period = fake.call_args.kwargs["period"]
        assert len(period) == 7 and period[4] == "-"


class TestHrIndicators:
    def test_delegates_and_serializes_subset(self):
        analytics = SimpleNamespace(
            effectif_actif=12,
            age_moyen=41.2,
            anciennete_moyenne_annees=5.4,
            masse_salariale_brute_totale=250000.0,
            turnover=SimpleNamespace(
                taux_turnover_annuel=8.3,
                nb_departs_12_mois=2,
                nb_embauches_12_mois=3,
            ),
            absenteisme=SimpleNamespace(
                taux_global=4.1,
                taux_maladie=3.0,
                taux_at=0.5,
            ),
        )
        fake = MagicMock(return_value=analytics)
        with patch.object(secure_queries, "build_analytics_avances", fake):
            result = secure_queries.hr_indicators("c1", {})
        fake.assert_called_once_with("c1")
        assert result["effectif_actif"] == 12
        assert result["turnover"]["nb_departs_12_mois"] == 2
        assert result["absenteisme"]["taux_global"] == 4.1
        # Aucune fuite de champs bruts non prévus (ex. pyramide complète).
        assert "pyramide_ages" not in result
