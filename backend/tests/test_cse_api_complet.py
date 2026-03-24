#!/usr/bin/env python3
"""
Tests complets des fonctionnalités CSE — sans connexion HTTP.

Exécute les mêmes scénarios que les onglets CSE côté RH (CSE.tsx) et côté
collaborateur (employee/CSE.tsx) en appelant directement les services et la base
(Supabase). Aucun login, aucun token, aucun appel API.

À lancer depuis backend_api avec : python test_cse_api_complet.py
Prérequis : .env avec SUPABASE_URL et SUPABASE_KEY (service role).
"""

import sys
import os
from pathlib import Path
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Any, Dict
from dataclasses import dataclass

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

try:
    from dotenv import load_dotenv
    load_dotenv(_here / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.cse.infrastructure.cse_export_impl import (
    export_delegation_hours as export_delegation_hours_xlsx,
    export_elected_members as export_elected_members_xlsx,
    export_meetings_history as export_meetings_history_xlsx,
)
from app.modules.cse.infrastructure.cse_pdf_impl import (
    generate_election_calendar_pdf,
    generate_minutes_pdf,
)
from app.modules.cse.infrastructure.cse_service_impl import (
    _check_module_active,
    add_participants,
    create_delegation_hour,
    create_elected_member,
    create_election_cycle,
    create_meeting,
    get_bdes_document_by_id,
    get_bdes_documents,
    get_delegation_hours,
    get_delegation_quota,
    get_delegation_summary,
    get_elected_member_by_employee,
    get_elected_member_by_id,
    get_elected_members,
    get_election_alerts,
    get_election_cycle_by_id,
    get_election_cycles,
    get_mandate_alerts,
    get_meeting_by_id,
    get_meetings,
    get_meeting_participants,
    remove_participant,
    start_recording,
    stop_recording,
    update_elected_member,
    update_meeting,
    upload_bdes_document,
)
from app.modules.cse.schemas import (
    DelegationHourCreate,
    ElectedMemberCreate,
    ElectedMemberUpdate,
    ElectionCycleCreate,
    MeetingCreate,
    MeetingUpdate,
)


@dataclass
class TestResult:
    name: str
    success: bool
    message: str
    data: Optional[Any] = None


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Pydantic v1 .dict() ou v2 .model_dump()."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj) if obj is not None else {}


class CSETester:
    def __init__(self):
        self.company_id: Optional[str] = None
        self.employee_id: Optional[str] = None
        self.profile_id: Optional[str] = None
        self.created_member_ids: List[str] = []
        self.created_meeting_ids: List[str] = []
        self.created_cycle_ids: List[str] = []
        self.created_hour_ids: List[str] = []
        self.results: List[TestResult] = []

    def log(self, message: str, level: str = "INFO"):
        prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "TEST": "🧪"}.get(level, "ℹ️")
        print(f"{prefix} {message}")

    def add(self, name: str, success: bool, message: str, data: Any = None):
        self.results.append(TestResult(name=name, success=success, message=message, data=data))
        self.log(f"{name}: {message}", "SUCCESS" if success else "ERROR")

    def setup_context(self) -> bool:
        """Récupère company_id, employee_id et profile_id depuis la base."""
        self.log("Récupération company, employé et profil...", "TEST")
        try:
            r = supabase.table("companies").select("id").limit(1).execute()
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucune company en base")
                return False
            self.company_id = r.data[0]["id"]

            r = supabase.table("employees").select("id").eq("company_id", self.company_id).limit(1).execute()
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucun employé pour cette company")
                return False
            self.employee_id = r.data[0]["id"]

            r = supabase.table("profiles").select("id").limit(1).execute()
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucun profil en base")
                return False
            self.profile_id = r.data[0]["id"]

            self.add("Setup", True, f"company={self.company_id[:8]}..., employee={self.employee_id[:8]}..., profile={self.profile_id[:8]}...")
            return True
        except Exception as e:
            self.add("Setup", False, str(e))
            return False

    def run_rh_tests(self) -> None:
        """Scénarios de la page CSE.tsx côté RH (tous les onglets)."""
        if not self.company_id or not self.profile_id:
            return

        self.log("\n--- CSE RH : Alertes (header) ---", "TEST")
        try:
            _check_module_active(self.company_id)
            alerts = get_mandate_alerts(self.company_id, months_before=3)
            self.add("Alertes mandats", True, f"{len(alerts)} alerte(s)", alerts)
        except Exception as e:
            self.add("Alertes mandats", False, str(e))

        try:
            alerts = get_election_alerts(self.company_id)
            self.add("Alertes électorales", True, f"{len(alerts)} alerte(s)", alerts)
        except Exception as e:
            self.add("Alertes électorales", False, str(e))

        self.log("\n--- CSE RH : Onglet Élus ---", "TEST")
        try:
            members = get_elected_members(self.company_id, active_only=True)
            self.add("Liste élus", True, f"{len(members)} élu(s)", members)
        except Exception as e:
            self.add("Liste élus", False, str(e))
            return

        self.log("\n--- CSE RH : Onglet Réunions ---", "TEST")
        try:
            meetings = get_meetings(self.company_id)
            self.add("Liste réunions", True, f"{len(meetings)} réunion(s)", meetings)
        except Exception as e:
            self.add("Liste réunions", False, str(e))
            return

        try:
            meetings_filt = get_meetings(self.company_id, status="a_venir", meeting_type="ordinaire")
            self.add("Liste réunions (filtres)", True, f"{len(meetings_filt)} réunion(s)")
        except Exception as e:
            self.add("Liste réunions (filtres)", False, str(e))

        meeting_id = meetings[0].id if meetings else None
        if meeting_id:
            try:
                meeting = get_meeting_by_id(meeting_id, self.company_id)
                self.add("Détail réunion", True, meeting_id[:8])
                # Test mise à jour statut (sans changer vraiment)
                update_meeting(meeting_id, self.company_id, MeetingUpdate(status=meeting.status))
                self.add("PUT statut réunion", True, "ok")
            except Exception as e:
                self.add("Détail réunion / PUT statut", False, str(e))

        self.log("\n--- CSE RH : Onglet Délégation ---", "TEST")
        now = date.today()
        period_start = now.replace(day=1)
        period_end = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        try:
            summary = get_delegation_summary(self.company_id, period_start, period_end)
            self.add("Récap délégation", True, f"{len(summary)} ligne(s)")
        except Exception as e:
            self.add("Récap délégation", False, str(e))

        try:
            resp = supabase.table("cse_delegation_quotas").select(
                "*, collective_agreements_catalog!inner(id, name)"
            ).eq("company_id", self.company_id).execute()
            quotas = resp.data or []
            self.add("Liste quotas délégation", True, f"{len(quotas)} quota(s)")
        except Exception as e:
            self.add("Liste quotas délégation", False, str(e))

        self.log("\n--- CSE RH : Onglet BDES ---", "TEST")
        try:
            docs = get_bdes_documents(self.company_id)
            self.add("Liste documents BDES", True, f"{len(docs)} document(s)")
        except Exception as e:
            self.add("Liste documents BDES", False, str(e))
            return

        if docs:
            try:
                doc = get_bdes_document_by_id(docs[0].id, self.company_id)
                self.add("Détail document BDES", True, doc.id[:8])
            except Exception as e:
                self.add("Détail document BDES", False, str(e))

        self.log("\n--- CSE RH : Onglet Élections ---", "TEST")
        try:
            cycles = get_election_cycles(self.company_id)
            self.add("Liste cycles électoraux", True, f"{len(cycles)} cycle(s)")
        except Exception as e:
            self.add("Liste cycles électoraux", False, str(e))
            return

        if cycles:
            try:
                cycle = get_election_cycle_by_id(cycles[0].id, self.company_id)
                self.add("Détail cycle électoral", True, cycle.id[:8])
            except Exception as e:
                self.add("Détail cycle électoral", False, str(e))

        self.log("\n--- CSE RH : Onglet Exports ---", "TEST")
        try:
            members = get_elected_members(self.company_id, active_only=False)
            members_dict = [_to_dict(m) for m in members]
            buf = export_elected_members_xlsx(members_dict)
            self.add("Export élus (Excel)", True, f"{len(buf)} octets")
        except Exception as e:
            self.add("Export élus (Excel)", False, str(e))

        try:
            members = get_elected_members(self.company_id, active_only=True)
            all_hours = []
            for m in members:
                h = get_delegation_hours(self.company_id, m.employee_id, period_start, period_end)
                all_hours.extend([_to_dict(x) for x in h])
            summary = get_delegation_summary(self.company_id, period_start, period_end)
            summary_dict = [_to_dict(s) for s in summary]
            buf = export_delegation_hours_xlsx(all_hours, summary_dict)
            self.add("Export heures délégation (Excel)", True, f"{len(buf)} octets")
        except Exception as e:
            self.add("Export heures délégation (Excel)", False, str(e))

        try:
            meetings = get_meetings(self.company_id)
            meetings_dict = [_to_dict(m) for m in meetings]
            buf = export_meetings_history_xlsx(meetings_dict)
            self.add("Export historique réunions (Excel)", True, f"{len(buf)} octets")
        except Exception as e:
            self.add("Export historique réunions (Excel)", False, str(e))

        year = now.year
        try:
            meetings_done = get_meetings(self.company_id, status="terminee")
            if meetings_done:
                m0 = get_meeting_by_id(meetings_done[0].id, self.company_id)
                meeting_dict = _to_dict(m0)
                buf = generate_minutes_pdf(meeting_dict)
                self.add("Export PV annuel (PDF)", True, f"{len(buf)} octets")
            else:
                self.add("Export PV annuel (PDF)", True, "aucune réunion terminée (skip)")
        except Exception as e:
            self.add("Export PV annuel (PDF)", False, str(e))

        try:
            if cycles:
                cycle = get_election_cycle_by_id(cycles[0].id, self.company_id)
                cycle_dict = _to_dict(cycle)
                timeline = [ _to_dict(s) for s in (cycle.timeline or []) ]
                buf = generate_election_calendar_pdf(cycle_dict, timeline)
                self.add("Export calendrier électoral (PDF)", True, f"{len(buf)} octets")
            else:
                self.add("Export calendrier électoral (PDF)", True, "aucun cycle (skip)")
        except Exception as e:
            self.add("Export calendrier électoral (PDF)", False, str(e))

    def run_employee_tests(self) -> None:
        """Scénarios de la page employee/CSE.tsx (côté collaborateur / élu)."""
        if not self.company_id or not self.employee_id or not self.profile_id:
            return

        self.log("\n--- CSE Collaborateur : Statut élu ---", "TEST")
        try:
            mandate = get_elected_member_by_employee(self.company_id, self.employee_id)
            is_elected = mandate is not None
            self.add("Statut élu (/me)", True, f"is_elected={is_elected}")
        except Exception as e:
            self.add("Statut élu (/me)", False, str(e))
            return

        if not is_elected:
            self.log("  (Utilisateur non élu : tests lecture quota/heures/réunions/BDES limités ou vides)", "WARNING")
            # On teste quand même les endpoints qui peuvent répondre (quota peut être null)
            try:
                quota = get_delegation_quota(self.company_id, self.employee_id)
                self.add("Quota délégation (non élu)", True, "quota=None ou valeur")
            except Exception as e:
                self.add("Quota délégation (non élu)", False, str(e))
            return

        self.log("\n--- CSE Collaborateur : Quota et heures ---", "TEST")
        try:
            quota = get_delegation_quota(self.company_id, self.employee_id)
            self.add("Quota délégation", True, f"quota_hours={quota.quota_hours_per_month if quota else None}")
        except Exception as e:
            self.add("Quota délégation", False, str(e))

        now = date.today()
        month_start = now.replace(day=1)
        month_end = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        try:
            hours = get_delegation_hours(self.company_id, self.employee_id, month_start, month_end)
            self.add("Heures délégation (mois)", True, f"{len(hours)} heure(s)")
        except Exception as e:
            self.add("Heures délégation (mois)", False, str(e))

        self.log("\n--- CSE Collaborateur : Réunions (mes réunions) ---", "TEST")
        try:
            meetings = get_meetings(self.company_id, participant_id=self.employee_id)
            self.add("Mes réunions", True, f"{len(meetings)} réunion(s)")
        except Exception as e:
            self.add("Mes réunions", False, str(e))

        self.log("\n--- CSE Collaborateur : BDES ---", "TEST")
        try:
            docs = get_bdes_documents(self.company_id, visible_to_elected_only=True)
            self.add("Documents BDES (élus)", True, f"{len(docs)} document(s)")
        except Exception as e:
            self.add("Documents BDES (élus)", False, str(e))

        self.log("\n--- CSE Collaborateur : Saisie heure délégation ---", "TEST")
        try:
            data = DelegationHourCreate(
                date=date.today(),
                duration_hours=0.5,
                reason="Test automatique CSE (à supprimer si besoin)",
            )
            hour = create_delegation_hour(
                self.company_id,
                self.employee_id,
                data,
                created_by=self.profile_id,
            )
            self.created_hour_ids.append(hour.id)
            self.add("Création heure délégation", True, hour.id[:8])
        except Exception as e:
            self.add("Création heure délégation", False, str(e))

    def run_crud_tests(self) -> None:
        """Quelques créations/suppressions pour valider les flux complets (nettoyés en fin)."""
        if not self.company_id or not self.employee_id or not self.profile_id:
            return

        self.log("\n--- CSE CRUD : Élu + Réunion + Cycle (création puis suppression) ---", "TEST")

        # Créer un élu (mandat futur)
        start = date.today()
        end = start + timedelta(days=365)
        try:
            data = ElectedMemberCreate(
                employee_id=self.employee_id,
                role="titulaire",
                college="Test",
                start_date=start,
                end_date=end,
            )
            member = create_elected_member(self.company_id, data, created_by=self.profile_id)
            self.created_member_ids.append(member.id)
            self.add("Création élu CSE", True, member.id[:8])
        except Exception as e:
            self.add("Création élu CSE", False, str(e))
            return

        # Créer une réunion
        try:
            data = MeetingCreate(
                title="Réunion test CSE",
                meeting_date=date.today() + timedelta(days=7),
                meeting_time=time(14, 0),
                meeting_type="ordinaire",
            )
            meeting = create_meeting(self.company_id, data, created_by=self.profile_id)
            self.created_meeting_ids.append(meeting.id)
            self.add("Création réunion CSE", True, meeting.id[:8])
        except Exception as e:
            self.add("Création réunion CSE", False, str(e))

        # Créer un cycle électoral
        try:
            data = ElectionCycleCreate(
                cycle_name="Cycle test CSE",
                mandate_end_date=date.today() + timedelta(days=400),
            )
            cycle = create_election_cycle(self.company_id, data)
            self.created_cycle_ids.append(cycle.id)
            self.add("Création cycle électoral", True, cycle.id[:8])
        except Exception as e:
            self.add("Création cycle électoral", False, str(e))

    def cleanup(self) -> None:
        """Supprime les données créées par les tests."""
        self.log("\n--- Nettoyage ---", "TEST")

        for mid in self.created_member_ids:
            try:
                supabase.table("cse_elected_members").delete().eq("id", mid).eq("company_id", self.company_id).execute()
                self.add("Suppression élu créé", True, mid[:8])
            except Exception as e:
                self.add("Suppression élu créé", False, str(e))

        for meeting_id in self.created_meeting_ids:
            try:
                supabase.table("cse_meetings").delete().eq("id", meeting_id).eq("company_id", self.company_id).execute()
                self.add("Suppression réunion créée", True, meeting_id[:8])
            except Exception as e:
                self.add("Suppression réunion créée", False, str(e))

        for cycle_id in self.created_cycle_ids:
            try:
                supabase.table("cse_election_timeline").delete().eq("election_cycle_id", cycle_id).execute()
                supabase.table("cse_election_cycles").delete().eq("id", cycle_id).eq("company_id", self.company_id).execute()
                self.add("Suppression cycle créé", True, cycle_id[:8])
            except Exception as e:
                self.add("Suppression cycle créé", False, str(e))

        # Heures de délégation créées : pas d'API delete exposée, on laisse ou on supprime en SQL
        for hid in self.created_hour_ids:
            try:
                supabase.table("cse_delegation_hours").delete().eq("id", hid).execute()
                self.add("Suppression heure délégation créée", True, hid[:8])
            except Exception as e:
                self.add("Suppression heure délégation créée", False, str(e))

    def run_all(self) -> None:
        self.log("=" * 60, "INFO")
        self.log("TESTS CSE (sans connexion, services + DB)", "TEST")
        self.log("=" * 60, "INFO")

        if not self.setup_context():
            return

        self.run_rh_tests()
        self.run_employee_tests()
        self.run_crud_tests()
        self.cleanup()

        total = len(self.results)
        success = sum(1 for r in self.results if r.success)
        failed = total - success
        self.log("\n" + "=" * 60, "INFO")
        self.log("RÉSUMÉ", "TEST")
        self.log("=" * 60, "INFO")
        self.log(f"Total: {total} | Réussis: {success} | Échoués: {failed}", "INFO")
        if failed > 0:
            for r in self.results:
                if not r.success:
                    self.log(f"  - {r.name}: {r.message}", "ERROR")
        self.log("=" * 60, "INFO")


def main():
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("❌ Définir SUPABASE_URL et SUPABASE_KEY dans backend_api/.env")
        sys.exit(1)
    tester = CSETester()
    tester.run_all()
    failed = sum(1 for r in tester.results if not r.success)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
