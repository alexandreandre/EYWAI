"""
Providers — storage, attestations de salaire, calendrier, événements familiaux.

Implémentations des interfaces du domain. Utilise uniquement app.core et
app.modules.absences.infrastructure (evenements_familiaux, salary_certificate_generator).
"""
from __future__ import annotations

import calendar as cal_module
import sys
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.absences.domain.interfaces import (
    ICalendarUpdateService,
    IEvenementFamilialQuotaProvider,
    ISalaryCertificateProvider,
    IStorageProvider,
)
from app.modules.absences.infrastructure.evenements_familiaux import (
    get_events_disponibles,
    get_solde_evenement,
)
# Source de vérité attestation de salaire : app.modules.payroll.documents
from app.modules.payroll.documents.salary_certificate_generator import (
    SalaryCertificateGenerator,
)

BUCKET_LEAVE_ATTACHMENTS = "leave_attachments"
BUCKET_SALARY_CERTIFICATES = "salary_certificates"


class StorageProvider(IStorageProvider):
    """URLs signées et téléchargement Supabase Storage."""

    def create_signed_upload_url(self, path: str, bucket: str) -> str:
        resp = supabase.storage.from_(bucket).create_signed_upload_url(path)
        url = resp.get("signedUrl") or resp.get("signedURL")
        if not url:
            raise RuntimeError(f"Clé signed URL non trouvée: {resp}")
        return url

    def create_signed_urls(
        self, paths: List[str], bucket: str, expiry_seconds: int = 3600
    ) -> Dict[str, str]:
        if not paths:
            return {}
        response = supabase.storage.from_(bucket).create_signed_urls(
            paths, expiry_seconds
        )
        if isinstance(response, dict) and response.get("error"):
            return {}
        url_map = {}
        for path, item in zip(paths, response):
            url = item.get("signedURL") or item.get("signedUrl")
            if url:
                url_map[path] = url
        return url_map

    def create_signed_url(
        self,
        path: str,
        bucket: str,
        expiry_seconds: int = 3600,
        download: bool = False,
    ) -> Optional[str]:
        options = {"download": True} if download else {}
        resp = supabase.storage.from_(bucket).create_signed_url(
            path, expiry_seconds, options
        )
        if not resp:
            return None
        return resp.get("signedURL") or resp.get("signedUrl")

    def download(self, bucket: str, path: str) -> Any:
        return supabase.storage.from_(bucket).download(path)


class SalaryCertificateProvider(ISalaryCertificateProvider):
    """Génération attestation de salaire + upload + enregistrement."""

    def generate_for_absence(
        self,
        absence_request_id: str,
        generated_by: Optional[str] = None,
    ) -> Optional[str]:
        try:
            absence_resp = (
                supabase.table("absence_requests")
                .select("*")
                .eq("id", absence_request_id)
                .single()
                .execute()
            )
            if not absence_resp or not absence_resp.data:
                return None

            absence_data = absence_resp.data
            employee_id = absence_data["employee_id"]
            company_id = absence_data.get("company_id")

            employee_resp = (
                supabase.table("employees")
                .select("*")
                .eq("id", employee_id)
                .single()
                .execute()
            )
            if not employee_resp or not employee_resp.data:
                return None
            employee_data = employee_resp.data

            if not company_id:
                company_id = employee_data.get("company_id")
            if company_id:
                company_resp = (
                    supabase.table("companies")
                    .select("*")
                    .eq("id", company_id)
                    .single()
                    .execute()
                )
                company_data = (
                    company_resp.data if company_resp and company_resp.data else {}
                )
            else:
                company_data = {}

            existing = (
                supabase.table("salary_certificates")
                .select("id")
                .eq("absence_request_id", absence_request_id)
                .maybe_single()
                .execute()
            )
            if existing and existing.data:
                return existing.data["id"]

            selected_days = absence_data.get("selected_days", [])
            if not selected_days:
                return None
            first_date_str = (
                selected_days[0]
                if isinstance(selected_days[0], str)
                else selected_days[0].isoformat()
            )
            absence_start_date = (
                date.fromisoformat(first_date_str)
                if isinstance(first_date_str, str)
                else first_date_str
            )

            generator = SalaryCertificateGenerator()
            reference_salary = generator.get_reference_salary(
                employee_id, absence_start_date
            )
            pdf_bytes = generator.generate_salary_certificate(
                employee_data, company_data, absence_data, reference_salary
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"attestation_salaire_{absence_request_id}_{timestamp}.pdf"
            )
            storage_path = f"{employee_id}/{filename}"
            supabase.storage.from_(BUCKET_SALARY_CERTIFICATES).upload(
                storage_path, pdf_bytes, {"content-type": "application/pdf"}
            )

            certificate_data = {
                "employee_id": employee_id,
                "absence_request_id": absence_request_id,
                "company_id": company_id,
                "storage_path": storage_path,
                "filename": filename,
                "generated_by": generated_by,
            }
            cert_resp = supabase.table("salary_certificates").insert(
                certificate_data
            ).execute()
            if cert_resp.data:
                return cert_resp.data[0]["id"]
            return None
        except Exception as e:
            print(
                f"⚠️ Erreur lors de la génération de l'attestation: {e}",
                file=sys.stderr,
            )
            traceback.print_exc()
            return None


