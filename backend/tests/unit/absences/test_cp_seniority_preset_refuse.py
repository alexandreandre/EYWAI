"""Un préréglage refusé par la base se dit en clair, au lieu d'un « Erreur base de données » (502)."""
import pytest
from postgrest.exceptions import APIError

from app.modules.absences.application import cp_seniority_commands
from app.modules.absences.infrastructure import cp_seniority_repository as repo


class _Requete:
    def __init__(self, erreur):
        self._erreur = erreur

    def update(self, _row):
        return self

    def insert(self, _row):
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        raise self._erreur


class _BaseQuiRefuse:
    def __init__(self, erreur):
        self._erreur = erreur

    def table(self, _nom):
        return _Requete(self._erreur)


def _refus_contrainte():
    return APIError(
        {
            "code": "23514",
            "message": 'new row for relation "company_cp_seniority_settings" violates '
            'check constraint "company_cp_seniority_settings_preset_check"',
            "details": None,
            "hint": None,
        }
    )


def test_preset_refuse_par_la_base_devient_un_message_clair(monkeypatch):
    monkeypatch.setattr(repo, "get_cp_seniority_settings_row", lambda _cid: {"id": "s1"})
    monkeypatch.setattr(repo, "supabase", _BaseQuiRefuse(_refus_contrainte()))

    with pytest.raises(ValueError, match="métallurgie"):
        cp_seniority_commands.apply_cp_seniority_preset("c1", "metallurgie_idcc_3248")


def test_autre_erreur_de_base_inchangee(monkeypatch):
    autre = APIError({"code": "PGRST301", "message": "jwt expired", "details": None, "hint": None})
    monkeypatch.setattr(repo, "get_cp_seniority_settings_row", lambda _cid: {"id": "s1"})
    monkeypatch.setattr(repo, "supabase", _BaseQuiRefuse(autre))

    with pytest.raises(APIError):
        cp_seniority_commands.apply_cp_seniority_preset("c1", "metallurgie_idcc_3248")
