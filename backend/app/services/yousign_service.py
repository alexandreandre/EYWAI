"""
Client HTTP Yousign API v3 (signature requests).

Variables d'environnement :
  YOUSIGN_API_KEY
  YOUSIGN_BASE_URL (ex. https://api.yousign.app/v3 ou https://api-sandbox.yousign.app/v3)
  YOUSIGN_WEBHOOK_SECRET (clé de vérification HMAC des webhooks)
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests


class YousignService:
    """Appels API Yousign v3 (demande de signature AES, statut, téléchargement, webhook)."""

    def __init__(self) -> None:
        self._api_key = os.getenv("YOUSIGN_API_KEY", "").strip()
        self._base_url = (
            os.getenv("YOUSIGN_BASE_URL", "https://api.yousign.app/v3").strip().rstrip("/")
        )
        self._webhook_secret = os.getenv("YOUSIGN_WEBHOOK_SECRET", "").strip()

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise RuntimeError(
                "YOUSIGN_API_KEY manquant : configurez la variable d'environnement pour utiliser Yousign."
            )
        return self._api_key

    def _headers(self, json_body: bool = True) -> Dict[str, str]:
        h: Dict[str, str] = {
            "Authorization": f"Bearer {self._require_api_key()}",
            "Accept": "application/json",
        }
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _raise_for_status(self, resp: requests.Response, context: str) -> None:
        if resp.ok:
            return
        detail = resp.text or resp.reason
        try:
            err_json = resp.json()
            if isinstance(err_json, dict):
                detail = str(err_json.get("detail") or err_json.get("message") or err_json)
        except Exception:
            pass
        raise RuntimeError(
            f"Yousign API ({context}) HTTP {resp.status_code}: {detail[:2000]}"
        )

    def create_signature_request(
        self,
        document_content: bytes,
        document_name: str,
        signer_email: str,
        signer_first_name: str,
        signer_last_name: str,
        expiration_days: int = 15,
        second_signer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crée une demande de signature (niveau AES), téléverse le PDF, ajoute le(s) signataire(s), active.
        Retourne { "procedure_id": str, "status": "pending" }.
        """
        exp_days = max(1, min(int(expiration_days), 365))
        expiration_date = (date.today() + timedelta(days=exp_days)).isoformat()

        ordered = bool(second_signer_email and second_signer_email.strip())

        create_payload: Dict[str, Any] = {
            "name": document_name[:128] if document_name else "Signature EYWAI",
            "delivery_mode": "email",
            "timezone": "Europe/Paris",
            "expiration_date": expiration_date,
        }
        if ordered:
            create_payload["ordered_signers"] = True

        r0 = requests.post(
            f"{self._base_url}/signature_requests",
            headers=self._headers(),
            json=create_payload,
            timeout=120,
        )
        self._raise_for_status(r0, "signature_requests POST")
        sr = r0.json()
        procedure_id = sr["id"]

        files = {
            "file": (document_name or "document.pdf", document_content, "application/pdf"),
        }
        data_form = {"nature": "signable_document"}
        r1 = requests.post(
            f"{self._base_url}/signature_requests/{procedure_id}/documents",
            headers={"Authorization": f"Bearer {self._require_api_key()}", "Accept": "application/json"},
            files=files,
            data=data_form,
            timeout=120,
        )
        self._raise_for_status(r1, "documents upload")
        doc = r1.json()
        document_id = doc["id"]

        def _signer_body(
            email: str,
            first: str,
            last: str,
            y_pos: int,
        ) -> Dict[str, Any]:
            return {
                "info": {
                    "first_name": first[:128] or "Signataire",
                    "last_name": last[:128] or "EYWAI",
                    "email": email.strip(),
                    "locale": "fr",
                },
                "signature_level": "advanced_electronic_signature",
                "signature_authentication_mode": "otp_email",
                "fields": [
                    {
                        "type": "signature",
                        "document_id": document_id,
                        "page": 1,
                        "x": 120,
                        "y": y_pos,
                    }
                ],
            }

        r2 = requests.post(
            f"{self._base_url}/signature_requests/{procedure_id}/signers",
            headers=self._headers(),
            json=_signer_body(
                signer_email,
                signer_first_name,
                signer_last_name,
                680,
            ),
            timeout=120,
        )
        self._raise_for_status(r2, "signer 1 POST")

        if ordered:
            se = second_signer_email.strip()
            local, _, domain = se.partition("@")
            r3 = requests.post(
                f"{self._base_url}/signature_requests/{procedure_id}/signers",
                headers=self._headers(),
                json=_signer_body(
                    se,
                    (local or "Signataire")[:128],
                    (domain or "second")[:128],
                    520,
                ),
                timeout=120,
            )
            self._raise_for_status(r3, "signer 2 POST")

        r_act = requests.post(
            f"{self._base_url}/signature_requests/{procedure_id}/activate",
            headers=self._headers(),
            timeout=120,
        )
        self._raise_for_status(r_act, "activate")

        return {"procedure_id": procedure_id, "status": "pending"}

    def get_signature_status(self, procedure_id: str) -> str:
        """Mappe le statut Yousign vers pending / signed / refused / expired."""
        resp = requests.get(
            f"{self._base_url}/signature_requests/{procedure_id}",
            headers=self._headers(),
            timeout=60,
        )
        self._raise_for_status(resp, "signature_requests GET")
        data = resp.json()
        raw = (data.get("status") or "").lower()
        if raw == "done":
            return "signed"
        if raw == "expired":
            return "expired"
        if raw in ("declined", "rejected", "deleted", "canceled"):
            return "refused"
        return "pending"

    def download_signed_document(self, procedure_id: str) -> bytes:
        """Télécharge le PDF signé (version completed)."""
        resp = requests.get(
            f"{self._base_url}/signature_requests/{procedure_id}/documents/download",
            headers={
                "Authorization": f"Bearer {self._require_api_key()}",
                "Accept": "application/pdf",
            },
            params={"version": "completed"},
            timeout=120,
        )
        self._raise_for_status(resp, "documents download")
        return resp.content

    def validate_webhook(self, payload: bytes, signature: str) -> bool:
        """Valide l'en-tête X-Yousign-Signature-256 (HMAC SHA-256 du corps brut)."""
        if not self._webhook_secret or not signature:
            return False
        digest = hmac.new(
            self._webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        expected = f"sha256={digest}"
        try:
            return hmac.compare_digest(
                signature.strip().encode("utf-8"),
                expected.encode("utf-8"),
            )
        except Exception:
            return False


yousign_service = YousignService()
