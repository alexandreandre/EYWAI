"""
Tests de l'adaptateur de requêtes sécurisées Copilot (infrastructure/secure_queries.py).

Garanties vérifiées :
- chaque fonction publique exige un company_id serveur non vide ;
- chaque requête directe est filtrée sur company_id (jamais de requête sans filtre) ;
- les agrégats paie / indicateurs RH délèguent aux services scopés par entreprise ;
- aucun appel réel à la base : le client Supabase et les services sont mockés.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.copilot.domain.filter_values import ValeurDeFiltreInconnue
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

    def test_applies_contract_type_filter(self):
        patcher, client = _patch_client(FakeResponse(count=2))
        with patcher:
            secure_queries.count_employees("c1", {"contract_type": "CDI"})
        assert ("company_id", "c1") in client.query.eq_calls
        assert ("contract_type", "CDI") in client.query.eq_calls

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
        assert result["total_demandes"] == 3
        assert result["by_status"]["validated"] == 2
        assert result["by_type"]["conges_payes"] == 2

    def test_applies_status_and_type_filters(self):
        """« maladie » est rapproché de la valeur d'énumération réelle.

        Sans ce rapprochement, Postgres rejette la valeur et l'outil entier
        échoue (``invalid input value for enum absence_type``).
        """
        patcher, client = _patch_client(FakeResponse(data=[]))
        with patcher:
            secure_queries.absence_summary(
                "c1", {"status": "validated", "type": "maladie"}
            )
        assert ("company_id", "c1") in client.query.eq_calls
        assert ("status", "validated") in client.query.eq_calls
        assert ("type", "arret_maladie") in client.query.eq_calls

    def test_type_inconnu_echoue_explicitement(self):
        patcher, _ = _patch_client(FakeResponse(data=[]))
        with patcher, pytest.raises(ValeurDeFiltreInconnue):
            secure_queries.absence_summary("c1", {"type": "vacances d'été"})

    def test_filters_by_selected_days_date_range(self):
        rows = [
            {
                "id": "1",
                "type": "conges_payes",
                "status": "validated",
                "selected_days": ["2026-06-30", "2026-07-01"],
            },
            {
                "id": "2",
                "type": "maladie",
                "status": "validated",
                "selected_days": ["2026-08-01"],
            },
        ]
        patcher, _ = _patch_client(FakeResponse(data=rows))
        with patcher:
            result = secure_queries.absence_summary(
                "c1",
                {"date_start": "2026-07-01", "date_end": "2026-07-31"},
            )
        assert result["total_demandes"] == 1
        assert result["total_selected_days"] == 1
        assert result["date_start"] == "2026-07-01"
        assert result["date_end"] == "2026-07-31"


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


class TestPerimetreOutilsNominatifs:
    """Le périmètre scopé borne les outils qui désignent des personnes.

    Ces tests portent sur la garantie la plus sensible du module : un RH
    restreint à une équipe ne doit voir que la sienne, et l'absence de droit
    doit produire « aucune donnée », jamais « toute l'entreprise ».
    """

    def test_grant_restreint_ne_voit_que_son_equipe(self):
        """Un RH restreint à une équipe : le grant existe, son périmètre prime."""
        grant = SimpleNamespace(scope_mode="teams")
        with patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=grant,
        ), patch.object(
            secure_queries,
            "filter_allowed_employee_ids_for_user",
            return_value=["e1"],
        ):
            autorises = secure_queries._employes_autorises(
                "mbc", "rh-restreint", "employees.view_all"
            )
        assert autorises == ["e1"]

    def test_grant_au_perimetre_vide_repond_aucun_pas_interdit(self):
        """Grant présent dont le périmètre ne couvre personne.

        L'utilisateur A le droit ; c'est la population qui est vide. La réponse
        juste est « aucun », pas « hors de votre périmètre » — et surtout aucun
        repli sur l'entreprise entière.
        """
        grant = SimpleNamespace(scope_mode="teams")
        with patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=grant,
        ), patch.object(
            secure_queries, "filter_allowed_employee_ids_for_user", return_value=[]
        ):
            resultat = secure_queries.absences_en_cours("mbc", {}, "rh-restreint")
        assert resultat["absences"] == []
        assert resultat.get("hors_perimetre") is None

    @pytest.mark.parametrize("role", ["admin", "rh", "collaborateur_rh"])
    def test_sans_grant_un_role_nomme_couvre_l_entreprise(self, role):
        """Admin / RH n'ont pas de ligne user_permissions : leurs droits
        viennent du rôle, et l'endpoint a déjà exigé un accès RH. Vérifié en
        production : sans cette branche, plus personne ne verrait rien."""
        patcher, _ = _patch_client(FakeResponse(data=[{"id": "e1"}, {"id": "e2"}]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            autorises = secure_queries._employes_autorises(
                "mbc", "rh-admin", "employees.view_all", role
            )
        assert autorises == ["e1", "e2"]

    def test_sans_grant_un_role_custom_ne_voit_personne(self):
        """Un rôle custom ne tient ses droits QUE de ses grants.

        Cas réel : DROZ-VINCENT (Mont Blanc Composite) a quinze permissions en
        périmètre « équipes », mais pas `employees.view_all`. Le repli des rôles
        nommés lui ouvrait les 89 salariés de l'entreprise — l'inverse exact de
        son paramétrage.
        """
        patcher, _ = _patch_client(FakeResponse(data=[{"id": "e1"}, {"id": "e2"}]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            autorises = secure_queries._employes_autorises(
                "mbc", "custom-user", "employees.view_all", "custom"
            )
        # `None` et non `[]` : l'assistant doit dire « hors de votre périmètre »
        # et non « aucun salarié », qui serait faux.
        assert autorises is None

    def test_role_inconnu_ne_voit_personne(self):
        """Fail-closed : un rôle non reconnu n'obtient pas le périmètre entreprise."""
        patcher, _ = _patch_client(FakeResponse(data=[{"id": "e1"}]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            autorises = secure_queries._employes_autorises(
                "mbc", "u", "employees.view_all", "collaborateur"
            )
        assert autorises is None

    def test_absences_en_cours_sans_user_id_ne_renvoie_rien(self):
        # Fail-closed : pas d'utilisateur, pas de périmètre, pas de données.
        resultat = secure_queries.absences_en_cours("mbc", {}, "")
        assert resultat["absences"] == []
        assert resultat["hors_perimetre"] is True

    def test_absences_en_cours_borne_la_requete_aux_salaries_autorises(self):
        patcher, client = _patch_client(FakeResponse(data=[]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=SimpleNamespace(scope_mode="teams"),
        ), patch.object(
            secure_queries,
            "filter_allowed_employee_ids_for_user",
            return_value=["e1", "e2"],
        ):
            secure_queries.absences_en_cours(
                "mbc", {"date_start": "2026-08-01", "date_end": "2026-08-31"}, "rh"
            )
        # La requête est filtrée sur l'entreprise ET sur la liste autorisée.
        assert ("company_id", "mbc") in client.query.eq_calls
        assert ("employee_id", ["e1", "e2"]) in client.query.in_calls

    def test_employee_detail_masque_le_salaire_sans_permission_paie(self):
        salarie = {
            "id": "e1",
            "first_name": "Alex",
            "last_name": "Martin",
            "job_title": "Technicien",
            "contract_type": "CDI",
            "employment_status": "actif",
            "hire_date": "2020-01-01",
            "date_debut_execution": "2020-01-01",
            "contract_end_date": None,
            "salaire_de_base": 2500.0,
            "team_id": None,
        }
        patcher, _ = _patch_client(FakeResponse(data=[salarie]))

        # Autorisé sur les salariés, mais pas sur la paie.
        def grants(user_id, company_id, permission):
            return ["e1"] if permission == "employees.view_all" else []

        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=SimpleNamespace(scope_mode="teams"),
        ), patch.object(
            secure_queries, "filter_allowed_employee_ids_for_user", side_effect=grants
        ):
            resultat = secure_queries.employee_detail("mbc", {"name": "Martin"}, "rh")

        fiche = resultat["employees"][0]
        assert fiche["salarie"] == "Alex Martin"
        assert fiche["salaire_de_base"] is None
        assert fiche["salaire_non_autorise"] is True

    def test_employee_detail_expose_le_salaire_avec_permission_paie(self):
        salarie = {
            "id": "e1",
            "first_name": "Alex",
            "last_name": "Martin",
            "job_title": "Technicien",
            "contract_type": "CDI",
            "employment_status": "actif",
            "hire_date": "2020-01-01",
            "date_debut_execution": "2020-01-01",
            "contract_end_date": None,
            "salaire_de_base": 2500.0,
            "team_id": None,
        }
        patcher, _ = _patch_client(FakeResponse(data=[salarie]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=SimpleNamespace(scope_mode="teams"),
        ), patch.object(
            secure_queries,
            "filter_allowed_employee_ids_for_user",
            return_value=["e1"],
        ):
            resultat = secure_queries.employee_detail("mbc", {"name": "Martin"}, "rh")
        assert resultat["employees"][0]["salaire_de_base"] == 2500.0

    def test_employee_detail_sans_aucun_droit_est_hors_perimetre(self):
        """Aucun grant et rôle non nommé : c'est un refus, pas une absence."""
        with patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            resultat = secure_queries.employee_detail(
                "mbc", {"name": "Martin"}, "custom-user", "custom"
            )
        assert resultat["employees"] == []
        assert resultat["hors_perimetre"] is True

    def test_echeances_rh_grant_vide_ne_renvoie_rien(self):
        with patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=SimpleNamespace(scope_mode="teams"),
        ), patch.object(
            secure_queries, "filter_allowed_employee_ids_for_user", return_value=[]
        ):
            resultat = secure_queries.echeances_rh("mbc", {}, "rh")
        assert resultat["echeances"] == []
        assert resultat["count"] == 0

    def test_echeances_rh_inclut_les_depassees(self):
        """Les échéances dépassées sont les plus urgentes : les exclure est
        exactement ce qui rendait les relances RH muettes."""
        hier = (date.today() - timedelta(days=10)).isoformat()
        salarie = {
            "id": "e1",
            "first_name": "Alex",
            "last_name": "Martin",
            "job_title": "Technicien",
            "team_id": None,
        }

        class QueryAvecNot(FakeQuery):
            """`FakeQuery` + `.not_.is_(col, "null")`, utilisé pour ne garder
            que les salariés dont la date d'échéance est renseignée."""

            @property
            def not_(self):
                parent = self

                class _Not:
                    def is_(self, column, value):
                        parent.eq_calls.append((f"not.{column}", value))
                        return parent

                return _Not()

        class ClientEcheances:
            def table(self, name):
                if name == "employees":
                    # `_index_salaries` et la requête titre de séjour tapent la
                    # même table : la doublure renvoie les deux formes réunies.
                    return QueryAvecNot(
                        FakeResponse(
                            data=[
                                {
                                    **salarie,
                                    "residence_permit_expiry_date": hier,
                                    "residence_permit_type": "Salarié",
                                }
                            ]
                        )
                    )
                return QueryAvecNot(FakeResponse(data=[]))

        with patch.object(
            secure_queries, "get_supabase_client", return_value=ClientEcheances()
        ), patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=SimpleNamespace(scope_mode="teams"),
        ), patch.object(
            secure_queries,
            "filter_allowed_employee_ids_for_user",
            return_value=["e1"],
        ):
            resultat = secure_queries.echeances_rh(
                "mbc", {"type": "titre_sejour"}, "rh"
            )

        assert resultat["count"] == 1
        echeance = resultat["echeances"][0]
        assert echeance["depassee"] is True
        assert echeance["jours_restants"] < 0
        assert echeance["salarie"] == "Alex Martin"


class TestDistinctionVideEtInterdit:
    """« Il n'y en a pas » et « vous n'y avez pas accès » sont deux réponses
    opposées. Les confondre fait dire une fausseté à l'assistant."""

    def test_echeances_signale_les_types_hors_perimetre(self):
        patcher, _ = _patch_client(FakeResponse(data=[]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            resultat = secure_queries.echeances_rh(
                "mbc", {"type": "titre_sejour"}, "custom-user", "custom"
            )
        assert resultat["count"] == 0
        assert resultat["types_hors_perimetre"] == ["titre_sejour"]

    def test_echeances_ne_signale_rien_quand_le_droit_existe(self):
        """Un vrai zéro ne doit pas être présenté comme un refus d'accès."""
        patcher, _ = _patch_client(FakeResponse(data=[]))
        with patcher, patch.object(
            secure_queries.scoped_permission_repository,
            "get_grant",
            return_value=None,
        ):
            resultat = secure_queries.echeances_rh(
                "mbc", {"type": "titre_sejour"}, "admin-user", "admin"
            )
        assert resultat["types_hors_perimetre"] == []
