"""
Repository employés et profils : persistance Supabase (tables employees, profiles).

Implémente les ports du domain. Comportement identique au router legacy.
"""

from calendar import monthrange
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.employees.domain.salary_timeline import salaire_actif_a_date


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


def _cse_role_label(role: Optional[str]) -> Optional[str]:
    """Libellé français du rôle CSE pour la fiche salarié."""
    if not role:
        return None
    mapping = {
        "titulaire": "Titulaire",
        "suppleant": "Suppléant",
        "secretaire": "Secrétaire",
        "tresorier": "Trésorier",
        "autre": "Autre",
    }
    return mapping.get(str(role).lower(), str(role))


def _enrich_employee_row_with_cse(
    row: Dict[str, Any], company_id: str
) -> Dict[str, Any]:
    """
    Ajoute college_electoral, statut_cse, heures_delegation_mensuelles
    si mandat CSE actif (cse_elected_members).
    """
    employee_id = row.get("id")
    if not employee_id:
        return row

    out = dict(row)
    out.setdefault("college_electoral", None)
    out.setdefault("statut_cse", None)
    out.setdefault("heures_delegation_mensuelles", None)

    try:
        mandate_res = (
            supabase.table("cse_elected_members")
            .select("role, college")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .eq("is_active", True)
            .gte("end_date", date.today().isoformat())
            .order("end_date", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        return out

    members = mandate_res.data or []
    if not members:
        return out

    member = members[0]
    out["college_electoral"] = member.get("college")
    out["statut_cse"] = _cse_role_label(member.get("role"))

    collective_agreement_id = row.get("collective_agreement_id")
    if not collective_agreement_id:
        try:
            company_cc = (
                supabase.table("company_collective_agreements")
                .select("collective_agreement_id")
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
            if company_cc.data:
                collective_agreement_id = company_cc.data[0].get(
                    "collective_agreement_id"
                )
        except Exception:
            collective_agreement_id = None

    if not collective_agreement_id:
        collective_agreement_id = None

    try:
        from app.modules.cse.application.delegation_service import (
            get_delegation_quota_computed,
        )

        quota = get_delegation_quota_computed(company_id, employee_id)
        if quota and quota.quota_hours_per_month is not None:
            out["heures_delegation_mensuelles"] = float(quota.quota_hours_per_month)
    except Exception:
        pass

    return out


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

    def get_summary_by_company(
        self,
        company_id: str,
        *,
        active_only: bool = False,
        payroll_ready_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Liste allégée sans enrichissement (performances listes / planning)."""
        select_cols = (
            "id, first_name, last_name, job_title, contract_type, "
            "statut, is_forfait_jour, hire_date, date_debut_execution, "
            "contract_end_date, seniority_reference_date, employment_status, "
            "current_exit_id, duree_hebdomadaire"
        )
        if payroll_ready_only:
            select_cols += (
                ", nir, date_naissance, adresse, coordonnees_bancaires, salaire_de_base"
            )
        response = (
            supabase.table("employees")
            .select(select_cols)
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        rows = [dict(row) for row in (response.data or [])]
        if payroll_ready_only:
            from app.modules.onboarding.domain.profile import (
                enrich_employee_profile_completeness,
                is_payroll_eligible,
            )

            payroll_launch_statuses = ("actif", "active", "en_onboarding")
            active_rows = [
                r
                for r in rows
                if (r.get("employment_status") or "actif").lower()
                in payroll_launch_statuses
            ]
            enriched: List[Dict[str, Any]] = []
            for row in active_rows:
                item = enrich_employee_profile_completeness(dict(row))
                item["payroll_eligible"] = is_payroll_eligible(row)
                enriched.append(item)
            return enriched
        if not active_only:
            return rows
        return [
            r
            for r in rows
            if (r.get("employment_status") or "actif").lower() in ("actif", "active")
        ]

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
        return _enrich_employee_row_with_cse(dict(response.data), company_id)

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

    def insert_salary_history(
        self,
        employee_id: str,
        company_id: str,
        ancien_salaire: Dict,
        nouveau_salaire: Dict,
        motif: str | None,
        effective_date: str,
        created_by: str,
    ) -> Dict[str, Any]:
        """INSERT salary_history uniquement (sans toucher employees)."""
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

    def sync_salaire_actif(
        self,
        employee_id: str,
        company_id: str,
        as_of: date,
    ) -> Optional[Dict[str, Any]]:
        """Aligne employees.salaire_de_base sur le salaire actif à as_of (timeline)."""
        emp = self.get_by_id(employee_id, company_id)
        if emp is None:
            return None
        timeline = self.get_salary_history(employee_id, company_id)
        fallback = _valeur_salaire_row(emp)
        valeur = salaire_actif_a_date(timeline, as_of, fallback)
        sb = emp.get("salaire_de_base")
        if isinstance(sb, dict):
            new_sb = dict(sb)
            new_sb["valeur"] = valeur
        else:
            new_sb = {"valeur": valeur}
        return self.update(employee_id, {"salaire_de_base": new_sb})

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
        INSERT salary_history + sync salaire actif (délègue à insert + sync).
        Conservé pour compatibilité ; préférer apply_salary_update en application.
        """
        row = self.insert_salary_history(
            employee_id=employee_id,
            company_id=company_id,
            ancien_salaire=ancien_salaire,
            nouveau_salaire=nouveau_salaire,
            motif=motif,
            effective_date=effective_date,
            created_by=created_by,
        )
        eff = date.fromisoformat(str(effective_date)[:10])
        if eff <= date.today():
            synced = self.sync_salaire_actif(employee_id, company_id, date.today())
            if synced is None:
                raise RuntimeError(
                    "Mise à jour du salaire impossible (employé introuvable ou sans effet)."
                )
        return row

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
