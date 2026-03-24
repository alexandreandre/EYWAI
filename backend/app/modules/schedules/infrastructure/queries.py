"""
Lecture employés / entreprises pour le module schedules (tables employees, companies).

Implémentation du port IEmployeeCompanyReader. Utilisé par l'application pour
récupérer company_id, statut, employee_folder_name, parametres_paie, etc.
"""
import sys
import traceback
from typing import Any, Dict, Optional, Tuple

from postgrest.exceptions import APIError

from app.core.database import supabase
from app.modules.schedules.domain.exceptions import (
    ScheduleDatabaseError,
    ScheduleNotFoundError,
)
from app.modules.schedules.domain.interfaces import IEmployeeCompanyReader


class EmployeeCompanyReader(IEmployeeCompanyReader):
    """Lecture employees et companies via Supabase."""

    def get_company_and_statut(
        self, employee_id: str
    ) -> Tuple[str, Optional[str]]:
        try:
            employee_res = (
                supabase.table("employees")
                .select("company_id, statut")
                .eq("id", employee_id)
                .single()
                .execute()
            )
        except Exception as e:
            print(f"❌ Erreur lors de la récupération de l'employé: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            try:
                employee_res = (
                    supabase.table("employees")
                    .select("company_id, statut")
                    .eq("id", employee_id)
                    .single()
                    .execute()
                )
            except Exception as e2:
                print(f"❌ Échec de la nouvelle tentative: {e2}", file=sys.stderr)
                raise ScheduleDatabaseError(
                    f"Erreur de connexion à la base de données: {str(e2)}"
                ) from e2

        employee_data = employee_res.data if hasattr(employee_res, "data") else None
        if not employee_data or not employee_data.get("company_id"):
            raise ScheduleNotFoundError("Employé non trouvé ou sans entreprise associée")
        return employee_data["company_id"], employee_data.get("statut")

    def get_employee_folder_name(self, employee_id: str) -> str:
        try:
            response = (
                supabase.table("employees")
                .select("employee_folder_name")
                .eq("id", employee_id)
                .single()
                .execute()
            )
        except APIError as e:
            # Supabase renvoie PGRST116 quand .single() ne trouve aucune ligne.
            if getattr(e, "code", None) == "PGRST116":
                raise ScheduleNotFoundError("Employé non trouvé.") from e
            raise ScheduleDatabaseError(
                f"Erreur de connexion à la base de données: {str(e)}"
            ) from e
        if not response or not response.data:
            raise ScheduleNotFoundError("Employé non trouvé.")
        return response.data["employee_folder_name"]

    def get_employee_for_payroll_events(self, employee_id: str) -> Dict[str, Any]:
        response = (
            supabase.table("employees")
            .select("employee_folder_name, duree_hebdomadaire, statut, company_id")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not response or not response.data:
            raise ScheduleNotFoundError("Employé non trouvé.")
        return response.data

    def get_company_parametres_paie(self, company_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("companies")
            .select("parametres_paie")
            .eq("id", company_id)
            .single()
            .execute()
        )
        if not response or not response.data:
            return None
        return response.data.get("parametres_paie")


# Instance unique pour l'application
employee_company_reader = EmployeeCompanyReader()
