"""Tests ai_extractor sans appel réseau."""

from unittest.mock import MagicMock, patch

from core.ai_extractor import (
    extract_structured_json,
    extract_with_web_search,
    is_official_citation_url,
)


def test_is_official_citation_url_service_public_fr():
    assert is_official_citation_url(
        "https://www.service-public.fr/particuliers/vosdroits/F2329"
    )


def test_is_official_citation_url_service_public_gouv():
    assert is_official_citation_url(
        "https://www.service-public.gouv.fr/particuliers/actualites/A18916"
    )


def test_is_official_citation_url_urssaf_subdomain():
    assert is_official_citation_url("https://www.urssaf.fr/accueil/taux")


def test_is_official_citation_url_unedic():
    assert is_official_citation_url(
        "https://www.unedic.org/la-reglementation/fiches-thematiques/taux-de-contribution"
    )


def test_is_official_citation_url_rejects_blog():
    assert not is_official_citation_url("https://blog-rh.example.com/taux")


@patch("openrouter_client.chat_completions_create")
def test_extract_accepts_official_url_without_date(mock_chat):
    choice = MagicMock()
    choice.message.content = (
        '{"patronal": 3.45, "citation_url": "https://www.agirc-arrco.fr/page", '
        '"citation_date": null}'
    )
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    schema = {
        "type": "object",
        "properties": {"patronal": {"type": "number"}},
        "required": ["patronal"],
        "additionalProperties": False,
    }
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="Extraire le taux",
            json_schema=schema,
            schema_name="test",
        )
    assert data == {"patronal": 3.45}
    from core.ai_extractor import last_citation

    assert last_citation()["url"] == "https://www.agirc-arrco.fr/page"
    assert last_citation()["date"] == "01/01/2026"


@patch("openrouter_client.chat_completions_create")
def test_extract_accepts_service_public_gouv_citation(mock_chat):
    choice = MagicMock()
    choice.message.content = (
        '{"cas_general": 12.31, "citation_url": '
        '"https://www.service-public.gouv.fr/particuliers/actualites/A18916", '
        '"citation_date": "02/06/2026"}'
    )
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    schema = {
        "type": "object",
        "properties": {"cas_general": {"type": "number"}},
        "required": ["cas_general"],
        "additionalProperties": False,
    }
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="Extraire le SMIC",
            json_schema=schema,
            schema_name="smic",
        )
    assert data == {"cas_general": 12.31}


@patch("openrouter_client.chat_completions_create")
def test_extract_with_web_search_parses_json(mock_chat):
    choice = MagicMock()
    # La citation officielle datée est désormais imposée par le schéma.
    choice.message.content = (
        '{"patronal": 3.45, "citation_url": "https://www.urssaf.fr/taux", '
        '"citation_date": "01/01/2026"}'
    )
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    schema = {
        "type": "object",
        "properties": {"patronal": {"type": "number"}},
        "required": ["patronal"],
        "additionalProperties": False,
    }
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="Extraire le taux patronal AGS",
            json_schema=schema,
            schema_name="ags",
            include_domains=["urssaf.fr"],
        )
    # Les clés de citation sont consommées (popées) avant retour.
    assert data == {"patronal": 3.45}
    mock_chat.assert_called_once()
    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["model"] == "perplexity/sonar"
    assert "response_format" in call_kwargs
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert "plugins" in call_kwargs.get("extra_body", {})
    sent_schema = call_kwargs["response_format"]["json_schema"]["schema"]
    assert "citation_url" in sent_schema["properties"]
    assert "citation_date" in sent_schema["required"]


@patch("openrouter_client.chat_completions_create")
def test_extract_with_web_search_rejects_missing_citation(mock_chat):
    choice = MagicMock()
    choice.message.content = '{"patronal": 3.45}'  # pas de citation
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    schema = {
        "type": "object",
        "properties": {"patronal": {"type": "number"}},
        "required": ["patronal"],
        "additionalProperties": False,
    }
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="Extraire le taux patronal AGS",
            json_schema=schema,
            schema_name="ags",
        )
    assert data is None


@patch("openrouter_client.chat_completions_create")
def test_extract_with_web_search_rejects_non_official_citation(mock_chat):
    choice = MagicMock()
    choice.message.content = (
        '{"patronal": 3.45, "citation_url": "https://blog-rh.example.com/taux", '
        '"citation_date": "01/01/2026"}'
    )
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    schema = {
        "type": "object",
        "properties": {"patronal": {"type": "number"}},
        "required": ["patronal"],
        "additionalProperties": False,
    }
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="Extraire le taux patronal AGS",
            json_schema=schema,
            schema_name="ags",
        )
    assert data is None


@patch("openrouter_client.chat_completions_create")
def test_extract_with_web_search_returns_none_on_empty(mock_chat):
    choice = MagicMock()
    choice.message.content = ""
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    mock_chat.return_value = mock_resp
    with patch("openrouter_client.require_api_key"):
        data = extract_with_web_search(
            task_prompt="test",
            json_schema={
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
            schema_name="test",
        )
    assert data is None
