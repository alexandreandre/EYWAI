from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx

from app.core.database import supabase
from app.modules.webhooks.infrastructure.adresse_sure import (
    AdresseVerifiee,
    AdresseWebhookRefusee,
    verifier_adresse_webhook,
)

_log = logging.getLogger(__name__)

_MAX_LOG_BODY = 8000
# Durée totale de lecture de la réponse : le timeout httpx vaut par lecture, un serveur
# qui répond au goutte-à-goutte tiendrait sinon la requête RH indéfiniment.
_DUREE_MAX_SECONDES = 10.0


def _stable_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def _adresses_par_preference(verifiee: AdresseVerifiee) -> List[Any]:
    """IPv4 d'abord (sortie IPv6 pas toujours disponible), puis IPv6, ordre DNS gardé."""
    return [a for a in verifiee.adresses if a.version == 4] + [
        a for a in verifiee.adresses if a.version == 6
    ]


def _cible_epinglee(
    verifiee: AdresseVerifiee, ip: Any
) -> Tuple[str, str, str, Optional[Tuple[str, str]]]:
    """URL réécrite sur une adresse vérifiée, en-tête Host, nom SNI, identifiants.

    Le serveur reçoit le même Host et le même nom TLS qu'avec l'URL d'origine ; seule la
    résolution est figée sur l'adresse que la garde a jugée publique.
    """
    parties = urlsplit(verifiee.url)
    hote_ip = f"[{ip}]" if ip.version == 6 else str(ip)
    suffixe_port = f":{verifiee.port}" if verifiee.port is not None else ""
    cible = urlunsplit(("https", hote_ip + suffixe_port, parties.path or "/", parties.query, ""))
    hote = f"[{verifiee.hote}]" if ":" in verifiee.hote else verifiee.hote
    auth = None
    if parties.username is not None:
        auth = (unquote(parties.username), unquote(parties.password or ""))
    return cible, hote + suffixe_port, verifiee.hote, auth


