"""Connecteur API Cegid Loop (Quadra) — import FEC asynchrone.

Aligné sur la documentation officielle Cegid Loop API Management :
- Auth : headers ``x-apikey`` (clé:secret) + ``Ocp-Apim-Subscription-Key``
  (aucun flux OAuth pour les API Loop publiques).
  https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/GetStart.html
- Dépôt fichier : ``GET /getFileUrlDeposit?filename=...`` → ``depositUrl`` (PUT Azure) ou ``uri``.
  https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/EcritureComptableImportURIFichier.html
- Import FEC : ``POST /importFEC`` body ``{codeIbs, URI|URL, SIRET?}`` → ``accountingImportRequestId``.
  https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/EcritureComptableImportFec.html
- Statut : ``GET /getImportStatus?accountingImportRequestId=...`` → ``status`` (1 attente, 2 en cours, 3 succès, 4 erreur).
  https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/EcritureComptableImportStatut.html
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core import settings
from app.core.logging import get_logger
from app.modules.accounting_integration.domain.value_objects import (
    ConnectionTestResult,
    TransmissionResult,
)
from app.shared.utils.secret_store import decrypt_secret, has_stored_secret

logger = get_logger("modules.accounting_integration.cegid_quadra")

# Host public documenté des API Cegid Loop (surchargeable par entreprise / env).
DEFAULT_BASE_URL = "https://loop-publicapi.cegid.com"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5

# Endpoints officiels Cegid Loop (relatifs au host).
FILE_DEPOSIT_PATH = "/getFileUrlDeposit"
FEC_IMPORT_PATH = "/importFEC"
IMPORT_STATUS_PATH = "/getImportStatus"

# Statuts d'import Cegid Loop (cf. doc Statut des imports).
CEGID_STATUS_PENDING = 1   # en attente
CEGID_STATUS_RUNNING = 2   # en cours
CEGID_STATUS_SUCCESS = 3   # terminé avec succès
CEGID_STATUS_ERROR = 4     # terminé en erreur


@dataclass(frozen=True)
class CegidCredentials:
    loop_apikey: str  # APIKey complète au format key:client_secret (header x-apikey)
    apim_subscription_key: str  # header Ocp-Apim-Subscription-Key
    code_dossier: str  # codeIbs du dossier comptable
    api_base_url: str


def _auth_from_raw(raw: Dict[str, Any]) -> tuple[str, str, str]:
    loop_apikey = str(
        raw.get("loop_apikey") or raw.get("api_key") or ""
    ).strip()
    apim_subscription_key = str(
        raw.get("apim_subscription_key") or raw.get("subscription_key") or ""
    ).strip()
    base = (
        str(raw.get("api_base_url") or "").strip()
        or getattr(settings, "CEGID_LOOP_API_BASE_URL", DEFAULT_BASE_URL)
    ).rstrip("/")
    return loop_apikey, apim_subscription_key, base


def _code_dossier_from_config(config: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> str:
    column_value = str(config.get("code_dossier_cegid") or "").strip()
    if column_value:
        return column_value
    if raw:
        return str(
            raw.get("code_dossier") or raw.get("codeIbs") or raw.get("code_ibs") or ""
        ).strip()
    return ""


def has_platform_cegid_auth_keys(platform_row: Optional[Dict[str, Any]]) -> bool:
    if not platform_row or not has_stored_secret(platform_row.get("platform_credentials_ref")):
        return False
    raw = decrypt_secret(platform_row.get("platform_credentials_ref")) or {}
    loop_apikey, apim_subscription_key, _ = _auth_from_raw(raw)
    return bool(loop_apikey and apim_subscription_key)


def parse_platform_cegid_auth(
    platform_row: Optional[Dict[str, Any]],
) -> Optional[CegidCredentials]:
    """Clés cabinet (sans codeIbs) — test auth plateforme."""
    if not has_platform_cegid_auth_keys(platform_row):
        return None
    raw = decrypt_secret((platform_row or {}).get("platform_credentials_ref")) or {}
    loop_apikey, apim_subscription_key, base = _auth_from_raw(raw)
    return CegidCredentials(
        loop_apikey=loop_apikey,
        apim_subscription_key=apim_subscription_key,
        code_dossier="",
        api_base_url=base,
    )


def _company_has_dedicated_auth(config: Dict[str, Any]) -> bool:
    """Mode dédié : explicite ou legacy (blob entreprise avec clés auth)."""
    mode = str(config.get("cegid_auth_mode") or "shared").strip().lower()
    if mode == "dedicated":
        return True
    if not has_stored_secret(config.get("credentials_ref")):
        return False
    raw = decrypt_secret(config.get("credentials_ref")) or {}
    loop_apikey, apim_subscription_key, _ = _auth_from_raw(raw)
    return bool(loop_apikey and apim_subscription_key)


def resolve_cegid_auth_source(
    config: Dict[str, Any],
    platform_row: Optional[Dict[str, Any]] = None,
) -> str:
    """Retourne shared | dedicated | incomplete."""
    if _company_has_dedicated_auth(config):
        return "dedicated"
    if has_platform_cegid_auth_keys(platform_row):
        code = _code_dossier_from_config(config)
        if code:
            return "shared"
        return "incomplete"
    return "incomplete"


def parse_cegid_credentials(
    config: Dict[str, Any],
    platform_row: Optional[Dict[str, Any]] = None,
) -> Optional[CegidCredentials]:
    """Fusionne clés cabinet (plateforme ou dédiées filiale) + codeIbs."""
    company_raw: Dict[str, Any] = {}
    if has_stored_secret(config.get("credentials_ref")):
        company_raw = decrypt_secret(config.get("credentials_ref")) or {}

    dedicated = _company_has_dedicated_auth(config)
    loop_apikey, apim_subscription_key, base = _auth_from_raw(company_raw)

    if dedicated:
        if not loop_apikey or not apim_subscription_key:
            return None
    else:
        platform_auth = parse_platform_cegid_auth(platform_row)
        if not platform_auth:
            return None
        loop_apikey = platform_auth.loop_apikey
        apim_subscription_key = platform_auth.apim_subscription_key
        base = platform_auth.api_base_url

    code_dossier = _code_dossier_from_config(config, company_raw)
    if not loop_apikey or not apim_subscription_key or not code_dossier:
        return None
    return CegidCredentials(
        loop_apikey=loop_apikey,
        apim_subscription_key=apim_subscription_key,
        code_dossier=code_dossier,
        api_base_url=base,
    )


def has_complete_cegid_credentials(
    config: Dict[str, Any],
    platform_row: Optional[Dict[str, Any]] = None,
) -> bool:
    return parse_cegid_credentials(config, platform_row) is not None


def _validate_apikey_format(loop_apikey: str) -> None:
    """L'APIKey Cegid est composée de ``key`` + ``:`` + ``client secret``."""
    if ":" not in loop_apikey:
        raise ValueError("APIKey Cegid invalide : format attendu clé:secret")
    key, _, secret = loop_apikey.partition(":")
    if not key.strip() or not secret.strip():
        raise ValueError("APIKey Cegid invalide : clé ou secret vide")


