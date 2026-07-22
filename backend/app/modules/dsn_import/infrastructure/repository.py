"""Persistance Supabase pour l'import DSN."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.dsn_import.domain.normalize import nir_match_key

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


def _is_transient_db_error(exc: Exception) -> bool:
    raw = str(exc)
    return any(
        token in raw
        for token in ("SSL", "BAD_RECORD_MAC", "ReadError", "Connection reset")
    )


def insert_batch(record: Dict[str, Any]) -> Optional[str]:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            client = get_supabase_admin_client()
            resp = client.table(BATCHES_TABLE).insert(record).execute()
            if resp.data:
                return str(resp.data[0]["id"])
        except Exception as exc:
            last_exc = exc
            if attempt < 2 and _is_transient_db_error(exc):
                time.sleep(0.5 * (attempt + 1))
                continue
            logger.exception("Insertion dsn_import_batches échouée")
            return None
    if last_exc:
        logger.exception("Insertion dsn_import_batches échouée après retries")
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
                "paie_occurrence, paie_jour_de_fin, taux_at_mp, group_id, is_active"
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
    client = get_supabase_admin_client()

    def _insert(rows: List[Dict[str, Any]]) -> int:
        resp = client.table(ITEMS_TABLE).insert(rows).execute()
        return len(resp.data or [])

    try:
        return _insert(items)
    except Exception:
        logger.exception("Insertion dsn_import_items échouée")
        deferred_types = {"absence", "exit"}
        filtered = [row for row in items if row.get("item_type") not in deferred_types]
        if len(filtered) == len(items):
            return 0
        skipped = len(items) - len(filtered)
        logger.warning(
            "Retry insertion dsn_import_items sans absence/exit (%d items ignorés)",
            skipped,
        )
        try:
            return _insert(filtered)
        except Exception:
            logger.exception("Insertion dsn_import_items (sans absence/exit) échouée")
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


def _find_employee_by_nir_key(
    client: Any, nir: str, *, company_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Repli tolérant à la clé NIR : la DSN émet souvent 13 chiffres, la base 15.

    On rapproche sur les 13 premiers caractères (clé de contrôle mise à part) via un
    préfixe SQL, puis on vérifie chaque candidat avec ``nir_match_key`` (les 13 premiers
    caractères identifient de façon unique une personne).
    """
    key = nir_match_key(nir)
    if not key:
        return None
    query = client.table("employees").select("*").ilike("nir", f"{key}%")
    if company_id:
        query = query.eq("company_id", company_id)
    resp = query.limit(5).execute()
    for row in resp.data or []:
        if nir_match_key(row.get("nir")) == key:
            return row
    return None


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
        if resp.data:
            return resp.data[0]
        return _find_employee_by_nir_key(client, nir, company_id=company_id)
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
        if resp.data:
            return resp.data[0]
        return _find_employee_by_nir_key(client, nir)
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


def list_dsn_placeholder_employees(company_id: str) -> List[Dict[str, Any]]:
    """Salariés créés via import DSN (email *.dsn-import.local), sans compte activé."""
    if not company_id:
        return []
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("id, first_name, last_name, nir, user_id, email, employment_status")
            .eq("company_id", company_id)
            .is_("user_id", "null")
            .like("email", "%.dsn-import.local")
            .order("last_name")
            .execute()
        )
        return [dict(row) for row in (resp.data or [])]
    except Exception:
        logger.exception("Liste salariés placeholder DSN échouée pour %s", company_id)
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


REVOCATIONS_TABLE = "dsn_import_period_revocations"


def list_employees_with_folder(company_id: str) -> List[Dict[str, Any]]:
    """Salariés de l'entreprise disposant d'un dossier paie sur disque."""
    if not company_id:
        return []
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table("employees")
            .select("id, employee_folder_name")
            .eq("company_id", company_id)
            .not_.is_("employee_folder_name", "null")
            .neq("employee_folder_name", "")
            .execute()
        )
        return [dict(row) for row in (resp.data or [])]
    except Exception:
        logger.exception("Liste salariés avec dossier paie échouée pour %s", company_id)
        return []


def list_revoked_periods(company_id: str) -> List[str]:
    if not company_id:
        return []
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(REVOCATIONS_TABLE)
            .select("period")
            .eq("company_id", company_id)
            .execute()
        )
        return sorted(str(row["period"]) for row in (resp.data or []) if row.get("period"))
    except Exception:
        logger.exception("Liste révocations DSN échouée pour %s", company_id)
        return []


def list_revoked_periods_by_company(company_ids: List[str]) -> Dict[str, List[str]]:
    if not company_ids:
        return {}
    try:
        client = get_supabase_admin_client()
        resp = (
            client.table(REVOCATIONS_TABLE)
            .select("company_id, period")
            .in_("company_id", company_ids)
            .execute()
        )
        out: Dict[str, List[str]] = {}
        for row in resp.data or []:
            cid = str(row.get("company_id") or "")
            period = row.get("period")
            if cid and period:
                out.setdefault(cid, []).append(str(period))
        for cid in out:
            out[cid] = sorted(set(out[cid]))
        return out
    except Exception:
        logger.exception("Liste révocations DSN par entreprise échouée")
        return {}


def upsert_period_revocation(
    company_id: str,
    period: str,
    *,
    revoked_by: Optional[str] = None,
) -> None:
    client = get_supabase_admin_client()
    payload: Dict[str, Any] = {
        "company_id": company_id,
        "period": period,
        "revoked_at": _now_iso(),
    }
    if revoked_by:
        payload["revoked_by"] = revoked_by
    client.table(REVOCATIONS_TABLE).upsert(
        payload,
        on_conflict="company_id,period",
    ).execute()


def clear_period_revocations(company_id: str, periods: List[str]) -> None:
    if not company_id or not periods:
        return
    try:
        client = get_supabase_admin_client()
        client.table(REVOCATIONS_TABLE).delete().eq("company_id", company_id).in_(
            "period", periods
        ).execute()
    except Exception:
        logger.exception(
            "Suppression révocations DSN échouée pour %s périodes %s",
            company_id,
            periods,
        )