class WebhookRepository:
    def list_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        """Pattern liste EYWAI"""
        try:
            res = (
                supabase.table("webhook_configs")
                .select("*")
                .eq("company_id", company_id)
                .order("created_at", desc=True)
                .execute()
            )
            return list(res.data or [])
        except Exception:
            _log.exception("[webhooks] list_by_company")
            return []

    def create(
        self, company_id: str, data: Dict[str, Any], created_by: str
    ) -> Dict[str, Any]:
        _ = created_by
        row = {
            "company_id": company_id,
            "name": data["name"],
            "url": str(data["url"]),
            "secret": data.get("secret") or None,
            "events": data["events"],
            "is_active": data.get("is_active", True),
        }
        res = supabase.table("webhook_configs").insert(row).execute()
        if not res.data:
            raise RuntimeError("Création webhook : aucune ligne retournée.")
        created = res.data[0] if isinstance(res.data, list) else res.data
        return dict(created)

    def update(self, webhook_id: str, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        patch: Dict[str, Any] = {}
        if "name" in data and data["name"] is not None:
            patch["name"] = data["name"]
        if "url" in data and data["url"] is not None:
            patch["url"] = str(data["url"])
        if "secret" in data:
            patch["secret"] = data["secret"] if data["secret"] else None
        if "events" in data and data["events"] is not None:
            patch["events"] = data["events"]
        if "is_active" in data and data["is_active"] is not None:
            patch["is_active"] = data["is_active"]
        if not patch:
            res = (
                supabase.table("webhook_configs")
                .select("*")
                .eq("id", webhook_id)
                .eq("company_id", company_id)
                .single()
                .execute()
            )
            if not res.data:
                raise LookupError("Webhook introuvable.")
            return dict(res.data)
        res = (
            supabase.table("webhook_configs")
            .update(patch)
            .eq("id", webhook_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not res.data:
            raise LookupError("Webhook introuvable.")
        updated = res.data[0] if isinstance(res.data, list) else res.data
        return dict(updated)

    def delete(self, webhook_id: str, company_id: str) -> bool:
        res = (
            supabase.table("webhook_configs")
            .delete()
            .eq("id", webhook_id)
            .eq("company_id", company_id)
            .execute()
        )
        return bool(res.data)

    def get_by_id(self, webhook_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        try:
            res = (
                supabase.table("webhook_configs")
                .select("*")
                .eq("id", webhook_id)
                .eq("company_id", company_id)
                .maybe_single()
                .execute()
            )
            return dict(res.data) if res is not None and res.data else None
        except Exception:
            _log.exception("[webhooks] get_by_id")
            return None

    def list_logs(self, webhook_id: str, company_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        wh = self.get_by_id(webhook_id, company_id)
        if not wh:
            return []
        try:
            res = (
                supabase.table("webhook_logs")
                .select("*")
                .eq("webhook_id", webhook_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return list(res.data or [])
        except Exception:
            _log.exception("[webhooks] list_logs")
            return []

    def _post_webhook(
        self,
        webhook: Dict[str, Any],
        event_type: str,
        company_id: str,
        business_payload: Dict[str, Any],
    ) -> Tuple[int, Optional[str], int, Dict[str, Any]]:
        envelope: Dict[str, Any] = {
            "event": event_type,
            "timestamp": int(time.time()),
            "company_id": company_id,
            "payload": business_payload,
        }
        body = _stable_json(envelope)
        body_bytes = body.encode("utf-8")
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        sec = webhook.get("secret")
        if sec:
            sig = hmac.new(
                str(sec).encode("utf-8"),
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            valeur_signature = f"sha256={sig}"
            headers["X-Martine-Signature"] = valeur_signature
            # Ancien nom, encore envoyé tant que les destinataires n'ont pas migré.
            headers["X-EYWAI-Signature"] = valeur_signature
        t0 = time.perf_counter()
        status = 0
        text: Optional[str] = None
        try:
            # Garde SSRF à l'envoi : une adresse enregistrée avant la garde, ou un nom dont
            # la réponse DNS a changé depuis, ne part pas vers une adresse interne.
            verifiee = verifier_adresse_webhook(str(webhook.get("url") or ""))
        except AdresseWebhookRefusee as refus:
            _log.warning("[webhooks] envoi bloqué : %s", refus)
            return 0, f"Envoi bloqué : {refus}", int((time.perf_counter() - t0) * 1000), envelope
        try:
            # Connexion sur une adresse vérifiée (pas de seconde résolution), certificat
            # contrôlé contre le nom (SNI), aucune redirection suivie, aucun proxy d'env.
            # Une adresse injoignable passe à la suivante ; la réponse lue est bornée.
            with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
                adresses = _adresses_par_preference(verifiee)
                for rang, ip in enumerate(adresses):
                    cible, host_header, sni, auth = _cible_epinglee(verifiee, ip)
                    headers["Host"] = host_header
                    try:
                        with client.stream(
                            "POST",
                            cible,
                            content=body_bytes,
                            headers=headers,
                            auth=auth,
                            extensions={"sni_hostname": sni},
                        ) as r:
                            status = r.status_code
                            lu = bytearray()
                            for bloc in r.iter_bytes():
                                lu += bloc
                                if (
                                    len(lu) >= _MAX_LOG_BODY
                                    or time.perf_counter() - t0 > _DUREE_MAX_SECONDES
                                ):
                                    break
                            text = bytes(lu[:_MAX_LOG_BODY]).decode("utf-8", "replace")
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        if rang == len(adresses) - 1:
                            raise
        except Exception:
            _log.debug("[webhooks] POST échoué (silencieux)", exc_info=True)
            status = 0
            text = None
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return status, text, duration_ms, envelope

    def _persist_delivery(
        self,
        webhook_id: str,
        event_type: str,
        envelope: Dict[str, Any],
        status: int,
        body_text: Optional[str],
        duration_ms: int,
    ) -> None:
        try:
            supabase.table("webhook_logs").insert(
                {
                    "webhook_id": webhook_id,
                    "event_type": event_type,
                    "payload": envelope,
                    "response_status": status if status else None,
                    "response_body": body_text,
                    "duration_ms": duration_ms,
                }
            ).execute()
        except Exception:
            _log.debug("[webhooks] log insert ignoré", exc_info=True)
        try:
            supabase.table("webhook_configs").update(
                {
                    "last_triggered_at": datetime.now(timezone.utc).isoformat(),
                    "last_status_code": status if status else None,
                }
            ).eq("id", webhook_id).execute()
        except Exception:
            _log.debug("[webhooks] update last_triggered ignoré", exc_info=True)

    def trigger_event(
        self,
        company_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Best effort — ne jamais lever d'exception.
        """
        try:
            res = (
                supabase.table("webhook_configs")
                .select("*")
                .eq("company_id", company_id)
                .eq("is_active", True)
                .execute()
            )
            rows: List[Dict[str, Any]] = list(res.data or [])
        except Exception:
            return
        for wh in rows:
            try:
                evs = wh.get("events") or []
                if event_type not in evs:
                    continue
                wid = str(wh["id"])
                status, text, duration_ms, envelope = self._post_webhook(
                    wh, event_type, company_id, payload
                )
                self._persist_delivery(wid, event_type, envelope, status, text, duration_ms)
            except Exception:
                pass

    def send_test(self, webhook_id: str, company_id: str) -> Tuple[int, bool]:
        wh = self.get_by_id(webhook_id, company_id)
        if not wh:
            raise LookupError("Webhook introuvable.")
        test_payload = {
            "test": True,
            "message": "Ping Martine — webhook de test",
            "timestamp": int(time.time()),
        }
        # « Tester » dit pourquoi l'adresse est refusée, au lieu d'un simple échec.
        verifier_adresse_webhook(str(wh.get("url") or ""))
        status, _, _, _ = self._post_webhook(
            wh, "webhook.test", company_id, test_payload
        )
        ok = 200 <= status < 300
        return status, ok


webhook_repository = WebhookRepository()
