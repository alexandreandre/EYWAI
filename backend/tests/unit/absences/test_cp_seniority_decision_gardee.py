"""La relecture d'une page ne remet pas au calcul automatique un droit validé ou corrigé par les RH."""
import pytest

from app.modules.absences.infrastructure import cp_seniority_repository as repo

ARGS = ("c1", "e1", 2026, 3.0, "non_cadre", 12.0, 0.0, {})


class BaseInterdite:
    def table(self, _nom):
        raise AssertionError("écriture interdite")


@pytest.mark.parametrize("statut", ["validated", "overridden"])
def test_decision_rh_gardee_a_la_relecture(monkeypatch, statut):
    ligne = {"id": "g1", "status": statut, "days_granted": 5.0}
    monkeypatch.setattr(repo, "get_cp_seniority_grant", lambda *_: ligne)
    monkeypatch.setattr(repo, "supabase", BaseInterdite())

    assert repo.upsert_cp_seniority_grant(*ARGS, garder_decision_rh=True) is ligne


def test_validation_explicite_toujours_ecrite(monkeypatch):
    monkeypatch.setattr(repo, "get_cp_seniority_grant", lambda *_: {"id": "g1", "status": "validated"})
    monkeypatch.setattr(repo, "supabase", BaseInterdite())

    with pytest.raises(AssertionError, match="écriture interdite"):
        repo.upsert_cp_seniority_grant(*ARGS, status="overridden")
