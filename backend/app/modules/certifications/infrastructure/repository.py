"""
Repository Supabase certifications (référentiel + habilitations collaborateurs).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, cast

from app.core.database import supabase

from app.modules.certifications.domain.interfaces import AbstractCertificationRepository


def _parse_expiry_value(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def compute_computed_status(
    expiry_date: Optional[date], alert_days: int
) -> str:
    """valid | expiring_soon | expired | no_expiry (règle ticket)."""
    if expiry_date is None:
        return "no_expiry"
    today = date.today()
    if expiry_date < today:
        return "expired"
    from datetime import timedelta

    threshold = today + timedelta(days=int(alert_days or 60))
    if expiry_date <= threshold:
        return "expiring_soon"
    return "valid"


class SupabaseCertificationRepository(AbstractCertificationRepository):
    """Accès DB tables certification_referential et employee_certifications."""

    def get_all_refs(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("certification_referential")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(r.data or []) if r else []

    def get_ref_by_id(self, ref_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("certification_referential")
            .select("*")
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return cast(Optional[Dict[str, Any]], r.data if r else None)

    def create_ref(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "status": data.get("status") or "active"}
        ins = supabase.table("certification_referential").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de la création du référentiel.")
        return dict(ins.data[0])

    def update_ref(self, ref_id: str, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data:
            existing = self.get_ref_by_id(ref_id, company_id)
            if not existing:
                raise LookupError("Référentiel non trouvé.")
            return existing
        u = (
            supabase.table("certification_referential")
            .update(data)
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Référentiel non trouvé.")
        return dict(u.data[0])

    def count_active_employee_certs_for_ref(self, ref_id: str, company_id: str) -> int:
        r = (
            supabase.table("employee_certifications")
            .select("id")
            .eq("certification_id", ref_id)
            .eq("company_id", company_id)
            .eq("is_archived", False)
            .limit(1)
            .execute()
        )
        return len(r.data or []) if r else 0

    def archive_ref(self, ref_id: str, company_id: str) -> None:
        if self.count_active_employee_certs_for_ref(ref_id, company_id) > 0:
            raise ValueError(
                "Impossible d’archiver : des habilitations actives utilisent encore ce référentiel."
            )
        u = (
            supabase.table("certification_referential")
            .update({"status": "archived"})
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Référentiel non trouvé.")

    def _fetch_employees_map(
        self, company_id: str, employee_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not employee_ids:
            return {}
        r = (
            supabase.table("employees")
            .select("id,first_name,last_name")
            .eq("company_id", company_id)
            .in_("id", employee_ids)
            .execute()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for row in list(r.data or []) if r else []:
            out[str(row["id"])] = dict(row)
        return out

    def _fetch_refs_map(self, company_id: str, ref_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not ref_ids:
            return {}
        r = (
            supabase.table("certification_referential")
            .select("*")
            .eq("company_id", company_id)
            .in_("id", ref_ids)
            .execute()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for row in list(r.data or []) if r else []:
            out[str(row["id"])] = dict(row)
        return out

    def get_all_employee_certs(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("employee_certifications")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
        )
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if not include_archived:
            q = q.eq("is_archived", False)
        r = q.execute()
        rows = list(r.data or []) if r else []
        if not rows:
            return []

        emp_ids = list({str(row["employee_id"]) for row in rows})
        ref_ids = list({str(row["certification_id"]) for row in rows})
        emps = self._fetch_employees_map(company_id, emp_ids)
        refs = self._fetch_refs_map(company_id, ref_ids)

        enriched: List[Dict[str, Any]] = []
        for row in rows:
            eid = str(row["employee_id"])
            rid = str(row["certification_id"])
            emp = emps.get(eid) or {}
            ref_row = refs.get(rid)
            name_parts = [emp.get("first_name") or "", emp.get("last_name") or ""]
            employee_name = " ".join(p for p in name_parts if p).strip() or None
            d = dict(row)
            d["_employee_name"] = employee_name
            d["_certification_ref_row"] = ref_row
            enriched.append(d)
        return enriched

    def get_employee_cert_by_id(
        self, cert_row_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_certifications")
            .select("*")
            .eq("id", cert_row_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = r.data if r else None
        if not row:
            return None
        row = dict(row)
        eid = str(row["employee_id"])
        ref_id = str(row["certification_id"])
        emps = self._fetch_employees_map(company_id, [eid])
        refs = self._fetch_refs_map(company_id, [ref_id])
        emp = emps.get(eid) or {}
        name_parts = [emp.get("first_name") or "", emp.get("last_name") or ""]
        employee_name = " ".join(p for p in name_parts if p).strip() or None
        d = dict(row)
        d["_employee_name"] = employee_name
        d["_certification_ref_row"] = refs.get(ref_id)
        return d

    def create_employee_cert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        ins = supabase.table("employee_certifications").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de la création de l’habilitation.")
        new_id = str(ins.data[0]["id"])
        got = self.get_employee_cert_by_id(new_id, company_id)
        if not got:
            raise RuntimeError("Erreur lors du rechargement de l’habilitation.")
        return got

    def update_employee_cert(
        self, cert_row_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not data:
            return self.get_employee_cert_by_id(cert_row_id, company_id) or {}
        u = (
            supabase.table("employee_certifications")
            .update(data)
            .eq("id", cert_row_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Habilitation non trouvée.")
        got = self.get_employee_cert_by_id(cert_row_id, company_id)
        if not got:
            raise LookupError("Habilitation non trouvée.")
        return got

    def archive_employee_cert(self, cert_row_id: str, company_id: str) -> None:
        u = (
            supabase.table("employee_certifications")
            .update({"is_archived": True})
            .eq("id", cert_row_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Habilitation non trouvée.")

    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        r = (
            supabase.table("employees")
            .select("id")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not r.data:
            return None
        return str(r.data["id"])

    def get_expiring_count(self, company_id: str) -> int:
        rows = self.get_all_employee_certs(company_id, None, False)
        n = 0
        for row in rows:
            ref = row.get("_certification_ref_row") or {}
            alert = int(ref.get("alert_days") or 60)
            exp = _parse_expiry_value(row.get("expiry_date"))
            if compute_computed_status(exp, alert) == "expiring_soon":
                n += 1
        return n

    def get_expired_count(self, company_id: str) -> int:
        rows = self.get_all_employee_certs(company_id, None, False)
        n = 0
        for row in rows:
            ref = row.get("_certification_ref_row") or {}
            alert = int(ref.get("alert_days") or 60)
            exp = _parse_expiry_value(row.get("expiry_date"))
            if compute_computed_status(exp, alert) == "expired":
                n += 1
        return n


certification_repository: AbstractCertificationRepository = SupabaseCertificationRepository()
