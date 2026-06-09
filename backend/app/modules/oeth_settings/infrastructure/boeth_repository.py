"""Repositories BOETH salariés et revues annuelles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase


class BoethProfilesRepository:
    def get_active_by_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_boeth_profiles")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def get_active_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employee_boeth_profiles")
            .select("*")
            .eq("company_id", company_id)
            .eq("is_active", True)
            .execute()
        )
        return r.data or []

    def count_active_by_company(self, company_id: str) -> int:
        return len(self.get_active_by_company(company_id))

    def upsert_profile(
        self,
        company_id: str,
        employee_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing = self.get_active_by_employee(employee_id)
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            previous_code = existing.get("boeth_code")
            new_code = data.get("boeth_code", previous_code)
            if previous_code != new_code:
                supabase.table("employee_boeth_status_history").insert(
                    {
                        "employee_id": employee_id,
                        "company_id": company_id,
                        "previous_boeth_code": previous_code,
                        "new_boeth_code": new_code,
                        "changed_at": data.get("valid_from") or datetime.now().date().isoformat(),
                    }
                ).execute()
            payload = {**data, "updated_at": now}
            payload.pop("created_at", None)
            res = (
                supabase.table("employee_boeth_profiles")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            payload = {
                **data,
                "employee_id": employee_id,
                "company_id": company_id,
                "is_active": True,
            }
            res = supabase.table("employee_boeth_profiles").insert(payload).execute()
        if not res.data:
            raise RuntimeError("Upsert employee_boeth_profiles sans données")
        return res.data[0] if isinstance(res.data, list) else res.data

    def deactivate(self, employee_id: str, company_id: str) -> None:
        existing = self.get_active_by_employee(employee_id)
        if not existing:
            return
        supabase.table("employee_boeth_status_history").insert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "previous_boeth_code": existing.get("boeth_code"),
                "new_boeth_code": None,
            }
        ).execute()
        supabase.table("employee_boeth_profiles").update(
            {"is_active": False, "valid_to": datetime.now().date().isoformat()}
        ).eq("id", existing["id"]).execute()

    def get_history(self, employee_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employee_boeth_status_history")
            .select("*")
            .eq("employee_id", employee_id)
            .order("changed_at", desc=True)
            .execute()
        )
        return r.data or []

    def get_status_for_period(
        self, company_id: str, year: int, month: int
    ) -> Dict[str, Dict[str, Any]]:
        """Map employee_id -> profil BOETH actif en début de mois."""
        profiles = self.get_active_by_company(company_id)
        result: Dict[str, Dict[str, Any]] = {}
        for p in profiles:
            result[p["employee_id"]] = p
        return result

    def get_change_in_period(
        self, employee_id: str, period: str
    ) -> Optional[Dict[str, Any]]:
        """Retourne le changement BOETH sur la période YYYY-MM."""
        r = (
            supabase.table("employee_boeth_status_history")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("changed_in_period", period)
            .maybe_single()
            .execute()
        )
        if r and r.data:
            return r.data
        year, month = map(int, period.split("-"))
        start = f"{year:04d}-{month:02d}-01"
        r2 = (
            supabase.table("employee_boeth_status_history")
            .select("*")
            .eq("employee_id", employee_id)
            .gte("changed_at", start)
            .order("changed_at")
            .limit(1)
            .execute()
        )
        rows = r2.data or []
        return rows[0] if rows else None


boeth_profiles_repository = BoethProfilesRepository()


class OethAnnualRepository:
    def get_review(self, company_id: str, year: int) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("company_oeth_annual_reviews")
            .select("*")
            .eq("company_id", company_id)
            .eq("employment_year", year)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def upsert_review(self, company_id: str, year: int, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "employment_year": year}
        payload.pop("created_at", None)
        if payload.get("id") is None:
            payload.pop("id", None)
        res = (
            supabase.table("company_oeth_annual_reviews")
            .upsert(payload, on_conflict="company_id,employment_year")
            .execute()
        )
        if not res.data:
            raise RuntimeError("Upsert company_oeth_annual_reviews sans données")
        return res.data[0] if isinstance(res.data, list) else res.data

    def list_reviews(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("company_oeth_annual_reviews")
            .select("*")
            .eq("company_id", company_id)
            .order("employment_year", desc=True)
            .execute()
        )
        return r.data or []

    def list_externes(self, company_id: str, year: int) -> List[Dict[str, Any]]:
        r = (
            supabase.table("company_oeth_boeth_externes")
            .select("*")
            .eq("company_id", company_id)
            .eq("employment_year", year)
            .execute()
        )
        return r.data or []

    def replace_externes(
        self, company_id: str, year: int, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        supabase.table("company_oeth_boeth_externes").delete().eq(
            "company_id", company_id
        ).eq("employment_year", year).execute()
        if not rows:
            return []
        payload = [{**r, "company_id": company_id, "employment_year": year} for r in rows]
        res = supabase.table("company_oeth_boeth_externes").insert(payload).execute()
        return res.data or []

    def list_deductions(self, company_id: str, year: int) -> List[Dict[str, Any]]:
        r = (
            supabase.table("company_oeth_deductions")
            .select("*")
            .eq("company_id", company_id)
            .eq("employment_year", year)
            .execute()
        )
        return r.data or []

    def replace_deductions(
        self, company_id: str, year: int, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        supabase.table("company_oeth_deductions").delete().eq(
            "company_id", company_id
        ).eq("employment_year", year).execute()
        if not rows:
            return []
        payload = [{**r, "company_id": company_id, "employment_year": year} for r in rows]
        res = supabase.table("company_oeth_deductions").insert(payload).execute()
        return res.data or []

    def list_ecap(self, company_id: str, year: int) -> List[Dict[str, Any]]:
        r = (
            supabase.table("company_oeth_ecap_positions")
            .select("*")
            .eq("company_id", company_id)
            .eq("employment_year", year)
            .execute()
        )
        return r.data or []

    def replace_ecap(
        self, company_id: str, year: int, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        supabase.table("company_oeth_ecap_positions").delete().eq(
            "company_id", company_id
        ).eq("employment_year", year).execute()
        if not rows:
            return []
        payload = [{**r, "company_id": company_id, "employment_year": year} for r in rows]
        res = supabase.table("company_oeth_ecap_positions").insert(payload).execute()
        return res.data or []


oeth_annual_repository = OethAnnualRepository()
