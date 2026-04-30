"""Persistance onboarding (Supabase)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

DEFAULT_ONBOARDING_TASKS: List[Dict[str, Any]] = [
    {
        "title": "Remettre le contrat signé",
        "category": "administratif",
        "due_days": 1,
        "position": 0,
    },
    {
        "title": "Collecter les documents RH",
        "description": "CNI, RIB, justificatif domicile, mutuelle",
        "category": "administratif",
        "due_days": 3,
        "position": 1,
    },
    {
        "title": "Déclarer l'embauche (DPAE)",
        "category": "administratif",
        "due_days": 1,
        "position": 2,
    },
    {
        "title": "Inscription mutuelle et prévoyance",
        "category": "administratif",
        "due_days": 7,
        "position": 3,
    },
    {
        "title": "Préparer le poste de travail",
        "category": "materiel",
        "due_days": 1,
        "position": 4,
    },
    {
        "title": "Remettre le matériel informatique",
        "category": "materiel",
        "due_days": 1,
        "position": 5,
    },
    {
        "title": "Badge et accès locaux",
        "category": "acces",
        "due_days": 1,
        "position": 6,
    },
    {
        "title": "Créer les accès email et outils",
        "category": "acces",
        "due_days": 1,
        "position": 7,
    },
    {
        "title": "Accès EYWAI collaborateur",
        "category": "acces",
        "due_days": 1,
        "position": 8,
    },
    {
        "title": "Présenter l'entreprise et l'équipe",
        "category": "formation",
        "due_days": 1,
        "position": 9,
    },
    {
        "title": "Formation aux outils internes",
        "category": "formation",
        "due_days": 7,
        "position": 10,
    },
    {
        "title": "Présenter le règlement intérieur",
        "category": "formation",
        "due_days": 3,
        "position": 11,
    },
    {
        "title": "Déjeuner d'équipe de bienvenue",
        "category": "social",
        "due_days": 7,
        "position": 12,
    },
    {
        "title": "Point d'étonnement J+30",
        "description": "Premier retour du nouveau collaborateur",
        "category": "social",
        "due_days": 30,
        "position": 13,
    },
]


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _build_checklist_payload(
    checklist_row: Dict[str, Any], task_rows: List[Dict[str, Any]]
) -> Dict[str, Any]:
    tasks_sorted = sorted(task_rows, key=lambda t: int(t.get("position") or 0))
    tasks_out: List[Dict[str, Any]] = []
    nb_completed = 0
    for t in tasks_sorted:
        if t.get("is_completed"):
            nb_completed += 1
        tasks_out.append(
            {
                "id": str(t["id"]),
                "checklist_id": str(t["checklist_id"]),
                "title": str(t.get("title") or ""),
                "description": t.get("description"),
                "category": str(t.get("category") or ""),
                "is_completed": bool(t.get("is_completed")),
                "completed_at": _parse_ts(t.get("completed_at")),
                "due_days": t.get("due_days"),
                "position": int(t.get("position") or 0),
            }
        )
    nb_total = len(tasks_out)
    progress_pct = (nb_completed / nb_total * 100.0) if nb_total else 0.0
    cr = _parse_ts(checklist_row.get("created_at")) or datetime.now(timezone.utc)
    return {
        "id": str(checklist_row["id"]),
        "employee_id": str(checklist_row["employee_id"]),
        "company_id": str(checklist_row["company_id"]),
        "created_at": cr,
        "completed_at": _parse_ts(checklist_row.get("completed_at")),
        "tasks": tasks_out,
        "nb_total": nb_total,
        "nb_completed": nb_completed,
        "progress_pct": progress_pct,
    }


class OnboardingRepository:
    def create_checklist(self, employee_id: str, company_id: str) -> Dict[str, Any]:
        existing = self.get_checklist_by_employee(employee_id, company_id)
        if existing:
            return existing

        ins = (
            supabase.table("onboarding_checklists")
            .insert({"employee_id": employee_id, "company_id": company_id})
            .execute()
        )
        if not ins or not ins.data:
            raise RuntimeError("Échec création checklist onboarding")
        checklist = ins.data[0]
        cid = str(checklist["id"])
        tasks_data: List[Dict[str, Any]] = []
        for tdef in DEFAULT_ONBOARDING_TASKS:
            tasks_data.append(
                {
                    "checklist_id": cid,
                    "company_id": company_id,
                    "title": tdef["title"],
                    "description": tdef.get("description"),
                    "category": tdef["category"],
                    "due_days": tdef.get("due_days"),
                    "position": tdef["position"],
                    "is_completed": False,
                }
            )
        tr = supabase.table("onboarding_tasks").insert(tasks_data).execute()
        inserted = (tr.data or []) if tr else []
        if len(inserted) != len(tasks_data):
            raise RuntimeError(
                "Échec création des tâches onboarding (insert incomplet)."
            )

        out = self.get_checklist_by_employee(employee_id, company_id)
        if not out:
            raise RuntimeError("Checklist onboarding introuvable après création.")
        return out

    def get_checklist_by_employee(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table("onboarding_checklists")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not res or not res.data:
            return None
        checklist_row = res.data
        tid = str(checklist_row["id"])
        tres = (
            supabase.table("onboarding_tasks")
            .select("*")
            .eq("checklist_id", tid)
            .eq("company_id", company_id)
            .order("position")
            .execute()
        )
        task_rows = (tres.data or []) if tres else []
        return _build_checklist_payload(checklist_row, task_rows)

    def complete_task(
        self,
        task_id: str,
        checklist_id: str,
        company_id: str,
        completed_by: str,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        upd = (
            supabase.table("onboarding_tasks")
            .update(
                {
                    "is_completed": True,
                    "completed_at": now,
                    "completed_by": completed_by,
                }
            )
            .eq("id", task_id)
            .eq("checklist_id", checklist_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not upd or not upd.data:
            return False

        remaining = (
            supabase.table("onboarding_tasks")
            .select("id", count="exact")
            .eq("checklist_id", checklist_id)
            .eq("company_id", company_id)
            .eq("is_completed", False)
            .execute()
        )
        cnt = remaining.count if remaining and remaining.count is not None else 0
        if cnt == 0:
            supabase.table("onboarding_checklists").update({"completed_at": now}).eq(
                "id", checklist_id
            ).eq("company_id", company_id).execute()
        return True

    def uncomplete_task(
        self, task_id: str, checklist_id: str, company_id: str
    ) -> bool:
        upd = (
            supabase.table("onboarding_tasks")
            .update(
                {
                    "is_completed": False,
                    "completed_at": None,
                    "completed_by": None,
                }
            )
            .eq("id", task_id)
            .eq("checklist_id", checklist_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not upd or not upd.data:
            return False
        supabase.table("onboarding_checklists").update({"completed_at": None}).eq(
            "id", checklist_id
        ).eq("company_id", company_id).execute()
        return True


onboarding_repository = OnboardingRepository()
