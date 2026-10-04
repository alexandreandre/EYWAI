"""Un bulletin supprimé laisse une trace datée : les exports de son mois deviennent « à refaire ».

Un bulletin recalculé ou ajouté se date lui-même (`generated_at`) ; un bulletin
supprimé n'est plus là pour le dire. La suppression s'inscrit donc au journal
d'audit (`payslip.delete`, avec l'année et le mois), qui est relu par l'écran
des exports. Jamais bloquant : le bulletin est déjà supprimé.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.constants import AUDIT_BULLETIN_SUPPRIME
from app.modules.payslips.infrastructure import repository as depot

pytestmark = pytest.mark.unit

SOCIETE = "11111111-1111-1111-1111-111111111111"
SALARIE = "44444444-4444-4444-4444-444444444444"
BULLETIN = "33333333-3333-3333-3333-333333333333"


def _client_avec(ligne: dict | None) -> MagicMock:
    client = MagicMock()
    requete = client.table.return_value.select.return_value.eq.return_value
    requete.maybe_single.return_value.execute.return_value = SimpleNamespace(data=ligne) if ligne else None
    return client


@pytest.fixture
def journal(monkeypatch):
    audit = MagicMock()
    monkeypatch.setattr(depot, "audit_repository", audit)
    monkeypatch.setattr(depot, "recalculer_credits_repos_employe", lambda *_a: None)
    return audit


def test_la_suppression_s_inscrit_au_journal_avec_son_mois(monkeypatch, journal):
    ligne = {"pdf_storage_path": None, "employee_id": SALARIE, "company_id": SOCIETE, "year": 2026, "month": 9}
    monkeypatch.setattr(depot, "supabase", _client_avec(ligne))

    assert depot.PayslipRepository().delete(BULLETIN) is True

    journal.log.assert_called_once_with(
        SOCIETE,
        None,
        None,
        AUDIT_BULLETIN_SUPPRIME,
        "payslip",
        resource_id=BULLETIN,
        details={"employee_id": SALARIE, "year": 2026, "month": 9},
    )


def test_un_bulletin_deja_parti_n_inscrit_rien(monkeypatch, journal):
    monkeypatch.setattr(depot, "supabase", _client_avec(None))

    assert depot.PayslipRepository().delete(BULLETIN) is False

    journal.log.assert_not_called()


def test_l_action_a_un_libelle_dans_le_journal():
    from app.modules.audit.infrastructure.repository import ACTIONS_LABELS

    assert ACTIONS_LABELS[AUDIT_BULLETIN_SUPPRIME] == "Suppression bulletin"
