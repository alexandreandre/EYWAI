"""Le webhook signe avec le nouvel en-tête ET l'ancien (destinataires non migrés)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.webhooks.infrastructure.repository import WebhookRepository


def test_les_deux_en_tetes_de_signature_sont_envoyes():
    repo = WebhookRepository()
    reponse = MagicMock(status_code=200, text="ok")
    client = MagicMock()
    client.__enter__.return_value.post.return_value = reponse
    with patch("app.modules.webhooks.infrastructure.repository.httpx.Client", return_value=client):
        repo._post_webhook(
            {"url": "https://exemple.test/hook", "secret": "s3cret"},
            "x.test", "company-1", {"a": 1},
        )
    headers = client.__enter__.return_value.post.call_args.kwargs["headers"]
    assert headers["X-Martine-Signature"].startswith("sha256=")
    assert headers["X-EYWAI-Signature"] == headers["X-Martine-Signature"]
