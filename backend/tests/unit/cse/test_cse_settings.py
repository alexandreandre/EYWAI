"""Tests unitaires API paramètres CSE entreprise."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.cse.application.cse_settings import (
    count_active_elected_members,
    get_company_cse_settings,
    save_company_cse_settings,
)


def _mock_supabase(count: int) -> MagicMock:
    """Simule le chaînage .table().select().eq().eq().gte().execute() de Supabase."""
    reponse = MagicMock()
    reponse.count = count
    chaine = MagicMock()
    chaine.select.return_value = chaine
    chaine.eq.return_value = chaine
    chaine.gte.return_value = chaine
    chaine.execute.return_value = reponse
    client = MagicMock()
    client.table.return_value = chaine
    return client, chaine


class TestCseSettingsCommands:
    def test_save_invalid_status_raises(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="cse_status invalide"):
                save_company_cse_settings("co-1", {"cse_status": "invalid"})

    def test_get_defaults_when_missing(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ):
            settings = get_company_cse_settings("co-1")
        assert settings.company_id == "co-1"
        assert settings.cse_status == "unknown"

    def test_save_carence(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ), patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.upsert",
            return_value={
                "company_id": "co-1",
                "cse_status": "carence",
                "carence_pv_document_id": None,
                "carence_valid_until": "2027-09-06",
                "notes": "PV 2019",
            },
        ):
            saved = save_company_cse_settings(
                "co-1",
                {
                    "cse_status": "carence",
                    "carence_valid_until": "2027-09-06",
                    "notes": "PV 2019",
                },
            )
        assert saved.cse_status == "carence"
        assert saved.carence_valid_until.isoformat() == "2027-09-06"


class TestCountActiveElectedMembers:
    """Un mandat is_active=True mais expiré ne doit plus compter comme actif : sinon
    l'import de mandats historiques bascule à tort une société en « élu / conforme »
    (compute_cse_compliance)."""

    def test_filtre_sur_is_active_et_end_date(self):
        client, chaine = _mock_supabase(2)
        with patch("app.core.database.supabase", client):
            resultat = count_active_elected_members("co-1")
        assert resultat == 2
        chaine.eq.assert_any_call("company_id", "co-1")
        chaine.eq.assert_any_call("is_active", True)
        assert chaine.gte.call_count == 1
        assert chaine.gte.call_args.args[0] == "end_date"

    def test_aucun_mandat_actif_renvoie_zero(self):
        client, _ = _mock_supabase(0)
        with patch("app.core.database.supabase", client):
            assert count_active_elected_members("co-1") == 0

    def test_count_none_renvoie_zero(self):
        client, chaine = _mock_supabase(None)
        with patch("app.core.database.supabase", client):
            assert count_active_elected_members("co-1") == 0
