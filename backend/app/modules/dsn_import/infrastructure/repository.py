"""Persistance Supabase pour l'import DSN."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.dsn_import.repository")

BATCHES_TABLE = "dsn_import_batches"
ITEMS_TABLE = "dsn_import_items"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Cache : présence des colonnes "fiche salarié" optionnelles (ajoutées par migration).
# Évite de casser l'insert si la migration d'état civil DSN n'est pas encore appliquée.
_employee_column_cache: Dict[str, bool] = {}


def employee_has_column(column: str) -> bool:
    """Indique si la colonne existe sur la table employees (résultat mis en cache)."""
    if column in _employee_column_cache:
        return _employee_column_cache[column]
    exists = True
    try:
        get_supabase_admin_client().table("employees").select(column).limit(1).execute()
    except Exception as exc:  # noqa: BLE001 — on n'attrape que l'absence de colonne
        if "42703" in str(exc) or "does not exist" in str(exc):
            exists = False
        else:
            # Erreur réseau/autre : on ne fait pas de rétention négative
            return True
    _employee_column_cache[column] = exists
    return exists


def insert_batch(record: Dict[str, Any]) -> Optional[str]:
    try:
        client = get_supabase_admin_client()
        resp = client.table(BATCHES_TABLE).insert(record).execute()
        if resp.data:
            return str(resp.data[0]["id"])
    except Exception:
        logger.exception("Insertion dsn_import_batches échouée")
    return None


def update_batch(batch_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    payload = {**fields, "updated_at": _now_iso()}
    resp = client.table(BATCHES_TABLE).update(payload).eq("id", batch_id).execute()
    return resp.data[0] if resp.data else None


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = client.table(BATCHES_TABLE).select("*").eq("id", batch_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Lecture batch %s échouée", batch_id)
        return None


def list_batches(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        q = client.table(BATCHES_TABLE).select("*").order("created_at", desc=True).limit(limit)
        if status:
            q = q.eq("status", status)
        resp = q.execute()
        return resp.data or []
    except Exception:
        logger.exception("Liste batches échouée")
        return []


def list_committed_batches(limit: int = 500) -> List[Dict[str, Any]]:
    return list_batches(limit=limit, status="committed")


def list_batches_by_statuses(statuses: List[str], limit: int = 100) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(BATCHES_TABLE)
            .select("*")
            .in_("status", statuses)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste batches par statuts échouée")
        return []


def list_companies_with_dsn_mode() -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        companies = (
            client.table("companies")
            .select(
                "id, company_name, siret, siren, dsn_sync_mode, "
                "paie_occurrence, paie_jour_de_fin, group_id, is_active"
            )
            .order("company_name")
            .execute()
        ).data or []
        groups = (
            client.table("company_groups").select("id, group_name").execute()
        ).data or []
        group_names = {str(g["id"]): g.get("group_name") for g in groups}
        out: List[Dict[str, Any]] = []
        for c in companies:
            gid = str(c["group_id"]) if c.get("group_id") else None
            row = dict(c)
            row["id"] = str(c["id"])
            row["group_name"] = group_names.get(gid) if gid else None
            out.append(row)
        return out
    except Exception:
        logger.exception("Liste entreprises dsn_sync_mode échouée")
        return []


def update_company_dsn_sync_mode(company_id: str, mode: str) -> None:
    client = get_supabase_admin_client()
    client.table("companies").update({"dsn_sync_mode": mode}).eq("id", company_id).execute()


def update_company_dsn_sync_mode_if_native(company_id: str, mode: str) -> None:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("dsn_sync_mode")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        row = (resp.data or [None])[0]
        if not row:
            return
        current = (row.get("dsn_sync_mode") or "native").strip().lower()
        if current in ("", "native", None):
            client.table("companies").update({"dsn_sync_mode": mode}).eq("id", company_id).execute()
    except Exception:
        logger.exception("MAJ conditionnelle dsn_sync_mode %s échouée", company_id)
        raise


def insert_items(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    try:
        client = get_supabase_admin_client()
        resp = client.table(ITEMS_TABLE).insert(items).execute()
        return len(resp.data or [])
    except Exception:
        logger.exception("Insertion dsn_import_items échouée")
        return 0


def list_items(batch_id: str) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(ITEMS_TABLE)
            .select("*")
            .eq("batch_id", batch_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Liste items batch %s échouée", batch_id)
        return []


def update_item(item_id: str, fields: Dict[str, Any]) -> None:
    try:
        client = get_supabase_admin_client()
        client.table(ITEMS_TABLE).update({**fields, "updated_at": _now_iso()}).eq(
            "id", item_id
        ).execute()
    except Exception:
        logger.exception("MAJ item %s échouée", item_id)


def find_group_by_siren(siren: str) -> Optional[Dict[str, Any]]:
    if not siren:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("company_groups")
            .select("*")
            .eq("siren", siren)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche groupe SIREN %s échouée", siren)
        return None


def find_company_by_siret(siret: str) -> Optional[Dict[str, Any]]:
    if not siret:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("*")
            .eq("siret", siret)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche entreprise SIRET %s échouée", siret)
        return None


def find_company_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    if not company_id:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("companies")
            .select("*")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche entreprise id %s échouée", company_id)
        return None


def list_companies_for_attribution() -> List[Dict[str, Any]]:
    """
    Liste les entreprises existantes (avec leur groupe) pour proposer le
    rattachement manuel d'un import DSN. Lecture seule, super-admin.
    """
    try:
        client = get_supabase_admin_client()
        companies = (
            client.table("companies")
            .select("id, company_name, siret, siren, group_id, is_active")
            .order("company_name")
            .execute()
        ).data or []
        groups = (
            client.table("company_groups").select("id, group_name").execute()
        ).data or []
        group_names = {str(g["id"]): g.get("group_name") for g in groups}
        out: List[Dict[str, Any]] = []
        for c in companies:
            gid = str(c["group_id"]) if c.get("group_id") else None
            out.append(
                {
                    "id": str(c["id"]),
                    "company_name": c.get("company_name") or "Entreprise",
                    "siret": c.get("siret"),
                    "siren": c.get("siren"),
                    "group_id": gid,
                    "group_name": group_names.get(gid) if gid else None,
                    "is_active": c.get("is_active", True),
                }
            )
        return out
    except Exception:
        logger.exception("Liste entreprises pour rattachement échouée")
        return []


def find_employee_by_nir(company_id: str, nir: str) -> Optional[Dict[str, Any]]:
    if not company_id or not nir:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("*")
            .eq("company_id", company_id)
            .eq("nir", nir)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche salarié NIR échouée")
        return None


def find_employee_by_nir_global(nir: str) -> Optional[Dict[str, Any]]:
    """Recherche un salarié par NIR (contrainte unique globale sur employees.nir)."""
    if not nir:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("*")
            .eq("nir", nir)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Recherche salarié NIR (global) échouée")
        return None


def list_active_employees_with_nir(company_id: str) -> List[Dict[str, Any]]:
    """Salariés actifs de l'entreprise porteurs d'un NIR (réconciliation effectifs DSN)."""
    if not company_id:
        return []
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select(
                "id, first_name, last_name, nir, employment_status, "
                "contract_end_date, hire_date"
            )
            .eq("company_id", company_id)
            .not_.is_("nir", "null")
            .neq("nir", "")
            .order("last_name")
            .execute()
        )
        active_statuses = {"actif", "active"}
        return [
            dict(row)
            for row in (resp.data or [])
            if (row.get("employment_status") or "actif").lower() in active_statuses
        ]
    except Exception:
        logger.exception("Liste salariés actifs NIR échouée pour %s", company_id)
        return []


def list_active_employees_without_nir(company_id: str) -> List[Dict[str, Any]]:
    """Salariés actifs sans NIR (hors comparaison NIR, signal informatif)."""
    if not company_id:
        return []
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("id, first_name, last_name, employment_status")
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        active_statuses = {"actif", "active"}
        out: List[Dict[str, Any]] = []
        for row in resp.data or []:
            if (row.get("employment_status") or "actif").lower() not in active_statuses:
                continue
            nir = (row.get("nir") or "").strip()
            if not nir:
                out.append(dict(row))
        return out
    except Exception:
        logger.exception("Liste salariés actifs sans NIR échouée pour %s", company_id)
        return []


def resolve_collective_agreement_id(idcc: str) -> Optional[str]:
    if not idcc:
        return None
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("collective_agreements_catalog")
            .select("id")
            .eq("idcc", idcc.strip())
            .limit(1)
            .execute()
        )
        return str(resp.data[0]["id"]) if resp.data else None
    except Exception:
        logger.exception("Recherche IDCC %s échouée", idcc)
        return None


def upsert_company_collective_agreement(company_id: str, agreement_id: str) -> None:
    try:
        client = get_supabase_admin_client()
        existing = (
            client.table("company_collective_agreements")
            .select("id")
            .eq("company_id", company_id)
            .eq("collective_agreement_id", agreement_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return
        client.table("company_collective_agreements").insert(
            {"company_id": company_id, "collective_agreement_id": agreement_id}
        ).execute()
    except Exception:
        logger.exception("Assignation CC entreprise échouée")
