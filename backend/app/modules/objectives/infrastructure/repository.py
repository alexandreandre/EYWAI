"""
Repository Supabase objectifs & KPI (employee_objectives, milestones, checkins).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.objectives.domain.interfaces import AbstractObjectivesRepository


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def _row_to_jsonable(row: Dict[str, Any]) -> Dict[str, Any]:
    """Prépare un dict pour insert/update Supabase (dates → ISO)."""
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat() if isinstance(v, datetime) else v.isoformat()
        elif isinstance(v, float):
            out[k] = v
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


class SupabaseObjectivesRepository(AbstractObjectivesRepository):
    """Implémentation Supabase."""

    def list_services(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("company_services")
            .select("*")
            .eq("company_id", company_id)
            .order("name")
            .execute()
        )
        return list(r.data or []) if r else []

    def create_service(self, company_id: str, name: str) -> Dict[str, Any]:
        ins = (
            supabase.table("company_services")
            .insert({"company_id": company_id, "name": name.strip()})
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Erreur création du service.")
        return dict(ins.data[0])

    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        from app.modules.employees.infrastructure.queries import (
            resolve_employee_id_for_user_account,
        )

        return resolve_employee_id_for_user_account(user_id, company_id)

    def get_active_employee_ids_for_service(
        self, company_id: str, service_id: str
    ) -> List[str]:
        r = (
            supabase.table("employees")
            .select("id")
            .eq("company_id", company_id)
            .eq("service_id", service_id)
            .eq("employment_status", "actif")
            .execute()
        )
        return [str(x["id"]) for x in list(r.data or []) if r]

    def _fetch_objective_row(
        self, objective_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_objectives")
            .select("*")
            .eq("id", objective_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return dict(r.data) if r and r.data else None

    def _fetch_milestones_map(self, objective_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not objective_ids:
            return {}
        r = (
            supabase.table("objective_milestones")
            .select("*")
            .in_("objective_id", objective_ids)
            .order("milestone_date")
            .execute()
        )
        out: Dict[str, List[Dict[str, Any]]] = {oid: [] for oid in objective_ids}
        for row in list(r.data or []) if r else []:
            oid = str(row["objective_id"])
            if oid in out:
                out[oid].append(dict(row))
        return out

    def _fetch_checkins_map(self, objective_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not objective_ids:
            return {}
        r = (
            supabase.table("objective_checkins")
            .select("*")
            .in_("objective_id", objective_ids)
            .order("checkin_date", desc=True)
            .execute()
        )
        out: Dict[str, List[Dict[str, Any]]] = {oid: [] for oid in objective_ids}
        for row in list(r.data or []) if r else []:
            oid = str(row["objective_id"])
            if oid in out:
                out[oid].append(dict(row))
        return out

    def _fetch_employee_names(self, company_id: str, emp_ids: List[str]) -> Dict[str, str]:
        if not emp_ids:
            return {}
        r = (
            supabase.table("employees")
            .select("id,first_name,last_name,employment_status")
            .eq("company_id", company_id)
            .in_("id", emp_ids)
            .execute()
        )
        out: Dict[str, str] = {}
        for row in list(r.data or []) if r else []:
            fn = row.get("first_name") or ""
            ln = row.get("last_name") or ""
            name = f"{fn} {ln}".strip() or str(row["id"])
            out[str(row["id"])] = name
        return out

    def _fetch_employee_status_map(self, company_id: str, emp_ids: List[str]) -> Dict[str, str]:
        if not emp_ids:
            return {}
        r = (
            supabase.table("employees")
            .select("id,employment_status")
            .eq("company_id", company_id)
            .in_("id", emp_ids)
            .execute()
        )
        return {
            str(row["id"]): str(row.get("employment_status") or "actif").lower()
            for row in list(r.data or []) if r
        }

    def _fetch_service_names(self, company_id: str, sids: List[str]) -> Dict[str, str]:
        if not sids:
            return {}
        r = (
            supabase.table("company_services")
            .select("id,name")
            .eq("company_id", company_id)
            .in_("id", sids)
            .execute()
        )
        return {str(row["id"]): str(row.get("name") or "") for row in list(r.data or []) if r}

    def _enrich_objective_row(
        self,
        row: Dict[str, Any],
        company_id: str,
        milestones_by_obj: Dict[str, List[Dict[str, Any]]],
        checkins_by_obj: Dict[str, List[Dict[str, Any]]],
        emp_names: Dict[str, str],
        svc_names: Dict[str, str],
    ) -> Dict[str, Any]:
        oid = str(row["id"])
        d = dict(row)
        eid = row.get("employee_id")
        d["_milestones"] = milestones_by_obj.get(oid, [])
        d["_checkins"] = checkins_by_obj.get(oid, [])
        d["_employee_name"] = emp_names.get(str(eid)) if eid else None
        sid = row.get("service_id")
        d["_service_name"] = svc_names.get(str(sid)) if sid else None
        return d

    def get_all(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        service_id: Optional[str] = None,
        period_year: Optional[int] = None,
        status: Optional[str] = None,
        include_inactive_employees: bool = False,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("employee_objectives").select("*").eq("company_id", company_id)
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if service_id:
            q = q.eq("service_id", service_id)
        if period_year is not None:
            q = q.eq("period_year", period_year)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True)
        r = q.execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        if not rows:
            return []

        emp_ids = list({str(x["employee_id"]) for x in rows if x.get("employee_id")})
        status_map = self._fetch_employee_status_map(company_id, emp_ids)
        if not include_inactive_employees and emp_ids:
            rows = [
                x
                for x in rows
                if not x.get("employee_id")
                or status_map.get(str(x["employee_id"]), "actif") == "actif"
            ]

        if not rows:
            return []

        oids = [str(x["id"]) for x in rows]
        ms = self._fetch_milestones_map(oids)
        cs = self._fetch_checkins_map(oids)
        emp_ids2 = list({str(x["employee_id"]) for x in rows if x.get("employee_id")})
        svc_ids = list({str(x["service_id"]) for x in rows if x.get("service_id")})
        en = self._fetch_employee_names(company_id, emp_ids2)
        sn = self._fetch_service_names(company_id, svc_ids)
        return [self._enrich_objective_row(x, company_id, ms, cs, en, sn) for x in rows]

    def get_by_id(self, objective_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetch_objective_row(objective_id, company_id)
        if not row:
            return None
        oid = str(row["id"])
        ms = self._fetch_milestones_map([oid])
        cs = self._fetch_checkins_map([oid])
        emp_ids = [str(row["employee_id"])] if row.get("employee_id") else []
        svc_ids = [str(row["service_id"])] if row.get("service_id") else []
        en = self._fetch_employee_names(company_id, emp_ids)
        sn = self._fetch_service_names(company_id, svc_ids)
        return self._enrich_objective_row(row, company_id, ms, cs, en, sn)

    def _insert_milestones(
        self, objective_id: str, milestones: List[Dict[str, Any]], updated_by: str
    ) -> None:
        for m in milestones:
            payload = {
                "objective_id": objective_id,
                "milestone_date": m["milestone_date"],
                "expected_value": m["expected_value"],
                "comment": m.get("comment"),
                "updated_by": updated_by,
            }
            ins = supabase.table("objective_milestones").insert(_row_to_jsonable(payload)).execute()
            if not ins.data:
                raise RuntimeError("Erreur création jalon.")

    def create(
        self, company_id: str, payload: Dict[str, Any], created_by: str
    ) -> Dict[str, Any]:
        milestones = list(payload.pop("_milestones", []) or [])
        row_in = {**payload, "company_id": company_id, "created_by": created_by}
        ins = (
            supabase.table("employee_objectives")
            .insert(_row_to_jsonable(row_in))
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Erreur création objectif.")
        oid = str(ins.data[0]["id"])
        if milestones:
            self._insert_milestones(oid, milestones, created_by)
        got = self.get_by_id(oid, company_id)
        if not got:
            raise RuntimeError("Erreur relecture objectif.")
        return got

    def update(
        self,
        objective_id: str,
        company_id: str,
        payload: Dict[str, Any],
        last_modified_by: str,
    ) -> Dict[str, Any]:
        if not payload:
            got = self.get_by_id(objective_id, company_id)
            if not got:
                raise LookupError("Objectif non trouvé.")
            return got
        upd = {**payload, "last_modified_by": last_modified_by}
        u = (
            supabase.table("employee_objectives")
            .update(_row_to_jsonable(upd))
            .eq("id", objective_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Objectif non trouvé.")
        got = self.get_by_id(objective_id, company_id)
        if not got:
            raise LookupError("Objectif non trouvé.")
        return got

    def cancel(self, objective_id: str, company_id: str) -> None:
        u = (
            supabase.table("employee_objectives")
            .update({"status": "cancelled"})
            .eq("id", objective_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Objectif non trouvé.")

    def evaluate(
        self, objective_id: str, company_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        u = (
            supabase.table("employee_objectives")
            .update(_row_to_jsonable(payload))
            .eq("id", objective_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Objectif non trouvé.")
        got = self.get_by_id(objective_id, company_id)
        if not got:
            raise LookupError("Objectif non trouvé.")
        return got

    def decline_to_team(
        self,
        parent_id: str,
        company_id: str,
        employee_ids: List[str],
        created_by: str,
    ) -> int:
        parent = self._fetch_objective_row(parent_id, company_id)
        if not parent:
            raise LookupError("Objectif parent non trouvé.")
        if not parent.get("service_id"):
            raise ValueError("L’objectif parent doit être rattaché à un service.")
        n_emp = len(employee_ids)
        share_weight = None
        if parent.get("weight") is not None and n_emp > 0:
            share_weight = float(parent["weight"]) / float(n_emp)
        base = {
            "title": parent.get("title"),
            "type": parent.get("type"),
            "period_year": parent.get("period_year"),
            "description": parent.get("description"),
            "kpi_label": parent.get("kpi_label"),
            "kpi_unit": parent.get("kpi_unit"),
            "kpi_target_value": parent.get("kpi_target_value"),
            "kpi_initial_value": parent.get("kpi_initial_value"),
            "due_date": parent.get("due_date"),
            "notes": parent.get("notes"),
        }
        created = 0
        for eid in employee_ids:
            ins_row = {
                **base,
                "employee_id": eid,
                "service_id": None,
                "parent_objective_id": parent_id,
                "status": "active",
                "annual_review_id": parent.get("annual_review_id"),
                "weight": share_weight,
            }
            self.create(company_id, {**ins_row, "_milestones": []}, created_by)
            created += 1
        return created

    def _assert_objective(self, objective_id: str, company_id: str) -> None:
        if not self._fetch_objective_row(objective_id, company_id):
            raise LookupError("Objectif non trouvé.")

    def add_milestone(
        self, objective_id: str, company_id: str, payload: Dict[str, Any], updated_by: str
    ) -> Dict[str, Any]:
        self._assert_objective(objective_id, company_id)
        row = {
            **payload,
            "objective_id": objective_id,
            "updated_by": updated_by,
        }
        ins = supabase.table("objective_milestones").insert(_row_to_jsonable(row)).execute()
        if not ins.data:
            raise RuntimeError("Erreur création jalon.")
        return dict(ins.data[0])

    def update_milestone(
        self,
        objective_id: str,
        milestone_id: str,
        company_id: str,
        payload: Dict[str, Any],
        updated_by: str,
    ) -> Dict[str, Any]:
        self._assert_objective(objective_id, company_id)
        upd = {**payload, "updated_by": updated_by}
        u = (
            supabase.table("objective_milestones")
            .update(_row_to_jsonable(upd))
            .eq("id", milestone_id)
            .eq("objective_id", objective_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Jalon non trouvé.")
        return dict(u.data[0])

    def delete_milestone(
        self, objective_id: str, milestone_id: str, company_id: str
    ) -> None:
        self._assert_objective(objective_id, company_id)
        chk = (
            supabase.table("objective_milestones")
            .select("id")
            .eq("id", milestone_id)
            .eq("objective_id", objective_id)
            .maybe_single()
            .execute()
        )
        if not chk.data:
            raise LookupError("Jalon non trouvé.")
        supabase.table("objective_milestones").delete().eq("id", milestone_id).eq(
            "objective_id", objective_id
        ).execute()

    def add_checkin(
        self, objective_id: str, company_id: str, payload: Dict[str, Any], updated_by: str
    ) -> Dict[str, Any]:
        self._assert_objective(objective_id, company_id)
        row = {**payload, "objective_id": objective_id, "updated_by": updated_by}
        ins = supabase.table("objective_checkins").insert(_row_to_jsonable(row)).execute()
        if not ins.data:
            raise RuntimeError("Erreur création point de suivi.")
        return dict(ins.data[0])

    def get_total_weight(
        self,
        company_id: str,
        employee_id: str,
        period_year: int,
        exclude_objective_id: Optional[str] = None,
    ) -> float:
        q = (
            supabase.table("employee_objectives")
            .select("id,weight")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .eq("period_year", period_year)
            .eq("status", "active")
        )
        if exclude_objective_id:
            q = q.neq("id", exclude_objective_id)
        r = q.execute()
        total = 0.0
        for row in list(r.data or []) if r else []:
            w = row.get("weight")
            if w is not None:
                total += float(w)
        return total

    def get_achievement_rate(self, company_id: str, period_year: int) -> Optional[float]:
        r = (
            supabase.table("employee_objectives")
            .select("final_achievement_rate,weight")
            .eq("company_id", company_id)
            .eq("period_year", period_year)
            .execute()
        )
        num = 0.0
        den = 0.0
        for row in list(r.data or []) if r else []:
            rate = row.get("final_achievement_rate")
            if rate is None:
                continue
            w = row.get("weight")
            wt = float(w) if w is not None else 1.0
            num += float(rate) * wt
            den += wt
        if den == 0:
            return None
        return num / den

    def get_previous_year_rows(
        self, company_id: str, employee_id: str, reference_period_year: int
    ) -> List[Dict[str, Any]]:
        prev = reference_period_year - 1
        q = (
            supabase.table("employee_objectives")
            .select("*")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .eq("period_year", prev)
            .in_("status", ["active", "partially_achieved"])
        )
        r = q.execute()
        rows = [dict(x) for x in list(r.data or []) if r]
        if not rows:
            return []
        oids = [str(x["id"]) for x in rows]
        ms = self._fetch_milestones_map(oids)
        cs = self._fetch_checkins_map(oids)
        en = self._fetch_employee_names(company_id, [employee_id])
        sn: Dict[str, str] = {}
        return [self._enrich_objective_row(x, company_id, ms, cs, en, sn) for x in rows]


objectives_repository: AbstractObjectivesRepository = SupabaseObjectivesRepository()
