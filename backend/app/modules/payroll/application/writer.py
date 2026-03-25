"""
Génération et enregistrement des événements de paie dans Supabase.

Migré depuis backend_api/payroll_writer.py.
"""
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from app.core.database import get_supabase_admin_client
from app.modules.payroll.application.analyzer import analyser_horaires_du_mois

load_dotenv()


def generer_et_enregistrer_evenements(
    employee_id: str,
    employee_name: str,
    duree_hebdo: float,
    year: int,
    month: int,
) -> Optional[Dict[str, Any]]:
    """
    Analyse les horaires et enregistre directement les événements de paie dans Supabase.
    """
    try:
        supabase = get_supabase_admin_client()
        print(f"🧮 [PayrollWriter] Début génération événements {employee_name} ({month}/{year})", file=sys.stderr)

        res = supabase.table("employee_schedules").select("planned_calendar, actual_hours") \
            .match({"employee_id": employee_id, "year": year, "month": month}) \
            .maybe_single().execute()

        if not res.data:
            print(f"❌ Aucun calendrier trouvé pour {employee_name} ({month}/{year})", file=sys.stderr)
            return None

        planned_calendar = res.data.get("planned_calendar") or []
        actual_hours = res.data.get("actual_hours") or []

        evenements = analyser_horaires_du_mois(
            planned_calendar, actual_hours, duree_hebdo, year, month, employee_name
        )

        payload = {
            "periode": {"mois": month, "annee": year},
            "calendrier_analyse": evenements
        }

        supabase.table("employee_schedules").update({
            "payroll_events": payload,
            "updated_at": datetime.utcnow().isoformat()
        }).match({
            "employee_id": employee_id,
            "year": year,
            "month": month
        }).execute()

        print(f"✅ [PayrollWriter] {len(evenements)} événements enregistrés pour {employee_name} ({month}/{year})", file=sys.stderr)
        return payload

    except Exception as e:
        print(f"❌ [PayrollWriter] Erreur : {e}", file=sys.stderr)
        return None
