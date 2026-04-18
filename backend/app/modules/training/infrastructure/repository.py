"""
Repository Supabase catalogue formations (training_catalog, training_enrollments).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.training.domain.interfaces import AbstractTrainingRepository


def _categories_from_db(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return [str(x) for x in parsed] if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _categories_to_db(cats: List[str]) -> List[str]:
    return list(cats)


def _parse_year_from_row(row: Dict[str, Any]) -> Optional[int]:
    for key in ("planned_date", "completion_date", "created_at"):
        v = row.get(key)
        if not v:
            continue
        if isinstance(v, datetime):
            return v.year
        if isinstance(v, date):
            return v.year
        s = str(v)[:10]
        try:
            return date.fromisoformat(s).year
        except ValueError:
            continue
    return None


class SupabaseTrainingRepository(AbstractTrainingRepository):
    """Implémentation Supabase."""

    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        r = (
            supabase.table("employees")
            .select("id")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return str(r.data["id"]) if r and r.data else None

    def _fetch_cert_map(
        self, company_id: str, cert_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not cert_ids:
            return {}
        r = (
            supabase.table("certification_referential")
            .select("*")
            .eq("company_id", company_id)
            .in_("id", cert_ids)
            .execute()
        )
        return {str(row["id"]): dict(row) for row in list(r.data or []) if r}

    def _enrollment_year(self, row: Dict[str, Any]) -> Optional[int]:
        return _parse_year_from_row(row)

    def get_all_trainings(
        self, company_id: str, include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        q = supabase.table("training_catalog").select("*").eq("company_id", company_id)
        if not include_archived:
            q = q.neq("status", "archived")
        q = q.order("created_at", desc=True)
        r = q.execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        if not rows:
            return []

        tids = [str(x["id"]) for x in rows]
        cert_ids = list({str(x["certification_id"]) for x in rows if x.get("certification_id")})
        cert_map = self._fetch_cert_map(company_id, cert_ids)

        counts: Dict[str, int] = {tid: 0 for tid in tids}
        er = (
            supabase.table("training_enrollments")
            .select("training_id,status")
            .eq("company_id", company_id)
            .in_("training_id", tids)
            .execute()
        )
        for e in list(er.data or []) if er else []:
            tid = str(e["training_id"])
            st = str(e.get("status") or "")
            if st != "cancelled" and tid in counts:
                counts[tid] += 1

        out: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            d["categories"] = _categories_from_db(row.get("categories"))
            cid = row.get("certification_id")
            d["_certification_ref"] = cert_map.get(str(cid)) if cid else None
            d["_enrolled_count"] = counts.get(str(row["id"]), 0)
            out.append(d)
        return out

    def get_training_by_id(self, training_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("training_catalog")
            .select("*")
            .eq("id", training_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not r.data:
            return None
        row = dict(r.data)
        row["categories"] = _categories_from_db(row.get("categories"))
        cid = row.get("certification_id")
        cert_map = self._fetch_cert_map(company_id, [str(cid)] if cid else [])
        row["_certification_ref"] = cert_map.get(str(cid)) if cid else None
        tid = str(row["id"])
        er = (
            supabase.table("training_enrollments")
            .select("id")
            .eq("training_id", tid)
            .eq("company_id", company_id)
            .neq("status", "cancelled")
            .execute()
        )
        row["_enrolled_count"] = len(er.data or []) if er else 0
        return row

    def create_training(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "status": data.get("status") or "active"}
        if "categories" in payload:
            payload["categories"] = _categories_to_db(list(payload["categories"] or []))
        ins = supabase.table("training_catalog").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de la création de la formation.")
        got = self.get_training_by_id(str(ins.data[0]["id"]), company_id)
        if not got:
            raise RuntimeError("Erreur lors du rechargement.")
        return got

    def update_training(
        self, training_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not data:
            got = self.get_training_by_id(training_id, company_id)
            if not got:
                raise LookupError("Formation non trouvée.")
            return got
        payload = dict(data)
        if "categories" in payload and payload["categories"] is not None:
            payload["categories"] = _categories_to_db(list(payload["categories"]))
        u = (
            supabase.table("training_catalog")
            .update(payload)
            .eq("id", training_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Formation non trouvée.")
        got = self.get_training_by_id(training_id, company_id)
        if not got:
            raise LookupError("Formation non trouvée.")
        return got

    def count_active_enrollments_for_training(
        self, training_id: str, company_id: str
    ) -> int:
        r = (
            supabase.table("training_enrollments")
            .select("id")
            .eq("training_id", training_id)
            .eq("company_id", company_id)
            .in_("status", ("planned", "in_progress"))
            .limit(1)
            .execute()
        )
        return len(r.data or []) if r else 0

    def archive_training(self, training_id: str, company_id: str) -> None:
        if self.count_active_enrollments_for_training(training_id, company_id) > 0:
            raise ValueError(
                "Impossible d’archiver : des inscriptions actives (planifiées ou en cours) existent."
            )
        u = (
            supabase.table("training_catalog")
            .update({"status": "archived"})
            .eq("id", training_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Formation non trouvée.")

    def has_active_enrollment_duplicate(
        self, company_id: str, training_id: str, employee_id: str
    ) -> bool:
        r = (
            supabase.table("training_enrollments")
            .select("id")
            .eq("company_id", company_id)
            .eq("training_id", training_id)
            .eq("employee_id", employee_id)
            .in_("status", ("planned", "in_progress"))
            .limit(1)
            .execute()
        )
        return len(r.data or []) > 0 if r else False

    def _fetch_employee_names(self, company_id: str, emp_ids: List[str]) -> Dict[str, str]:
        if not emp_ids:
            return {}
        r = (
            supabase.table("employees")
            .select("id,first_name,last_name")
            .eq("company_id", company_id)
            .in_("id", emp_ids)
            .execute()
        )
        out: Dict[str, str] = {}
        for row in list(r.data or []) if r else []:
            fn = row.get("first_name") or ""
            ln = row.get("last_name") or ""
            out[str(row["id"])] = f"{fn} {ln}".strip() or str(row["id"])
        return out

    def _fetch_training_meta(
        self, company_id: str, training_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not training_ids:
            return {}
        r = (
            supabase.table("training_catalog")
            .select("id,title,unit_cost_ht")
            .eq("company_id", company_id)
            .in_("id", training_ids)
            .execute()
        )
        return {str(row["id"]): dict(row) for row in list(r.data or []) if r}

    def get_enrollments(
        self,
        company_id: str,
        training_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("training_enrollments").select("*").eq("company_id", company_id)
        if training_id:
            q = q.eq("training_id", training_id)
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True)
        r = q.execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        if not rows:
            return []
        eids = list({str(x["employee_id"]) for x in rows})
        tids = list({str(x["training_id"]) for x in rows})
        names = self._fetch_employee_names(company_id, eids)
        tmeta = self._fetch_training_meta(company_id, tids)
        out: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            tid = str(row["training_id"])
            eid = str(row["employee_id"])
            d["_employee_name"] = names.get(eid)
            tm = tmeta.get(tid, {})
            d["_training_title"] = tm.get("title")
            d["_unit_cost_ht"] = tm.get("unit_cost_ht")
            out.append(d)
        return out

    def get_enrollment_by_id(
        self, enrollment_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("training_enrollments")
            .select("*")
            .eq("id", enrollment_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not r.data:
            return None
        row = dict(r.data)
        eid = str(row["employee_id"])
        tid = str(row["training_id"])
        names = self._fetch_employee_names(company_id, [eid])
        tmeta = self._fetch_training_meta(company_id, [tid])
        row["_employee_name"] = names.get(eid)
        tm = tmeta.get(tid, {})
        row["_training_title"] = tm.get("title")
        row["_unit_cost_ht"] = tm.get("unit_cost_ht")
        return row

    def create_enrollment(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        ins = supabase.table("training_enrollments").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de la création de l’inscription.")
        new_id = str(ins.data[0]["id"])
        got = self.get_enrollment_by_id(new_id, company_id)
        if not got:
            raise RuntimeError("Erreur lors du rechargement.")
        return got

    def update_enrollment(
        self, enrollment_id: str, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not data:
            got = self.get_enrollment_by_id(enrollment_id, company_id)
            if not got:
                raise LookupError("Inscription non trouvée.")
            return got
        u = (
            supabase.table("training_enrollments")
            .update(data)
            .eq("id", enrollment_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Inscription non trouvée.")
        got = self.get_enrollment_by_id(enrollment_id, company_id)
        if not got:
            raise LookupError("Inscription non trouvée.")
        return got

    def cancel_enrollment(self, enrollment_id: str, company_id: str) -> None:
        u = (
            supabase.table("training_enrollments")
            .update({"status": "cancelled"})
            .eq("id", enrollment_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Inscription non trouvée.")

    def get_total_consumed(self, company_id: str, year: int) -> float:
        r = (
            supabase.table("training_enrollments")
            .select("*")
            .eq("company_id", company_id)
            .in_("status", ("planned", "completed"))
            .execute()
        )
        rows = list(r.data or []) if r else []
        if not rows:
            return 0.0
        tids = list({str(x["training_id"]) for x in rows})
        costs = self._fetch_training_meta(company_id, tids)
        total = 0.0
        for row in rows:
            y = self._enrollment_year(row)
            if y != year:
                continue
            tid = str(row["training_id"])
            cost = costs.get(tid, {}).get("unit_cost_ht")
            if cost is not None:
                total += float(cost)
        return total


training_repository: AbstractTrainingRepository = SupabaseTrainingRepository()
