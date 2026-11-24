"""Le webhook signe avec le nouvel en-tête ET l'ancien (destinataires non migrés)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.webhooks.infrastructure.repository import WebhookRepository


def test_les_deux_en_tetes_de_signature_sont_envoyes(monkeypatch):
    from app.modules.webhooks.infrastructure import adresse_sure

    # Aucune résolution réelle : l'hôte est servi par une adresse publique doublée.
    monkeypatch.setattr(adresse_sure, "_resoudre", lambda hote, port: ["93.184.215.14"])
    repo = WebhookRepository()
    reponse = MagicMock(status_code=200)
    reponse.iter_bytes.return_value = iter([b"ok"])
    client = MagicMock()
    client.__enter__.return_value.stream.return_value.__enter__.return_value = reponse
    with patch("app.modules.webhooks.infrastructure.repository.httpx.Client", return_value=client):
        repo._post_webhook(
            {"url": "https://exemple.test/hook", "secret": "s3cret"},
            "x.test", "company-1", {"a": 1},
        )
    headers = client.__enter__.return_value.stream.call_args.kwargs["headers"]
    assert headers["X-Martine-Signature"].startswith("sha256=")
    assert headers["X-EYWAI-Signature"] == headers["X-Martine-Signature"]
