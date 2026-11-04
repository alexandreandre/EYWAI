"""Plus d'appels vers des tables ou colonnes qui n'existent pas.

Audit de modernisation du 03/11/2026 (R4, temps 2 point 5) : chaque jour, 915
réponses 404 sur `yousign_configs`, 184 sur `payroll_runs`, 2 937 erreurs
« colonne absente » sur `employees.is_cadre_dirigeant` (deux allers-retours par
lecture), et 37 727 appels à `set_session_company`, que rien ne lisait. La
réponse ne change pas : ces lectures échouaient toujours et retombaient sur la
même valeur, qui est maintenant rendue sans appel.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[2] / "app"


def test_yousign_se_juge_a_la_cle_sans_lire_de_table(monkeypatch):
    from app.modules.signatures.infrastructure import queries

    base = MagicMock()
    with patch.object(queries, "supabase", base):
        monkeypatch.setenv("YOUSIGN_API_KEY", "cle")
        assert queries.get_yousign_config("societe-1") == {"id": "env", "company_id": "societe-1"}
        monkeypatch.delenv("YOUSIGN_API_KEY")
        assert queries.get_yousign_config("societe-1") is None
    base.table.assert_not_called()


def test_le_planning_n_interroge_plus_une_cloture_qui_n_existe_pas():
    from app.modules.planning.infrastructure import queries

    base = MagicMock()
    with patch.object(queries, "supabase", base):
        assert queries.get_payroll_period_locked("societe-1", 10, 2026) is False
    base.table.assert_not_called()


def test_l_analytique_ne_lit_plus_payroll_runs():
    from app.modules.payroll.infrastructure import analytics_repository as module

    base = MagicMock()
    with patch.object(module, "supabase", base):
        depot = module.PayrollAnalyticsRepository()
        assert depot.fetch_payroll_runs("societe-1", 2026) == []
        assert depot.is_period_closed("societe-1", 2026, 10) is False
    base.table.assert_not_called()


def test_l_anciennete_des_conges_se_lit_en_une_requete_sans_la_colonne_absente():
    from app.modules.absences.application import cp_seniority_queries as module

    base = MagicMock()
    requete = base.table.return_value.select.return_value.eq.return_value.limit.return_value
    requete.execute.return_value = MagicMock(data=[{"hire_date": "2020-01-01", "statut": "Cadre"}])
    with patch.object(module, "supabase", base):
        contexte = module.load_employee_cp_seniority_context("salarie-1")

    assert base.table.return_value.select.call_count == 1
    colonnes = base.table.return_value.select.call_args.args[0]
    assert "is_cadre_dirigeant" not in colonnes
    assert contexte.is_cadre_dirigeant is False


@pytest.mark.parametrize(
    "motif",
    [
        r"table\(\s*[\"']yousign_configs[\"']",
        r"table\(\s*[\"']payroll_runs[\"']",
        r"[\"']set_session_company[\"']",
        r"select\([^)]*is_cadre_dirigeant",
        r"[\"'][^\"'\n]*, is_cadre_dirigeant[\"']",
    ],
)
def test_aucun_appel_ne_revient(motif):
    trouves = [
        str(f.relative_to(APP))
        for f in APP.rglob("*.py")
        if re.search(motif, f.read_text(encoding="utf-8"))
    ]
    assert trouves == []
