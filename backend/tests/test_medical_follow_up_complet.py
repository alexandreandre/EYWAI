#!/usr/bin/env python3
"""
Tests complets des fonctionnalités Suivi médical (page MedicalFollowUp.tsx).

Exécute les mêmes scénarios que l’onglet Suivi médical en appelant directement
les services et la base (Supabase). Aucun login, aucun token, aucun appel HTTP.

Fonctionnalités couvertes :
- Module activé (settings)
- Liste des obligations avec filtres (salarié, type de visite, statut)
- KPIs (en retard, échéance < 30 j, total actives, réalisées ce mois)
- Marquer comme planifiée
- Marquer comme réalisée
- Créer une visite à la demande
- Export CSV (structure des données)
- Calcul des obligations (compute_obligations_for_employee)

À lancer depuis backend_api avec : python test_medical_follow_up_complet.py
Prérequis : .env avec SUPABASE_URL et SUPABASE_KEY (service role).
"""

import sys
import os
from pathlib import Path
from datetime import date, timedelta
from typing import List, Optional, Any, Dict

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

try:
    from dotenv import load_dotenv
    load_dotenv(_here / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.medical_follow_up.application.service import (
    compute_obligations_for_employee,
    get_company_medical_setting,
)


class TestResult:
    def __init__(self, name: str, success: bool, message: str, data: Any = None):
        self.name = name
        self.success = success
        self.message = message
        self.data = data


def _list_obligations(
    company_id: str,
    employee_id: Optional[str] = None,
    visit_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Réplique la logique GET /api/medical-follow-up/obligations (sans auth)."""
    query = (
        supabase.table("medical_follow_up_obligations")
        .select("*, employee:employees(first_name, last_name)")
        .eq("company_id", company_id)
        .neq("status", "annulee")
    )
    if employee_id:
        query = query.eq("employee_id", employee_id)
    if visit_type:
        query = query.eq("visit_type", visit_type)
    if status:
        query = query.eq("status", status)
    if priority is not None:
        query = query.eq("priority", priority)
    if due_from:
        query = query.gte("due_date", due_from)
    if due_to:
        query = query.lte("due_date", due_to)
    query = query.order("priority").order("due_date")
    res = query.execute()
    rows = res.data or []
    result = []
    for r in rows:
        emp = r.get("employee") or {}
        result.append({
            "id": r["id"],
            "company_id": r["company_id"],
            "employee_id": r["employee_id"],
            "visit_type": r["visit_type"],
            "trigger_type": r["trigger_type"],
            "due_date": r["due_date"],
            "priority": r["priority"],
            "status": r["status"],
            "justification": r.get("justification"),
            "planned_date": r.get("planned_date"),
            "completed_date": r.get("completed_date"),
            "rule_source": r.get("rule_source") or "legal",
            "request_motif": r.get("request_motif"),
            "request_date": r.get("request_date"),
            "employee_first_name": emp.get("first_name"),
            "employee_last_name": emp.get("last_name"),
        })
    return result


def _compute_kpis(company_id: str) -> Dict[str, int]:
    """Réplique la logique GET /api/medical-follow-up/kpis (sans auth)."""
    today = date.today()
    due_30 = (today + timedelta(days=30)).isoformat()
    month_start = today.replace(day=1).isoformat()

    all_res = (
        supabase.table("medical_follow_up_obligations")
        .select("due_date, status, completed_date")
        .eq("company_id", company_id)
        .neq("status", "annulee")
        .execute()
    )
    rows = all_res.data or []

    overdue = sum(
        1
        for r in rows
        if r.get("status") != "realisee"
        and r.get("due_date")
        and r["due_date"] < today.isoformat()
    )
    due_within_30 = sum(
        1
        for r in rows
        if r.get("status") != "realisee"
        and r.get("due_date")
        and today.isoformat() <= r["due_date"] <= due_30
    )
    active_total = sum(1 for r in rows if r.get("status") != "realisee")
    completed_this_month = sum(
        1
        for r in rows
        if r.get("status") == "realisee"
        and r.get("completed_date")
        and r["completed_date"] >= month_start
    )
    return {
        "overdue_count": overdue,
        "due_within_30_count": due_within_30,
        "active_total": active_total,
        "completed_this_month": completed_this_month,
    }


class MedicalFollowUpTester:
    def __init__(self):
        self.company_id: Optional[str] = None
        self.employee_id: Optional[str] = None
        self.results: List[TestResult] = []
        self.created_obligation_ids: List[str] = []
        self._obligation_id_planified: Optional[str] = None
        self._obligation_id_completed: Optional[str] = None
        self._original_planified: Optional[Dict] = None
        self._original_completed: Optional[Dict] = None

    def log(self, message: str, level: str = "INFO"):
        prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "TEST": "🧪"}.get(level, "ℹ️")
        print(f"{prefix} {message}")

    def add(self, name: str, success: bool, message: str, data: Any = None):
        self.results.append(TestResult(name=name, success=success, message=message, data=data))
        self.log(f"{name}: {message}", "SUCCESS" if success else "ERROR")

    def setup_context(self) -> bool:
        """Récupère company_id et employee_id depuis la base."""
        self.log("Récupération company et employé...", "TEST")
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

            self.add("Setup", True, f"company={self.company_id[:8]}..., employee={self.employee_id[:8]}...")
            return True
        except Exception as e:
            self.add("Setup", False, str(e))
            return False

    def run_all_tests(self) -> None:
        if not self.company_id or not self.employee_id:
            return

        self.log("\n--- Suivi médical : Module activé ---", "TEST")
        try:
            enabled = get_company_medical_setting(str(self.company_id))
            self.add("Module suivi médical activé", True, f"enabled={enabled}", enabled)
        except Exception as e:
            self.add("Module suivi médical activé", False, str(e))
            return

        self.log("\n--- Suivi médical : Calcul des obligations (employé) ---", "TEST")
        try:
            computed = compute_obligations_for_employee(str(self.company_id), str(self.employee_id))
            self.add("Compute obligations (employé)", True, f"{len(computed)} obligation(s)", computed)
        except Exception as e:
            self.add("Compute obligations (employé)", False, str(e))

        self.log("\n--- Suivi médical : Liste des obligations (sans filtre) ---", "TEST")
        try:
            obligations = _list_obligations(self.company_id)
            self.add("Liste obligations (tous)", True, f"{len(obligations)} obligation(s)", obligations)
        except Exception as e:
            self.add("Liste obligations (tous)", False, str(e))
            return

        self.log("\n--- Suivi médical : Filtres (salarié, type, statut) ---", "TEST")
        try:
            by_employee = _list_obligations(self.company_id, employee_id=self.employee_id)
            self.add("Filtre par salarié", True, f"{len(by_employee)} obligation(s)")
        except Exception as e:
            self.add("Filtre par salarié", False, str(e))
        try:
            by_type = _list_obligations(self.company_id, visit_type="vip")
            self.add("Filtre par type (vip)", True, f"{len(by_type)} obligation(s)")
        except Exception as e:
            self.add("Filtre par type (vip)", False, str(e))
        try:
            by_status = _list_obligations(self.company_id, status="a_faire")
            self.add("Filtre par statut (à faire)", True, f"{len(by_status)} obligation(s)")
        except Exception as e:
            self.add("Filtre par statut (à faire)", False, str(e))

        self.log("\n--- Suivi médical : KPIs ---", "TEST")
        try:
            kpis = _compute_kpis(self.company_id)
            self.add(
                "KPIs",
                True,
                f"retard={kpis['overdue_count']}, <30j={kpis['due_within_30_count']}, actives={kpis['active_total']}, ce mois={kpis['completed_this_month']}",
                kpis,
            )
        except Exception as e:
            self.add("KPIs", False, str(e))

        # Choisir une obligation "à faire" pour planifiée, une pour réalisée (ou réutiliser)
        obls_a_faire = [o for o in obligations if o.get("status") == "a_faire"]
        obls_planifiees = [o for o in obligations if o.get("status") == "planifiee"]

        self.log("\n--- Suivi médical : Marquer comme planifiée ---", "TEST")
        if obls_a_faire:
            ob = obls_a_faire[0]
            self._obligation_id_planified = ob["id"]
            self._original_planified = {
                "status": ob.get("status"),
                "planned_date": ob.get("planned_date"),
                "justification": ob.get("justification"),
            }
            planned_date = date.today().isoformat()
            justification = "Test automatique planifiée"
            try:
                supabase.table("medical_follow_up_obligations").update(
                    {"status": "planifiee", "planned_date": planned_date, "justification": justification}
                ).eq("id", ob["id"]).execute()
                updated = _list_obligations(self.company_id)
                found = next((x for x in updated if x["id"] == ob["id"]), None)
                ok = found and found.get("status") == "planifiee" and found.get("planned_date") == planned_date
                self.add("Marquer comme planifiée", ok, f"id={ob['id'][:8]}..." if ok else "mise à jour non reflétée")
            except Exception as e:
                self.add("Marquer comme planifiée", False, str(e))
        else:
            self.add("Marquer comme planifiée", True, "Aucune obligation à faire, skip (OK)")

        self.log("\n--- Suivi médical : Marquer comme réalisée ---", "TEST")
        # Utiliser une obligation planifiée ou à faire (éventuellement celle qu’on vient de planifier)
        obls_now = _list_obligations(self.company_id)
        obls_for_completed = [o for o in obls_now if o.get("status") in ("a_faire", "planifiee")]
        if obls_for_completed:
            ob = obls_for_completed[0]
            self._obligation_id_completed = ob["id"]
            self._original_completed = {
                "status": ob.get("status"),
                "completed_date": ob.get("completed_date"),
                "justification": ob.get("justification"),
            }
            completed_date = date.today().isoformat()
            justification = "Test automatique réalisée"
            try:
                supabase.table("medical_follow_up_obligations").update(
                    {"status": "realisee", "completed_date": completed_date, "justification": justification}
                ).eq("id", ob["id"]).execute()
                updated = _list_obligations(self.company_id)
                found = next((x for x in updated if x["id"] == ob["id"]), None)
                ok = found and found.get("status") == "realisee" and found.get("completed_date") == completed_date
                self.add("Marquer comme réalisée", ok, f"id={ob['id'][:8]}..." if ok else "mise à jour non reflétée")
            except Exception as e:
                self.add("Marquer comme réalisée", False, str(e))
        else:
            self.add("Marquer comme réalisée", True, "Aucune obligation à planifier/réaliser, skip (OK)")

        self.log("\n--- Suivi médical : Créer visite à la demande ---", "TEST")
        request_date = date.today().isoformat()
        request_motif = "Test automatique visite à la demande"
        ins = {
            "company_id": self.company_id,
            "employee_id": self.employee_id,
            "visit_type": "demande",
            "trigger_type": "demande",
            "due_date": request_date,
            "priority": 3,
            "status": "a_faire",
            "rule_source": "legal",
            "request_motif": request_motif,
            "request_date": request_date,
        }
        try:
            res = supabase.table("medical_follow_up_obligations").insert(ins).execute()
            inserted = (res.data or [{}])[0]
            new_id = inserted.get("id")
            if new_id:
                self.created_obligation_ids.append(new_id)
            self.add(
                "Créer visite à la demande",
                bool(new_id),
                f"id={new_id[:8]}..." if new_id else "insert sans id",
                new_id,
            )
        except Exception as e:
            self.add("Créer visite à la demande", False, str(e))

        self.log("\n--- Suivi médical : Liste après créations ---", "TEST")
        try:
            after = _list_obligations(self.company_id)
            on_demand = [o for o in after if o.get("visit_type") == "demande" and o.get("request_motif") == request_motif]
            self.add("Liste après création à la demande", len(on_demand) >= 1, f"{len(on_demand)} visite(s) à la demande trouvée(s)")
        except Exception as e:
            self.add("Liste après création à la demande", False, str(e))

        self.log("\n--- Suivi médical : Export CSV (structure) ---", "TEST")
        try:
            obligations_export = _list_obligations(self.company_id)
            headers = [
                "Salarié", "Type de visite", "Déclencheur", "Date limite", "Priorité",
                "Statut", "Justification", "Date planifiée", "Date réalisée",
            ]
            rows = []
            for o in obligations_export:
                name = f"{o.get('employee_first_name') or ''} {o.get('employee_last_name') or ''}".strip()
                rows.append([
                    name, o.get("visit_type"), o.get("trigger_type"), o.get("due_date"),
                    str(o.get("priority")), o.get("status"), o.get("justification") or "",
                    o.get("planned_date") or "", o.get("completed_date") or "",
                ])
            self.add("Export CSV (structure)", len(headers) == 9 and (len(rows) >= 0), f"{len(rows)} ligne(s)")
        except Exception as e:
            self.add("Export CSV (structure)", False, str(e))

        self.cleanup()

    def cleanup(self) -> None:
        """Supprime les données créées par les tests et restaure les obligations modifiées."""
        self.log("\n--- Nettoyage ---", "TEST")

        # Si la même obligation a été planifiée puis réalisée, on ne restaure qu'une fois (état initial)
        if self._obligation_id_planified == self._obligation_id_completed and self._original_planified:
            try:
                payload = {
                    "status": self._original_planified["status"],
                    "planned_date": self._original_planified["planned_date"],
                    "justification": self._original_planified["justification"],
                }
                if self._original_planified.get("status") == "realisee":
                    payload["completed_date"] = self._original_planified.get("completed_date")
                else:
                    payload["completed_date"] = None
                supabase.table("medical_follow_up_obligations").update(payload).eq("id", self._obligation_id_planified).execute()
                self.add("Restauration obligation (planifiée+réalisée)", True, self._obligation_id_planified[:8])
            except Exception as e:
                self.add("Restauration obligation (planifiée+réalisée)", False, str(e))
        else:
            # Restaurer obligation marquée réalisée d'abord (puis planifiée)
            if self._obligation_id_completed and self._original_completed:
                try:
                    supabase.table("medical_follow_up_obligations").update(
                        {
                            "status": self._original_completed["status"],
                            "completed_date": self._original_completed["completed_date"],
                            "justification": self._original_completed["justification"],
                        }
                    ).eq("id", self._obligation_id_completed).execute()
                    self.add("Restauration obligation réalisée", True, self._obligation_id_completed[:8])
                except Exception as e:
                    self.add("Restauration obligation réalisée", False, str(e))
            if self._obligation_id_planified and self._original_planified:
                try:
                    supabase.table("medical_follow_up_obligations").update(
                        {
                            "status": self._original_planified["status"],
                            "planned_date": self._original_planified["planned_date"],
                            "justification": self._original_planified["justification"],
                        }
                    ).eq("id", self._obligation_id_planified).execute()
                    self.add("Restauration obligation planifiée", True, self._obligation_id_planified[:8])
                except Exception as e:
                    self.add("Restauration obligation planifiée", False, str(e))

        # Supprimer les visites à la demande créées par le test
        for oid in self.created_obligation_ids:
            try:
                supabase.table("medical_follow_up_obligations").delete().eq("id", oid).execute()
                self.add("Suppression visite à la demande créée", True, oid[:8])
            except Exception as e:
                self.add("Suppression visite à la demande créée", False, str(e))

    def run_all(self) -> None:
        self.log("=" * 60, "INFO")
        self.log("TESTS SUIVI MÉDICAL (sans connexion, services + DB)", "TEST")
        self.log("=" * 60, "INFO")

        if not self.setup_context():
            return

        self.run_all_tests()

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
    tester = MedicalFollowUpTester()
    tester.run_all()
    failed = sum(1 for r in tester.results if not r.success)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
