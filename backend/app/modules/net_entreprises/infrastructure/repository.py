"""Accès Supabase pour la config Net-entreprises et le suivi des transmissions.

Utilise le client admin (service_role) car la config contient des champs sensibles
et le suivi doit pouvoir être écrit côté serveur quelle que soit la session.
Aucune exception non maîtrisée ne doit faire planter l'appelant : les lectures
renvoient None / liste vide en cas d'erreur, c'est la couche application qui décide.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.net_entreprises.repository")

CONFIG_TABLE = "company_net_entreprises_config"
TRANSMISSIONS_TABLE = "dsn_transmissions"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Configuration de connexion ---------------------------------------------


def get_config(company_id: str) -> Optional[Dict[str, Any]]:
    """Retourne la ligne de config (avec secret_ref) ou None."""
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(CONFIG_TABLE)
            .select("*")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception:
        logger.exception("Lecture config net_entreprises échouée (company=%s)", company_id)
    return None


def upsert_config(company_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Crée ou met à jour la config de connexion (1 ligne / entreprise)."""
    client = get_supabase_admin_client()
    existing = get_config(company_id)
    payload = {k: v for k, v in fields.items() if v is not None or k in fields}
    payload["updated_at"] = _now_iso()
    if existing:
        resp = (
            client.table(CONFIG_TABLE)
            .update(payload)
            .eq("company_id", company_id)
            .execute()
        )
    else:
        payload["company_id"] = company_id
        payload.setdefault("created_at", _now_iso())
        resp = client.table(CONFIG_TABLE).insert(payload).execute()
    if resp.data:
        return resp.data[0]
    return get_config(company_id)


def update_test_result(
    company_id: str, status: str, message: str
) -> None:
    """Mémorise le dernier résultat de test de connexion."""
    try:
        client = get_supabase_admin_client()
        client.table(CONFIG_TABLE).update(
            {
                "last_test_at": _now_iso(),
                "last_test_status": status,
                "last_test_message": message,
                "updated_at": _now_iso(),
            }
        ).eq("company_id", company_id).execute()
    except Exception:
        logger.exception("MAJ résultat test net_entreprises échouée (company=%s)", company_id)


# --- Suivi des transmissions -------------------------------------------------


def insert_transmission(record: Dict[str, Any]) -> Optional[str]:
    """Insère une ligne de suivi de transmission. Retourne l'id ou None."""
    try:
        client = get_supabase_admin_client()
        resp = client.table(TRANSMISSIONS_TABLE).insert(record).execute()
        if resp.data:
            return resp.data[0].get("id")
    except Exception:
        logger.exception("Insertion dsn_transmissions échouée (company=%s)", record.get("company_id"))
    return None


def update_transmission(transmission_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Met à jour une ligne de transmission."""
    client = get_supabase_admin_client()
    payload = dict(fields)
    payload["updated_at"] = _now_iso()
    resp = (
        client.table(TRANSMISSIONS_TABLE)
        .update(payload)
        .eq("id", transmission_id)
        .execute()
    )
    if resp.data:
        return resp.data[0]
    return None


def get_transmission(company_id: str, transmission_id: str) -> Optional[Dict[str, Any]]:
    """Retourne une transmission de l'entreprise ou None."""
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(TRANSMISSIONS_TABLE)
            .select("*")
            .eq("id", transmission_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
    except Exception:
        logger.exception("Lecture dsn_transmission échouée (id=%s)", transmission_id)
    return None


def list_transmissions_by_company(
    company_id: str,
    period: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Liste les transmissions d'une entreprise, plus récentes en premier."""
    try:
        client = get_supabase_admin_client()
        query = (
            client.table(TRANSMISSIONS_TABLE)
            .select("*")
            .eq("company_id", company_id)
        )
        if period:
            query = query.eq("period", period)
        resp = query.order("created_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception:
        logger.exception("Liste dsn_transmissions échouée (company=%s)", company_id)
        return []


def list_all_transmissions(
    status: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Liste toutes les transmissions (super-admin), plus récentes en premier."""
    try:
        client = get_supabase_admin_client()
        query = client.table(TRANSMISSIONS_TABLE).select("*")
        if status:
            query = query.eq("status", status)
        if period:
            query = query.eq("period", period)
        resp = query.order("created_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception:
        logger.exception("Liste globale dsn_transmissions échouée")
        return []


def list_all_configs() -> List[Dict[str, Any]]:
    """Liste toutes les configs (super-admin) — secrets exclus côté application."""
    try:
        client = get_supabase_admin_client()
        resp = client.table(CONFIG_TABLE).select("*").execute()
        return resp.data or []
    except Exception:
        logger.exception("Liste globale configs net_entreprises échouée")
        return []


def get_company_names(company_ids: List[str]) -> Dict[str, str]:
    """Retourne un mapping {company_id: company_name} pour l'affichage super-admin."""
    if not company_ids:
        return {}
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("id, company_name")
            .in_("id", list(set(company_ids)))
            .execute()
        )
        return {
            str(r["id"]): (r.get("company_name") or "")
            for r in (resp.data or [])
        }
    except Exception:
        logger.exception("Lecture noms entreprises échouée")
        return {}
