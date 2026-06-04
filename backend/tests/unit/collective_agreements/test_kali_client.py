"""Tests unitaires client KALI / PISTE (sans appels réseau)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.collective_agreements.infrastructure.kali_client import (
    KaliClient,
    KaliConventionMeta,
    KaliFetchResult,
    KaliNotFoundError,
    PisteNotConfiguredError,
    _extract_kalicont_id,
    _filter_vigueur_sections,
    _idcc_variants,
    _normalize_idcc,
)


class TestKaliHelpers:
    def test_idcc_variants(self):
        assert "1486" in _idcc_variants("1486")
        assert "1486" in _idcc_variants("01486")

    def test_normalize_idcc(self):
        assert _normalize_idcc("1486") == "1486"
        assert _normalize_idcc("44") == "0044"

    def test_extract_kalicont_id_from_cid_conteneur(self):
        row = {"id": "KALITEXT000005680030", "cidConteneur": "KALICONT000005635173"}
        assert _extract_kalicont_id(row) == "KALICONT000005635173"

    def test_extract_kalicont_id(self):
        row = {"id": "KALICONT000012345678"}
        assert _extract_kalicont_id(row) == "KALICONT000012345678"

    def test_filter_vigueur_sections(self):
        sections = [
            {"title": "A", "etat": "VIGUEUR"},
            {"title": "B", "etat": "ABROGE"},
            {"title": "C"},
        ]
        out = _filter_vigueur_sections(sections)
        assert len(out) == 2
        assert out[0]["title"] == "A"
        assert out[1]["title"] == "C"


class TestKaliClient:
    def test_not_configured_raises(self, monkeypatch):
        monkeypatch.delenv("PISTE_CLIENT_ID", raising=False)
        monkeypatch.delenv("PISTE_CLIENT_SECRET", raising=False)
        client = KaliClient(client_id="", client_secret="")
        assert not client.is_configured()
        with pytest.raises(PisteNotConfiguredError):
            client.require_configured()

    @patch.object(KaliClient, "resolve_convention")
    @patch.object(KaliClient, "_post")
    def test_fetch_convention_text_minimal(self, mock_post, mock_resolve):
        meta = KaliConventionMeta(
            idcc="1486",
            kalicont_id="KALICONT000012345678",
            title="CC Syntec",
            legifrance_url="https://www.legifrance.gouv.fr/conv_coll/id/KALICONT000012345678/",
        )
        mock_resolve.return_value = meta

        def post_handler(path, body):
            if "kaliCont" in path:
                return {
                    "conteneur": {
                        "sections": [
                            {
                                "title": "Textes Salaires",
                                "etat": "VIGUEUR",
                                "sections": [
                                    {
                                        "id": "SECTION-SALAIRE-1",
                                        "etat": "VIGUEUR_ETEN",
                                        "title": "Avenant salaires 2024",
                                        "articles": [
                                            {
                                                "num": "1",
                                                "texte": "Coefficient 240 : 1815 euros",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
                }
            return None

        mock_post.side_effect = post_handler
        client = KaliClient(client_id="id", client_secret="secret")
        result = client.fetch_convention_text("1486")

        assert isinstance(result, KaliFetchResult)
        assert result.meta.idcc == "1486"
        assert "1815" in result.full_text or "240" in result.full_text
        assert result.character_count > 0

    @patch.object(KaliClient, "_resolve_from_list")
    @patch.object(KaliClient, "_resolve_from_search")
    def test_resolve_convention_not_found(self, mock_search, mock_list):
        mock_list.return_value = None
        mock_search.return_value = None
        client = KaliClient(client_id="id", client_secret="secret")
        with pytest.raises(KaliNotFoundError):
            client.resolve_convention("9999")

    @patch.object(KaliClient, "_post")
    def test_resolve_from_list(self, mock_post):
        mock_post.return_value = {
            "results": [
                {
                    "id": "KALICONT000099999999",
                    "titre": "Convention test",
                }
            ]
        }
        client = KaliClient(client_id="id", client_secret="secret")
        meta = client._resolve_from_list("1486")
        assert meta is not None
        assert meta.kalicont_id.startswith("KALICONT")
        assert meta.title == "Convention test"
