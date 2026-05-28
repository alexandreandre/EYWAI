"""
Repository Supabase compétences (competency_referential, employee_competencies).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase

from app.modules.competencies.domain.interfaces import AbstractCompetenciesRepository


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _is_active_employee_row(row: Dict[str, Any]) -> bool:
    st = row.get("employment_status")
    if st is None:
        return True
    if st in ("parti", "en_sortie"):
        return False
    return st == "actif"


def _emp_name(row: Dict[str, Any]) -> str:
    fn = str(row.get("first_name") or "").strip()
    ln = str(row.get("last_name") or "").strip()
    return f"{fn} {ln}".strip() or "Collaborateur"


def _gap(score: int, required: Optional[int]) -> bool:
    if required is None:
        return False
    return score < int(required)


class SupabaseCompetenciesRepository(AbstractCompetenciesRepository):
    """Implémentation Supabase."""

    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        from app.modules.employees.infrastructure.queries import (
            resolve_employee_id_for_user_account,
        )

        return resolve_employee_id_for_user_account(user_id, company_id)

    def get_employee_row(self, employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, company_id")
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return dict(r.data) if r and r.data else None

    def get_employee_profile_for_mobility(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select(
                "id, company_id, first_name, last_name, job_title, employment_status"
            )
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return dict(r.data) if r and r.data else None

    def list_active_job_titles(self, company_id: str, *, limit: int = 20) -> List[str]:
        jr = (
            supabase.table("employees")
            .select("job_title")
            .eq("company_id", company_id)
            .eq("employment_status", "actif")
            .limit(200)
            .execute()
        )
        titles: List[str] = []
        for row in list(jr.data or []):
            jt = (row.get("job_title") or "").strip()
            if jt and jt not in titles:
                titles.append(jt)
            if len(titles) >= limit:
                break
        return titles

    def get_all_refs(self, company_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
        q = supabase.table("competency_referential").select("*").eq("company_id", company_id)
        if not include_archived:
            q = q.neq("status", "archived")
        q = q.order("name")
        r = q.execute()
        return [dict(x) for x in list(r.data or []) if r]

    def get_ref_by_id(self, ref_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("competency_referential")
            .select("*")
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return dict(r.data) if r and r.data else None

    def create_ref(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "status": data.get("status") or "active"}
        ins = supabase.table("competency_referential").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de la création de la compétence.")
        return dict(ins.data[0])

    def update_ref(self, ref_id: str, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data:
            row = self.get_ref_by_id(ref_id, company_id)
            if not row:
                raise LookupError("Compétence non trouvée.")
            return row
        u = (
            supabase.table("competency_referential")
            .update(data)
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Compétence non trouvée.")
        return dict(u.data[0])

    def archive_ref(self, ref_id: str, company_id: str) -> None:
        u = (
            supabase.table("competency_referential")
            .update({"status": "archived"})
            .eq("id", ref_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Compétence non trouvée.")

    def count_evaluations_for_competency(self, competency_id: str, company_id: str) -> int:
        r = (
            supabase.table("employee_competencies")
            .select("id")
            .eq("competency_id", competency_id)
            .eq("company_id", company_id)
            .execute()
        )
        return len(list(r.data or [])) if r else 0

    def _fetch_refs_map(self, company_id: str, ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not ids:
            return {}
        r = (
            supabase.table("competency_referential")
            .select("*")
            .eq("company_id", company_id)
            .in_("id", ids)
            .execute()
        )
        return {str(x["id"]): dict(x) for x in list(r.data or []) if r}

    def _fetch_employees_map(
        self, company_id: str, employee_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not employee_ids:
            return {}
        r = (
            supabase.table("employees")
            .select("id, first_name, last_name, employment_status")
            .eq("company_id", company_id)
            .in_("id", employee_ids)
            .execute()
        )
        return {str(x["id"]): dict(x) for x in list(r.data or []) if r}

    def get_all_evaluations(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        competency_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("employee_competencies").select("*").eq("company_id", company_id)
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if competency_id:
            q = q.eq("competency_id", competency_id)
        q = q.order("evaluation_date", desc=True).order("created_at", desc=True)
        r = q.execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        if not rows:
            return []
        cids = list({str(x["competency_id"]) for x in rows})
        eids = list({str(x["employee_id"]) for x in rows})
        c_map = self._fetch_refs_map(company_id, cids)
        e_map = self._fetch_employees_map(company_id, eids)
        out: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            cid = str(row["competency_id"])
            eid = str(row["employee_id"])
            cref = c_map.get(cid, {})
            emp = e_map.get(eid, {})
            req = cref.get("required_level")
            if req is not None:
                req = int(req)
            sc = int(row.get("score") or 0)
            d["_competency_name"] = cref.get("name")
            d["_competency_category"] = cref.get("category")
            d["_required_level"] = req
            d["_employee_name"] = _emp_name(emp) if emp else None
            d["_is_gap"] = _gap(sc, req)
            out.append(d)
        return out

    def get_evaluation_by_id(
        self, evaluation_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_competencies")
            .select("*")
            .eq("id", evaluation_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None
        row = dict(r.data)
        cid = str(row["competency_id"])
        eid = str(row["employee_id"])
        c_map = self._fetch_refs_map(company_id, [cid])
        e_map = self._fetch_employees_map(company_id, [eid])
        cref = c_map.get(cid, {})
        emp = e_map.get(eid, {})
        req = cref.get("required_level")
        if req is not None:
            req = int(req)
        sc = int(row.get("score") or 0)
        row["_competency_name"] = cref.get("name")
        row["_competency_category"] = cref.get("category")
        row["_required_level"] = req
        row["_employee_name"] = _emp_name(emp) if emp else None
        row["_is_gap"] = _gap(sc, req)
        return row

    def insert_evaluation(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        ins = supabase.table("employee_competencies").insert(payload).execute()
        if not ins.data:
            raise RuntimeError("Erreur lors de l'enregistrement de l'évaluation.")
        new_id = str(ins.data[0]["id"])
        got = self.get_evaluation_by_id(new_id, company_id)
        if not got:
            raise RuntimeError("Erreur lors du rechargement.")
        return got

    def get_latest_evaluations(
        self, company_id: str, employee_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        all_rows = self.get_all_evaluations(company_id, employee_id=employee_id)
        best: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in all_rows:
            key = (str(row["employee_id"]), str(row["competency_id"]))
            ed = _parse_date(row.get("evaluation_date"))
            cur = best.get(key)
            if cur is None:
                best[key] = row
                continue
            cur_ed = _parse_date(cur.get("evaluation_date"))
            if ed and cur_ed:
                if ed > cur_ed:
                    best[key] = row
                elif ed == cur_ed:
                    c0 = _parse_dt(row.get("created_at"))
                    c1 = _parse_dt(cur.get("created_at"))
                    if c0 and c1 and c0 > c1:
                        best[key] = row
            elif ed and not cur_ed:
                best[key] = row
        return list(best.values())

    def _active_employees(
        self, company_id: str, service_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("employees")
            .select("id, first_name, last_name, employment_status, service_id")
            .eq("company_id", company_id)
        )
        if service_id:
            q = q.eq("service_id", service_id)
        r = q.order("last_name").execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        return [row for row in rows if _is_active_employee_row(row)]

    def get_matrix_payload(
        self,
        company_id: str,
        service_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        employees = self._active_employees(company_id, service_id)
        comps = self.get_all_refs(company_id, include_archived=False)
        if category:
            comps = [c for c in comps if str(c.get("category") or "") == category]
        emp_list = [{"id": str(e["id"]), "name": _emp_name(e)} for e in employees]
        comp_list = [
            {
                "id": str(c["id"]),
                "name": str(c.get("name") or ""),
                "category": str(c.get("category") or ""),
                "required_level": int(c["required_level"])
                if c.get("required_level") is not None
                else None,
            }
            for c in comps
        ]
        latest = self.get_latest_evaluations(company_id)
        latest_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in latest:
            latest_map[(str(row["employee_id"]), str(row["competency_id"]))] = row

        cells: List[Dict[str, Any]] = []
        gaps: List[Dict[str, Any]] = []
        for e in employees:
            eid = str(e["id"])
            ename = _emp_name(e)
            for c in comps:
                cid = str(c["id"])
                cname = str(c.get("name") or "")
                req = c.get("required_level")
                if req is not None:
                    req = int(req)
                row = latest_map.get((eid, cid))
                score = int(row.get("score", 0)) if row else 0
                is_g = _gap(score, req)
                cell = {
                    "employee_id": eid,
                    "employee_name": ename,
                    "competency_id": cid,
                    "competency_name": cname,
                    "score": score,
                    "required_level": req,
                    "is_gap": is_g,
                }
                cells.append(cell)
                if is_g:
                    gaps.append(dict(cell))
        return {
            "employees": emp_list,
            "competencies": comp_list,
            "cells": cells,
            "gaps": gaps,
        }

    def get_trainings_by_competency_ids(
        self, company_id: str, competency_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not competency_ids:
            return {}
        r = (
            supabase.table("training_catalog")
            .select("id, title, competency_id, status")
            .eq("company_id", company_id)
            .in_("competency_id", competency_ids)
            .neq("status", "archived")
            .execute()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for row in list(r.data or []) if r else []:
            cid = str(row.get("competency_id") or "")
            if cid and cid not in out:
                out[cid] = dict(row)
        return out


competencies_repository: AbstractCompetenciesRepository = SupabaseCompetenciesRepository()
