"""Persistance Supabase — generated_documents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase

BUCKET = "generated_documents"
_EMPLOYEE_VISIBLE_STATUSES = ("envoye", "signe")


def _data(resp: Any) -> Any:
    return resp.data if resp else None


def _list(resp: Any) -> List[Dict[str, Any]]:
    d = _data(resp)
    if d is None:
        return []
    return d if isinstance(d, list) else [d]


class SupabaseDocumentsRepository:
    def get_all(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        *,
        employee_visible_only: bool = False,
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("generated_documents")
            .select("*")
            .eq("company_id", company_id)
        )
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if document_type:
            q = q.eq("document_type", document_type)
        if employee_visible_only:
            q = q.in_("status", list(_EMPLOYEE_VISIBLE_STATUSES))
        elif status:
            q = q.eq("status", status)
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)
        rows = _list(q.order("created_at", desc=True).execute())
        if not rows:
            return []
        self._enrich_rows(rows)
        return rows

    def _enrich_rows(self, rows: List[Dict[str, Any]]) -> None:
        emp_ids = list({str(r["employee_id"]) for r in rows if r.get("employee_id")})
        names: Dict[str, str] = {}
        for eid in emp_ids:
            er = (
                supabase.table("employees")
                .select("id, first_name, last_name")
                .eq("id", eid)
                .maybe_single()
                .execute()
            )
            ed = _data(er)
            if ed:
                fn = (ed.get("first_name") or "").strip()
                ln = (ed.get("last_name") or "").strip()
                full = f"{fn} {ln}".strip()
                names[eid] = full if full else None
        tpl_ids = list({str(r["template_id"]) for r in rows if r.get("template_id")})
        tpl_names: Dict[str, str] = {}
        for tid in tpl_ids:
            tr = (
                supabase.table("document_templates")
                .select("id, name")
                .eq("id", tid)
                .maybe_single()
                .execute()
            )
            td = _data(tr)
            if td and td.get("name"):
                tpl_names[tid] = str(td["name"])
        for r in rows:
            eid = r.get("employee_id")
            r["employee_name"] = names.get(str(eid)) if eid else None
            tid = r.get("template_id")
            r["template_name"] = tpl_names.get(str(tid)) if tid else None

    def get_by_id(self, document_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("generated_documents")
            .select("*")
            .eq("id", document_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = _data(r)
        if not row:
            return None
        self._enrich_rows([row])
        return row

    def insert(self, row: Dict[str, Any]) -> Dict[str, Any]:
        ins = supabase.table("generated_documents").insert(row).execute()
        rows = _list(ins)
        if not rows:
            raise RuntimeError("Échec insertion generated_documents")
        self._enrich_rows(rows)
        return rows[0]

    @staticmethod
    def employee_can_access_status(status: str) -> bool:
        return str(status or "") in _EMPLOYEE_VISIBLE_STATUSES

    def update_status(self, document_id: str, company_id: str, status: str) -> Dict[str, Any]:
        upd = (
            supabase.table("generated_documents")
            .update({"status": status})
            .eq("id", document_id)
            .eq("company_id", company_id)
            .execute()
        )
        rows = _list(upd)
        if not rows:
            raise LookupError("Document non trouvé ou non mis à jour")
        self._enrich_rows(rows)
        return rows[0]

    def delete(self, document_id: str, company_id: str) -> None:
        r = (
            supabase.table("generated_documents")
            .select("id, status")
            .eq("id", document_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = _data(r)
        if not row:
            raise LookupError("Document introuvable")
        if str(row.get("status") or "") != "brouillon":
            raise ValueError("Suppression réservée aux documents au statut « brouillon ».")
        supabase.table("generated_documents").delete().eq("id", document_id).eq(
            "company_id", company_id
        ).execute()

    def create_signed_download_url(self, storage_path: str, expires: int = 3600) -> str:
        return self._create_signed_url(storage_path, expires, download=True)

    def create_signed_preview_url(self, storage_path: str, expires: int = 3600) -> str:
        return self._create_signed_url(storage_path, expires, download=False)

    @staticmethod
    def _create_signed_url(storage_path: str, expires: int, *, download: bool) -> str:
        sur = supabase.storage.from_(BUCKET).create_signed_url(
            storage_path, expires, options={"download": download}
        )
        if isinstance(sur, dict):
            u = sur.get("signedURL") or sur.get("signedUrl")
            if u:
                return str(u)
        raise RuntimeError("URL signée indisponible")


documents_repository = SupabaseDocumentsRepository()
