"""Accès Supabase — bibliothèque document_templates / document_template_versions."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.document_library.schemas.requests import (
    DOCUMENT_TYPE_LABELS,
    KNOWN_DOCUMENT_TYPES,
    DocumentTemplateCreate,
    DocumentTemplateUpdate,
)

BUCKET = "document_templates"


def _data(resp: Any) -> Any:
    return resp.data if resp else None


def _list(resp: Any) -> List[Dict[str, Any]]:
    d = _data(resp)
    if d is None:
        return []
    return d if isinstance(d, list) else [d]


def _sanitize_filename(name: str) -> str:
    base = name.strip().replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^\w.\-() ]+", "_", base, flags=re.UNICODE)
    return base or "fichier"


class SupabaseDocumentLibraryRepository:
    def get_all(
        self, company_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("document_templates")
            .select("*")
            .eq("company_id", company_id)
            .order("updated_at", desc=True)
        )
        if status:
            q = q.eq("status", status)
        rows = _list(q.execute())
        if not rows:
            return []
        ids = [str(r["id"]) for r in rows]
        v_rows = _list(
            supabase.table("document_template_versions")
            .select("*")
            .in_("template_id", ids)
            .order("version", desc=True)
            .execute()
        )
        by_tid: Dict[str, List[Dict[str, Any]]] = {}
        for vr in v_rows:
            tid = str(vr["template_id"])
            by_tid.setdefault(tid, []).append(vr)
        for tid in by_tid:
            by_tid[tid].sort(key=lambda x: int(x.get("version") or 0), reverse=True)
        out: List[Dict[str, Any]] = []
        for row in rows:
            tid = str(row["id"])
            versions = by_tid.get(tid, [])
            current = versions[0] if versions else None
            enriched = dict(row)
            enriched["current_version"] = current
            enriched["versions_count"] = len(versions)
            out.append(enriched)
        return out

    def get_by_id(self, template_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("document_templates")
            .select("*")
            .eq("id", template_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = _data(r)
        if not row:
            return None
        v_rows = _list(
            supabase.table("document_template_versions")
            .select("*")
            .eq("template_id", template_id)
            .order("version", desc=True)
            .execute()
        )
        current = v_rows[0] if v_rows else None
        out = dict(row)
        out["current_version"] = current
        out["versions_count"] = len(v_rows)
        return out

    def _clear_default_for_type(
        self, company_id: str, document_type: str, exclude_id: Optional[str] = None
    ) -> None:
        q = (
            supabase.table("document_templates")
            .update({"is_default": False})
            .eq("company_id", company_id)
            .eq("document_type", document_type)
            .eq("status", "active")
        )
        if exclude_id:
            q = q.neq("id", exclude_id)
        q.execute()

    def create(
        self, company_id: str, data: DocumentTemplateCreate, created_by: Optional[str]
    ) -> Dict[str, Any]:
        dtype = data.document_type.strip()
        if dtype not in KNOWN_DOCUMENT_TYPES:
            raise ValueError(f"Type de document inconnu : {dtype}")
        name = (data.name or "").strip() or DOCUMENT_TYPE_LABELS.get(dtype, dtype)
        insert_payload: Dict[str, Any] = {
            "company_id": company_id,
            "document_type": dtype,
            "name": name,
            "is_default": False,
            "status": "active",
            "created_by": created_by,
        }
        ins = supabase.table("document_templates").insert(insert_payload).execute()
        created = _list(ins)
        if not created:
            raise RuntimeError("Création du modèle impossible")
        row = created[0]
        out = dict(row)
        out["current_version"] = None
        out["versions_count"] = 0
        return out

    def update(
        self, template_id: str, company_id: str, data: DocumentTemplateUpdate
    ) -> Dict[str, Any]:
        existing = self.get_by_id(template_id, company_id)
        if not existing:
            raise LookupError("Modèle introuvable")
        payload: Dict[str, Any] = {}
        if data.name is not None:
            payload["name"] = data.name.strip() or existing["name"]
        if data.status is not None:
            payload["status"] = data.status
        if data.is_default is True:
            self._clear_default_for_type(
                company_id, str(existing["document_type"]), exclude_id=template_id
            )
            payload["is_default"] = True
        elif data.is_default is False:
            payload["is_default"] = False
        if not payload:
            return existing
        supabase.table("document_templates").update(payload).eq(
            "id", template_id
        ).eq("company_id", company_id).execute()
        refreshed = self.get_by_id(template_id, company_id)
        if not refreshed:
            raise LookupError("Modèle introuvable après mise à jour")
        return refreshed

    def _has_active_generated_documents(self, template_id: str) -> bool:
        r = (
            supabase.table("generated_documents")
            .select("id")
            .eq("template_id", template_id)
            .in_("status", ["brouillon", "envoye", "signe"])
            .limit(1)
            .execute()
        )
        return bool(_list(r))

    def archive(self, template_id: str, company_id: str) -> Dict[str, Any]:
        existing = self.get_by_id(template_id, company_id)
        if not existing:
            raise LookupError("Modèle introuvable")
        if self._has_active_generated_documents(template_id):
            raise ValueError(
                "Impossible d'archiver : des documents générés actifs "
                "référencent encore ce modèle."
            )
        supabase.table("document_templates").update({"status": "archived"}).eq(
            "id", template_id
        ).eq("company_id", company_id).execute()
        refreshed = self.get_by_id(template_id, company_id)
        if not refreshed:
            raise LookupError("Modèle introuvable après archivage")
        return refreshed

    def max_version(self, template_id: str) -> int:
        r = (
            supabase.table("document_template_versions")
            .select("version")
            .eq("template_id", template_id)
            .order("version", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        row = _data(r)
        if not row:
            return 0
        return int(row.get("version") or 0)

    def add_version(
        self,
        template_id: str,
        file_url: str,
        file_name: str,
        file_format: str,
        file_size: Optional[int],
        uploaded_by: Optional[str],
    ) -> Dict[str, Any]:
        next_v = self.max_version(template_id) + 1
        ins = (
            supabase.table("document_template_versions")
            .insert(
                {
                    "template_id": template_id,
                    "version": next_v,
                    "file_url": file_url,
                    "file_name": file_name,
                    "file_format": file_format,
                    "file_size": file_size,
                    "uploaded_by": uploaded_by,
                }
            )
            .execute()
        )
        created = _list(ins)
        if not created:
            raise RuntimeError("Enregistrement de version impossible")
        return created[0]

    def get_versions(self, template_id: str, company_id: str) -> List[Dict[str, Any]]:
        tpl = self.get_by_id(template_id, company_id)
        if not tpl:
            raise LookupError("Modèle introuvable")
        return _list(
            supabase.table("document_template_versions")
            .select("*")
            .eq("template_id", template_id)
            .order("version", desc=True)
            .execute()
        )

    def get_version_row(
        self, template_id: str, version_id: str, company_id: str
    ) -> Dict[str, Any]:
        tpl = self.get_by_id(template_id, company_id)
        if not tpl:
            raise LookupError("Modèle introuvable")
        r = (
            supabase.table("document_template_versions")
            .select("*")
            .eq("id", version_id)
            .eq("template_id", template_id)
            .maybe_single()
            .execute()
        )
        row = _data(r)
        if not row:
            raise LookupError("Version introuvable")
        return row

    def upload_template_file(
        self,
        company_id: str,
        template_id: str,
        version: int,
        file_bytes: bytes,
        file_name: str,
        file_format: str,
    ) -> str:
        safe = _sanitize_filename(file_name)
        path = f"{company_id}/{template_id}/v{version}/{safe}"
        ctype = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if file_format == "docx"
            else "text/html"
        )
        supabase.storage.from_(BUCKET).upload(
            path,
            file_bytes,
            file_options={"content-type": ctype, "x-upsert": "true"},
        )
        return path

    def create_signed_download_url(self, file_url: str, expires: int = 3600) -> str:
        r = supabase.storage.from_(BUCKET).create_signed_url(
            file_url, expires, options={"download": True}
        )
        if isinstance(r, dict):
            u = r.get("signedURL") or r.get("signedUrl")
            if u:
                return str(u)
        raise RuntimeError("URL signée indisponible")


document_library_repository = SupabaseDocumentLibraryRepository()
