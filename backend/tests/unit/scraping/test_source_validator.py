"""Tests validation mensuelle URLs officielles (Sonar + sync affichage)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


from agent.source_registry import (
    RATE_KEY_TO_SOURCE_KEYS,
    OfficialSource,
    refresh_all_payroll_source_links,
    refresh_payroll_source_links_for_rate_key,
)
from agent.source_validator import (
    _discover_display_url_with_sonar,
    _verify_official_url_with_sonar,
    validate_all_official_sources,
)
from core.official_domains import host_is_official


def test_host_is_official_accepts_state_hosts():
    assert host_is_official("https://www.urssaf.fr/foo")
    assert host_is_official("https://travail-emploi.gouv.fr/article/hs")
    assert host_is_official("https://entreprendre.service-public.gouv.fr/vosdroits/F78")
    assert not host_is_official("https://example.com/x")


@patch("openrouter_client.chat_completions_create")
@patch("openrouter_client.require_api_key")
def test_verify_sonar_confirms_current_url(mock_require, mock_chat):
    mock_require.return_value = "key"
    mock_chat.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "is_valid": True,
                            "official_url": "https://www.urssaf.fr/smic",
                            "rationale": "Page toujours canonique",
                        }
                    )
                )
            )
        ]
    )

    result = _verify_official_url_with_sonar(
        source_name="SMIC",
        source_key="SMIC",
        current_url="https://www.urssaf.fr/smic",
        target_field="smic",
        http_alive=True,
        http_status=200,
        final_url="https://www.urssaf.fr/smic",
    )

    assert result["action"] == "confirmed"
    assert result["official_url"] == "https://www.urssaf.fr/smic"
    assert result["sonar_used"] is True


@patch("openrouter_client.chat_completions_create")
@patch("openrouter_client.require_api_key")
def test_verify_sonar_proposes_new_url(mock_require, mock_chat):
    mock_require.return_value = "key"
    new_url = "https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/article/les-heures-supplementaires"
    mock_chat.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "is_valid": False,
                            "official_url": new_url,
                            "rationale": "Nouvelle fiche ministère",
                        }
                    )
                )
            )
        ]
    )

    result = _verify_official_url_with_sonar(
        source_name="Heures supplémentaires",
        source_key="HEURES_SUPP",
        current_url="https://boss.gouv.fr/contenu/ancien",
        target_field="heures_supp",
        http_alive=True,
        http_status=200,
        final_url="https://boss.gouv.fr/contenu/ancien",
    )

    assert result["action"] == "updated"
    assert result["official_url"] == new_url


@patch("agent.source_validator.refresh_all_payroll_source_links")
@patch("agent.source_validator._verify_official_url_with_sonar")
@patch("agent.source_validator.check_url_alive")
@patch("agent.source_validator.fetch_all_official_sources")
def test_validate_all_confirms_and_refreshes_display(
    mock_fetch,
    mock_alive,
    mock_sonar,
    mock_refresh,
):
    src = OfficialSource(
        source_id="id-1",
        source_key="SMIC",
        source_name="SMIC",
        primary_url="https://www.urssaf.fr/smic",
        alternative_urls=[],
        target_field="smic",
        scraper_name="SMIC",
    )
    mock_fetch.return_value = [src]
    mock_alive.return_value = (True, 200, "https://www.urssaf.fr/smic")
    mock_sonar.return_value = {
        "official_url": "https://www.urssaf.fr/smic",
        "action": "confirmed",
        "rationale": "ok",
        "sonar_used": True,
    }
    mock_refresh.return_value = {"rate_keys_updated": ["smic"], "cotisations_updated": False}

    supabase = MagicMock()
    table = MagicMock()
    supabase.table.return_value = table
    update_chain = MagicMock()
    table.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    summary = validate_all_official_sources(supabase=supabase)

    assert summary["checked"] == 1
    assert summary["confirmed"] == 1
    assert summary["sonar_used"] == 1
    mock_refresh.assert_called_once_with(supabase)


@patch("agent.source_validator.refresh_all_payroll_source_links")
@patch("agent.source_validator._discover_display_url_with_sonar")
@patch("agent.source_validator._verify_official_url_with_sonar")
@patch("agent.source_validator.check_url_alive")
@patch("agent.source_validator.fetch_all_official_sources")
def test_validate_failed_triggers_discovery_and_updates_display_only(
    mock_fetch,
    mock_alive,
    mock_verify,
    mock_discover,
    mock_refresh,
):
    old_url = "https://boss.gouv.fr/contenu/ancien"
    new_url = "https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/article/les-heures-supplementaires"
    src = OfficialSource(
        source_id="id-hs",
        source_key="HEURES_SUPP",
        source_name="Heures supplémentaires",
        primary_url=old_url,
        alternative_urls=[],
        target_field="heures_supp",
        scraper_name="heuressupp",
    )
    mock_fetch.return_value = [src]
    mock_alive.return_value = (False, 404, old_url)
    mock_verify.return_value = {
        "official_url": None,
        "action": "failed",
        "rationale": "URL morte",
        "sonar_used": True,
    }
    mock_discover.return_value = {
        "official_url": new_url,
        "action": "updated",
        "rationale": "Fiche ministère",
        "sonar_used": True,
    }
    mock_refresh.return_value = {"rate_keys_updated": ["heures_supp"], "cotisations_updated": False}

    supabase = MagicMock()
    table = MagicMock()
    supabase.table.return_value = table
    update_chain = MagicMock()
    table.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    with patch("agent.source_validator.update_primary_url") as mock_update:
        summary = validate_all_official_sources(supabase=supabase)

    assert summary["updated"] == 1
    assert summary["failed"] == 0
    mock_discover.assert_called_once()
    mock_update.assert_called_once()
    assert mock_update.call_args[0][2] == new_url
    detail = summary["details"][0]
    assert detail.get("display_only") is True
    assert detail.get("discovery_fallback") is True


@patch("agent.source_validator.refresh_all_payroll_source_links")
@patch("agent.source_validator._discover_display_url_with_sonar")
@patch("agent.source_validator._verify_official_url_with_sonar")
@patch("agent.source_validator.check_url_alive")
@patch("agent.source_validator.fetch_all_official_sources")
def test_validate_skips_when_sonar_down_and_http_inconclusive(
    mock_fetch,
    mock_alive,
    mock_verify,
    mock_discover,
    mock_refresh,
):
    src = OfficialSource(
        source_id="id-fnal",
        source_key="FNAL",
        source_name="FNAL",
        primary_url="https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/fonds-national-aide-logement.html",
        alternative_urls=[],
        target_field="cotisations",
        scraper_name="FNAL",
    )
    mock_fetch.return_value = [src]
    mock_alive.return_value = (False, 0, "Connection reset")
    mock_verify.return_value = {
        "official_url": None,
        "action": "failed",
        "rationale": "Sonar indisponible — repli HTTP uniquement",
        "sonar_used": False,
    }
    mock_discover.return_value = {
        "official_url": None,
        "action": "failed",
        "rationale": "Sonar indisponible pour la découverte d'URL d'affichage",
        "sonar_used": False,
    }
    mock_refresh.return_value = {"rate_keys_updated": [], "cotisations_updated": False}

    supabase = MagicMock()
    table = MagicMock()
    supabase.table.return_value = table
    update_chain = MagicMock()
    table.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    summary = validate_all_official_sources(supabase=supabase)

    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert summary["details"][0]["action"] == "skipped"
    payload = table.update.call_args[0][0]
    assert payload["url_validation_status"] == "inconclusive"


@patch("openrouter_client.chat_completions_create")
@patch("openrouter_client.require_api_key")
def test_call_sonar_json_caps_max_tokens(mock_require, mock_chat):
    """Évite le 402 OpenRouter quand le solde ne couvre pas 65536 tokens."""
    from agent.source_validator import _call_sonar_json

    mock_require.return_value = "key"
    mock_chat.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "is_valid": True,
                            "official_url": "https://www.urssaf.fr/x",
                            "rationale": "ok",
                        }
                    )
                )
            )
        ]
    )

    data = _call_sonar_json(
        system="sys",
        user="user",
        schema={
            "type": "object",
            "properties": {
                "is_valid": {"type": "boolean"},
                "official_url": {"type": ["string", "null"]},
                "rationale": {"type": "string"},
            },
            "required": ["is_valid", "official_url", "rationale"],
            "additionalProperties": False,
        },
        schema_name="url_validation",
    )

    assert data is not None
    assert mock_chat.call_args.kwargs["max_tokens"] == 2048


@patch("openrouter_client.chat_completions_create")
@patch("openrouter_client.require_api_key")
def test_discover_display_url_finds_replacement(mock_require, mock_chat):
    mock_require.return_value = "key"
    new_url = "https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/article/les-heures-supplementaires"
    mock_chat.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "official_url": new_url,
                            "rationale": "Référence actuelle",
                        }
                    )
                )
            )
        ]
    )

    result = _discover_display_url_with_sonar(
        source_name="Heures supplémentaires",
        source_key="HEURES_SUPP",
        current_url="https://boss.gouv.fr/contenu/ancien",
        target_field="heures_supp",
        prior_rationale="URL obsolète",
    )

    assert result["action"] == "updated"
    assert result["official_url"] == new_url


def test_refresh_payroll_source_links_updates_when_changed():
    supabase = MagicMock()
    payroll_table = MagicMock()
    sources_table = MagicMock()

    def table_router(name: str):
        if name == "payroll_config":
            return payroll_table
        if name == "scraping_sources":
            return sources_table
        return MagicMock()

    supabase.table.side_effect = table_router

    payroll_select = MagicMock()
    payroll_table.select.return_value = payroll_select
    payroll_select.eq.return_value = payroll_select
    payroll_select.maybe_single.return_value = payroll_select
    payroll_select.execute.return_value = MagicMock(
        data={"id": "cfg-1", "source_links": ["https://old.example/fr"]}
    )

    sources_select = MagicMock()
    sources_table.select.return_value = sources_select
    sources_select.eq.return_value = sources_select
    sources_select.limit.return_value = sources_select
    sources_select.execute.return_value = MagicMock(
        data=[
            {
                "id": "src-1",
                "source_key": "SMIC",
                "source_name": "SMIC",
                "primary_url": "https://www.urssaf.fr/smic",
                "alternative_urls": [],
                "target_field": "smic",
            }
        ]
    )

    payroll_update = MagicMock()
    payroll_table.update.return_value = payroll_update
    payroll_update.eq.return_value = payroll_update
    payroll_update.execute.return_value = MagicMock(data=[])

    changed = refresh_payroll_source_links_for_rate_key(supabase, "smic")
    assert changed is True
    payroll_table.update.assert_called_once()
    payload = payroll_table.update.call_args[0][0]
    assert payload["source_links"][0] == "https://www.urssaf.fr/smic"


def test_refresh_all_skips_unknown_rate_keys():
    supabase = MagicMock()
    with patch(
        "agent.source_registry.refresh_payroll_source_links_for_rate_key",
        return_value=False,
    ) as mock_one, patch(
        "agent.source_registry.refresh_cotisations_source_links",
        return_value=False,
    ) as mock_coti:
        result = refresh_all_payroll_source_links(supabase)
        assert mock_one.call_count == len(RATE_KEY_TO_SOURCE_KEYS) - 1
        mock_coti.assert_called_once()
        assert result["rate_keys_updated"] == []
