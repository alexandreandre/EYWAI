"""
Repository employés et profils : persistance Supabase (tables employees, profiles).

Implémente les ports du domain. Comportement identique au router legacy.
"""

from calendar import monthrange
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def _subtract_months(today: date, months: int) -> date:
    """Retourne une date il y a ``months`` mois (pour filtre ancienneté)."""
    y, m = today.year, today.month - months
    while m <= 0:
        m += 12
        y -= 1
    last = monthrange(y, m)[1]
    day = min(today.day, last)
    return date(y, m, day)


def _valeur_salaire_row(row: Dict[str, Any]) -> float:
    sb = row.get("salaire_de_base")
    if sb is None:
        return 0.0
    if isinstance(sb, dict) and "valeur" in sb:
        try:
            return float(sb["valeur"])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _statut_collectif_ok(statut_brut: Any, filtre: Optional[str]) -> bool:
    """Cadre / Non-Cadre / aucun filtre (normalisation espaces/tirets)."""
    if not filtre:
        return True
    low = str(statut_brut or "").strip().lower()
    compact = low.replace(" ", "").replace("-", "")
    fw = filtre.strip().lower().replace(" ", "").replace("-", "")
    if fw == "cadre":
        return "cadre" in compact and "noncadre" not in compact
    if fw == "noncadre":
        return "noncadre" in compact or "cadre" not in compact
    return True

from app.modules.employees.domain.interfaces import (
    IEmployeeRepository,
    IProfileRepository,
)


class EmployeeRepository(IEmployeeRepository):
    """Implémentation Supabase de IEmployeeRepository."""

    def get_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        return [dict(row) for row in (response.data or [])]

    def get_by_id(self, employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return dict(response.data)

    def get_by_id_only(self, employee_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return dict(response.data)

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("employees").insert(data).execute()
        if not response.data:
            raise RuntimeError("Insert employees returned no data")
        return dict(response.data[0])

    def update(
        self, employee_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees").update(data).eq("id", employee_id).execute()
        )
        if not response.data:
            return None
        return dict(response.data[0])

    def delete(self, employee_id: str) -> bool:
        supabase.table("employees").delete().eq("id", employee_id).execute()
        return True

    def update_salary(
        self,
        employee_id: str,
        company_id: str,
        ancien_salaire: Dict,
        nouveau_salaire: Dict,
        motif: str | None,
        effective_date: str,
        created_by: str,
    ) -> Dict[str, Any]:
        """
        1. UPDATE employees SET salaire_de_base = nouveau_salaire
           WHERE id = employee_id AND company_id = company_id
        2. INSERT INTO salary_history (...)
        3. Retourner la ligne salary_history insérée
        """
        upd = (
            supabase.table("employees")
            .update({"salaire_de_base": nouveau_salaire})
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not upd.data:
            raise RuntimeError(
                "Mise à jour du salaire impossible (employé introuvable ou sans effet)."
            )
        ins = (
            supabase.table("salary_history")
            .insert(
                {
                    "employee_id": employee_id,
                    "company_id": company_id,
                    "ancien_salaire": ancien_salaire,
                    "nouveau_salaire": nouveau_salaire,
                    "motif": motif,
                    "effective_date": effective_date,
                    "created_by": created_by,
                }
            )
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Insertion salary_history sans retour.")
        row = ins.data[0] if isinstance(ins.data, list) else ins.data
        return dict(row)

    def get_salary_history(
        self,
        employee_id: str,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """
        SELECT * FROM salary_history
        WHERE employee_id = ... AND company_id = ...
        ORDER BY effective_date DESC
        """
        r = (
            supabase.table("salary_history")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .order("effective_date", desc=True)
            .execute()
        )
        return (r.data or []) if r else []

    def get_employees_filtered(
        self,
        company_id: str,
        service_id: str | None = None,
        statut: str | None = None,
        contract_type: str | None = None,
        anciennete_min_mois: int | None = None,
        salaire_min: float | None = None,
        salaire_max: float | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Retourne les employés actifs filtrés.
        employment_status = 'actif' toujours appliqué.
        anciennete_min_mois : hire_date <= (today - N mois).
        salaire_min / salaire_max : post-filtre Python sur salaire_de_base.valeur.
        """
        q = (
            supabase.table("employees")
            .select("*")
            .eq("company_id", company_id)
            .eq("employment_status", "actif")
        )
        if service_id:
            q = q.eq("service_id", service_id)
        if contract_type:
            q = q.eq("contract_type", contract_type)
        if anciennete_min_mois is not None and anciennete_min_mois >= 0:
            cutoff = _subtract_months(date.today(), anciennete_min_mois)
            q = q.lte("hire_date", cutoff.isoformat())

        r = q.order("last_name").execute()
        rows = [dict(row) for row in (r.data or [])]

        out: List[Dict[str, Any]] = []
        for row in rows:
            if not _statut_collectif_ok(row.get("statut"), statut):
                continue
            v = _valeur_salaire_row(row)
            if salaire_min is not None and v < salaire_min:
                continue
            if salaire_max is not None and v > salaire_max:
                continue
            out.append(row)

        return out


class ProfileRepository(IProfileRepository):
    """Implémentation Supabase de IProfileRepository (table profiles)."""

    def upsert(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("profiles").upsert(profile_data).execute()
        if not response.data:
            raise RuntimeError("Upsert profiles returned no data")
        data = response.data
        first = data[0] if isinstance(data, list) else data
        return dict(first) if first is not None else {}