def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                resp = client.request(method, url, headers=headers, **kwargs)
            if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            return resp
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            raise exc
    if last_exc:
        raise last_exc
    raise RuntimeError("Requête Cegid échouée après retries")


class CegidQuadraConnector:
    mode = "api_quadra"

    def __init__(self, platform_row: Optional[Dict[str, Any]] = None) -> None:
        self._platform_row = platform_row

    def _auth_headers(self, creds: CegidCredentials) -> Dict[str, str]:
        """Headers d'authentification Loop (cf. Getting started)."""
        return {
            "x-apikey": creds.loop_apikey,
            "Ocp-Apim-Subscription-Key": creds.apim_subscription_key,
            "Accept": "application/json",
        }

    def _authenticated_request(
        self,
        creds: CegidCredentials,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        _validate_apikey_format(creds.loop_apikey)
        headers = self._auth_headers(creds)
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        url = f"{creds.api_base_url}{path}"
        return _request_with_retry(
            method,
            url,
            headers=headers,
            json=json_body,
            params=params,
        )

    def get_file_deposit_url(
        self, creds: CegidCredentials, filename: str
    ) -> Dict[str, Any]:
        """``GET /getFileUrlDeposit?filename=...`` → ``{depositUrl}`` ou ``{uri}``."""
        resp = self._authenticated_request(
            creds, "GET", FILE_DEPOSIT_PATH, params={"filename": filename}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Obtention URL de dépôt Cegid refusée (HTTP {resp.status_code})"
            )
        return resp.json() if resp.content else {}

    def upload_fec_to_deposit(
        self, deposit_info: Dict[str, Any], content: bytes
    ) -> None:
        """Dépose le FEC via PUT sur l'URL Azure retournée par getFileUrlDeposit."""
        upload_url = str(
            deposit_info.get("depositUrl")
            or deposit_info.get("url")
            or ""
        ).strip()
        if not upload_url:
            # Mode URI : pas d'URL de dépôt → l'upload Azure n'est pas applicable ici.
            raise RuntimeError("depositUrl absente dans la réponse Cegid getFileUrlDeposit")

        # PUT sur un blob Azure : header x-ms-blob-type obligatoire.
        headers = {
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": "application/octet-stream",
        }
        resp = _request_with_retry(
            "PUT",
            upload_url,
            headers=headers,
            content=content,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Upload FEC vers le stockage Cegid échoué (HTTP {resp.status_code})"
            )

    def register_fec_import(
        self,
        creds: CegidCredentials,
        deposit_info: Dict[str, Any],
    ) -> str:
        """``POST /importFEC`` → ``accountingImportRequestId``.

        On renseigne ``URI`` (Azure Storage) si disponible, sinon ``URL`` authentifiée.
        Exactement un des deux doit être fourni (cf. doc importFEC).
        """
        uri = str(deposit_info.get("uri") or "").strip()
        url = str(deposit_info.get("depositUrl") or deposit_info.get("url") or "").strip()
        payload: Dict[str, Any] = {"codeIbs": creds.code_dossier}
        if uri:
            payload["URI"] = uri
        elif url:
            payload["URL"] = url
        else:
            raise RuntimeError("Aucun URI/URL de fichier à importer côté Cegid")

        resp = self._authenticated_request(
            creds, "POST", FEC_IMPORT_PATH, json_body=payload
        )
        if resp.status_code >= 400:
            detail = resp.text[:200] if resp.content else ""
            raise RuntimeError(
                f"Import FEC Cegid refusé (HTTP {resp.status_code}) {detail}".strip()
            )
        body = resp.json() if resp.content else {}
        request_id = str(
            body.get("accountingImportRequestId")
            or body.get("importId")
            or body.get("id")
            or ""
        ).strip()
        if not request_id:
            raise RuntimeError("Import FEC Cegid : accountingImportRequestId absent")
        return request_id

    def poll_import_status(
        self, creds: CegidCredentials, request_id: str
    ) -> Tuple[str, str]:
        """``GET /getImportStatus`` → (statut_normalisé, message).

        statut_normalisé ∈ sent (en cours) | transmitted (succès) | failed (erreur)
        """
        resp = self._authenticated_request(
            creds,
            "GET",
            IMPORT_STATUS_PATH,
            params={"accountingImportRequestId": request_id},
        )
        if resp.status_code >= 400:
            return "failed", f"Statut import Cegid indisponible (HTTP {resp.status_code})"
        body = resp.json() if resp.content else {}
        raw_status = body.get("status")
        try:
            status_code = int(raw_status)
        except (TypeError, ValueError):
            status_code = None

        if status_code == CEGID_STATUS_SUCCESS:
            return "transmitted", "Écritures intégrées dans Cegid Loop (mode brouillard)."
        if status_code == CEGID_STATUS_ERROR:
            return "failed", "Import FEC en erreur côté Cegid Loop."
        if status_code in (CEGID_STATUS_PENDING, CEGID_STATUS_RUNNING):
            return "sent", "Import FEC en cours de traitement chez Cegid Loop."
        # Statut inattendu : on reste en cours pour re-poller plus tard.
        return "sent", "Statut d'import Cegid non reconnu — nouvelle vérification ultérieure."

    def _run_auth_test(self, creds: CegidCredentials) -> ConnectionTestResult:
        try:
            _validate_apikey_format(creds.loop_apikey)
        except ValueError as exc:
            return ConnectionTestResult(
                success=False,
                status="failed",
                message=str(exc),
            )
        try:
            resp = self._authenticated_request(
                creds,
                "GET",
                FILE_DEPOSIT_PATH,
                params={"filename": "eywai-connection-test.txt"},
            )
            if resp.status_code in (401, 403):
                return ConnectionTestResult(
                    success=False,
                    status="failed",
                    message="Identifiants Cegid refusés (clé API ou subscription key invalide).",
                )
            if resp.status_code < 400:
                return ConnectionTestResult(
                    success=True,
                    status="connected",
                    message="Connexion Cegid Loop établie (clés valides).",
                )
            return ConnectionTestResult(
                success=False,
                status="failed",
                message=f"Test Cegid Loop échoué (HTTP {resp.status_code}).",
            )
        except Exception as exc:
            logger.warning("Test Cegid Loop : %s", exc)
            return ConnectionTestResult(
                success=False,
                status="failed",
                message=f"Impossible de joindre Cegid Loop : {exc}",
            )

    def test_platform_connection(
        self, platform_row: Optional[Dict[str, Any]]
    ) -> ConnectionTestResult:
        creds = parse_platform_cegid_auth(platform_row)
        if not creds:
            return ConnectionTestResult(
                success=False,
                status="not_configured",
                message="Clés comptables Cegid non configurées au niveau plateforme.",
            )
        return self._run_auth_test(creds)

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        if not config.get("enabled"):
            return ConnectionTestResult(
                success=False,
                status="not_configured",
                message="Intégration non activée pour cette entreprise.",
            )
        creds = parse_cegid_credentials(config, self._platform_row)
        if not creds:
            auth_source = resolve_cegid_auth_source(config, self._platform_row)
            if auth_source == "dedicated":
                msg = "Credentials Cegid dédiés incomplets (APIKey, subscription key, code dossier)."
            elif has_platform_cegid_auth_keys(self._platform_row):
                msg = "Code dossier Cegid manquant pour cette filiale."
            else:
                msg = "Credentials Cegid incomplets (clés comptables ou code dossier)."
            return ConnectionTestResult(
                success=False,
                status="not_configured",
                message=msg,
            )
        return self._run_auth_test(creds)

    def _pick_fec_file(
        self, files: List[tuple[str, bytes]]
    ) -> Optional[tuple[str, bytes]]:
        for name, content in files:
            lower = name.lower()
            if "fec" in lower or lower.endswith(".txt"):
                return name, content
        return files[0] if files else None

    def submit_files(
        self,
        config: Dict[str, Any],
        files: List[tuple[str, bytes]],
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        creds = parse_cegid_credentials(config, self._platform_row)
        if not creds:
            return TransmissionResult(
                success=False,
                status="manual",
                message="Credentials Cegid absents — repli manuel.",
            )
        fec = self._pick_fec_file(files)
        if not fec:
            return TransmissionResult(
                success=False,
                status="failed",
                message="Aucun fichier FEC à transmettre.",
            )
        filename, content = fec
        # Cegid attend une extension .txt/.tra/.csv ; on normalise en .txt si besoin.
        if not filename.lower().endswith((".txt", ".tra", ".csv")):
            filename = f"{filename.rsplit('.', 1)[0]}.txt"
        try:
            deposit_info = self.get_file_deposit_url(creds, filename)
            self.upload_fec_to_deposit(deposit_info, content)
            request_id = self.register_fec_import(creds, deposit_info)
            return TransmissionResult(
                success=True,
                status="sent",
                message="Import FEC soumis à Cegid Loop — traitement asynchrone.",
                external_ref=request_id,
            )
        except Exception as exc:
            logger.exception("Transmission Cegid Loop échouée")
            return TransmissionResult(
                success=False,
                status="failed",
                message=f"Transmission Cegid Loop : {exc}",
            )