class CalendarUpdateProvider(ICalendarUpdateService):
    """Mise à jour employee_schedules.planned_calendar après validation absence."""

    def update_calendar_from_days(
        self,
        employee_id: str,
        days: List[date],
        absence_type_str: str,
    ) -> None:
        type_mapping = {
            "conge_paye": "conge",
            "rtt": "rtt",
            "repos_compensateur": "conge",
            "evenement_familial": "conge",
        }
        new_calendar_type = type_mapping.get(absence_type_str)
        if not new_calendar_type:
            return

        grouped_by_month: Dict[tuple, List[int]] = {}
        for d in days:
            key = (d.year, d.month)
            grouped_by_month.setdefault(key, []).append(d.day)

        for (year, month), day_list in grouped_by_month.items():
            schedule = (
                supabase.table("employee_schedules")
                .select("planned_calendar")
                .match(
                    {
                        "employee_id": employee_id,
                        "year": year,
                        "month": month,
                    }
                )
                .maybe_single()
                .execute()
            )

            if not schedule or not schedule.data or not schedule.data.get(
                "planned_calendar"
            ):
                emp = (
                    supabase.table("employees")
                    .select("company_id")
                    .eq("id", employee_id)
                    .maybe_single()
                    .execute()
                )
                if not emp or not emp.data or not emp.data.get("company_id"):
                    raise ValueError(
                        f"Employé {employee_id} sans company_id - impossible de créer le planning."
                    )
                num_days = cal_module.monthrange(year, month)[1]
                calendrier_prevu = []
                for day in range(1, num_days + 1):
                    if day in day_list:
                        calendrier_prevu.append(
                            {
                                "jour": day,
                                "type": new_calendar_type,
                                "heures_prevues": 0,
                            }
                        )
                    else:
                        calendrier_prevu.append(
                            {
                                "jour": day,
                                "type": "travail",
                                "heures_prevues": 0,
                            }
                        )
                planned_calendar_json = {"calendrier_prevu": calendrier_prevu}
                supabase.table("employee_schedules").insert(
                    {
                        "employee_id": employee_id,
                        "company_id": emp.data["company_id"],
                        "year": year,
                        "month": month,
                        "planned_calendar": planned_calendar_json,
                        "actual_hours": {},
                        "payroll_events": {},
                        "cumuls": {},
                    }
                ).execute()
            else:
                planned_calendar = schedule.data["planned_calendar"]
                for entry in planned_calendar.get("calendrier_prevu", []):
                    if entry.get("jour") in day_list:
                        entry["type"] = new_calendar_type
                supabase.table("employee_schedules").update(
                    {"planned_calendar": planned_calendar}
                ).match(
                    {
                        "employee_id": employee_id,
                        "year": year,
                        "month": month,
                    }
                ).execute()


class EvenementFamilialQuotaProvider(IEvenementFamilialQuotaProvider):
    """Quota et solde événements familiaux (délégation à services.evenements_familiaux)."""

    def get_events_disponibles(self, employee_id: str) -> List[Dict[str, Any]]:
        return get_events_disponibles(employee_id)

    def get_solde_evenement(
        self,
        employee_id: str,
        event_code: str,
        hire_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        return get_solde_evenement(employee_id, event_code, hire_date)


storage_provider = StorageProvider()
salary_certificate_provider = SalaryCertificateProvider()
calendar_update_provider = CalendarUpdateProvider()
evenement_familial_provider = EvenementFamilialQuotaProvider()
