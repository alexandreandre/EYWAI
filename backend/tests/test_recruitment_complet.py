#!/usr/bin/env python3
"""
Tests complets des fonctionnalités Recrutement (page Recruitment.tsx).

Exécute les mêmes scénarios que l'onglet Recrutement en appelant directement
les services et la base (Supabase). Aucun login, aucun token, aucun appel HTTP.

Fonctionnalités couvertes :
 1. Module activé (settings)
 2. Création d'un poste (job) + pipeline par défaut
 3. Liste des postes
 4. Modification d'un poste
 5. Récupération des étapes du pipeline
 6. Création d'un candidat
 7. Liste des candidats (sans filtre, par job, recherche)
 8. Détail d'un candidat
 9. Modification d'un candidat
10. Déplacement d'un candidat dans le pipeline (stage_changed)
11. Ajout d'une note
12. Ajout d'un avis favorable
13. Ajout d'un avis défavorable
14. Planification d'un entretien + participants
15. Mise à jour entretien (summary)
16. Timeline (vérification des événements)
17. Détection de doublon candidat (même email)
18. Détection de doublon salarié (même email)
19. Refus d'un candidat (motif obligatoire)
20. Embauche d'un candidat → création salarié
21. Suppression d'un candidat en début de process
22. Motifs de refus (liste statique)
23. Nettoyage complet

À lancer depuis backend_api avec : python test_recruitment_complet.py
Prérequis : .env avec SUPABASE_URL et SUPABASE_KEY (service role).
"""

import sys
import os
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

try:
    from dotenv import load_dotenv
    load_dotenv(_here / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.recruitment.application.service import (
    check_duplicate_candidate,
    check_duplicate_employee,
    get_recruitment_setting,
    is_user_participant_for_candidate,
    service_hire_candidate,
)
from app.modules.recruitment.infrastructure.providers import (
    DEFAULT_PIPELINE_STAGES,
    REJECTION_REASONS,
)
from app.modules.recruitment.infrastructure.repository import (
    _pipeline_stage_repo,
    _timeline_writer,
)


def create_default_pipeline(company_id: str, job_id: str):
    """Alias test : création des étapes pipeline (ex-services.recruitment_service)."""
    return _pipeline_stage_repo.create_default_for_job(company_id, job_id)


def add_timeline_event(
    company_id: str,
    candidate_id: str,
    event_type: str,
    description: str,
    actor_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Alias test : événement timeline (ex-services.recruitment_service)."""
    _timeline_writer.add(
        company_id, candidate_id, event_type, description, actor_id, metadata
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, name: str, success: bool, message: str, data: Any = None):
        self.name = name
        self.success = success
        self.message = message
        self.data = data


def _list_jobs(company_id: str, status: Optional[str] = None) -> List[Dict]:
    q = supabase.table("recruitment_jobs").select("*").eq("company_id", company_id)
    if status:
        q = q.eq("status", status)
    q = q.order("created_at", desc=True)
    return q.execute().data or []


def _get_stages(company_id: str, job_id: str) -> List[Dict]:
    return (
        supabase.table("recruitment_pipeline_stages")
        .select("*").eq("job_id", job_id).eq("company_id", company_id)
        .order("position").execute().data or []
    )


def _list_candidates(company_id: str, job_id: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
    q = (
        supabase.table("recruitment_candidates")
        .select("*, stage:recruitment_pipeline_stages(name, stage_type)")
        .eq("company_id", company_id)
    )
    if job_id:
        q = q.eq("job_id", job_id)
    q = q.order("created_at", desc=True)
    rows = q.execute().data or []
    if search:
        s = search.lower()
        rows = [
            c for c in rows
            if s in (c.get("first_name", "") + " " + c.get("last_name", "")).lower()
            or s in (c.get("email") or "").lower()
            or s in (c.get("phone") or "").lower()
        ]
    return rows


def _get_candidate(company_id: str, candidate_id: str) -> Optional[Dict]:
    r = (
        supabase.table("recruitment_candidates")
        .select("*, stage:recruitment_pipeline_stages(name, stage_type)")
        .eq("id", candidate_id).eq("company_id", company_id)
        .maybe_single().execute()
    )
    return r.data if r else None


def _list_notes(company_id: str, candidate_id: str) -> List[Dict]:
    return (
        supabase.table("recruitment_notes")
        .select("*, author:profiles!author_id(first_name, last_name)")
        .eq("candidate_id", candidate_id).eq("company_id", company_id)
        .order("created_at", desc=True).execute().data or []
    )


def _list_opinions(company_id: str, candidate_id: str) -> List[Dict]:
    return (
        supabase.table("recruitment_opinions")
        .select("*, author:profiles!author_id(first_name, last_name)")
        .eq("candidate_id", candidate_id).eq("company_id", company_id)
        .order("created_at", desc=True).execute().data or []
    )


def _list_interviews(company_id: str, candidate_id: Optional[str] = None) -> List[Dict]:
    q = (
        supabase.table("recruitment_interviews")
        .select("*, recruitment_interview_participants(user_id, role)")
        .eq("company_id", company_id)
    )
    if candidate_id:
        q = q.eq("candidate_id", candidate_id)
    return q.order("scheduled_at", desc=True).execute().data or []


def _list_timeline(company_id: str, candidate_id: str) -> List[Dict]:
    return (
        supabase.table("recruitment_timeline_events")
        .select("*")
        .eq("candidate_id", candidate_id).eq("company_id", company_id)
        .order("created_at", desc=True).execute().data or []
    )


# ═══════════════════════════════════════════════════════════════════════
# Main tester
# ═══════════════════════════════════════════════════════════════════════

class RecruitmentTester:
    def __init__(self):
        self.company_id: Optional[str] = None
        self.actor_id: Optional[str] = None
        self.results: List[TestResult] = []

        # IDs créés (pour cleanup)
        self._created_job_ids: List[str] = []
        self._created_candidate_ids: List[str] = []
        self._created_employee_ids: List[str] = []
        self._created_note_ids: List[str] = []
        self._created_opinion_ids: List[str] = []
        self._created_interview_ids: List[str] = []

        # Données de test
        self._job_id: Optional[str] = None
        self._stages: List[Dict] = []
        self._candidate_id_main: Optional[str] = None
        self._candidate_id_reject: Optional[str] = None
        self._candidate_id_hire: Optional[str] = None
        self._candidate_id_delete: Optional[str] = None
        self._candidate_id_dup: Optional[str] = None
        self._interview_id: Optional[str] = None

    # ── Logging ───────────────────────────────────────────────────

    def log(self, message: str, level: str = "INFO"):
        prefix = {"INFO": "ℹ️ ", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️ ", "TEST": "🧪"}.get(level, "ℹ️ ")
        print(f"{prefix} {message}")

    def add(self, name: str, success: bool, message: str, data: Any = None):
        self.results.append(TestResult(name=name, success=success, message=message, data=data))
        self.log(f"{name}: {message}", "SUCCESS" if success else "ERROR")

    # ── Setup ─────────────────────────────────────────────────────

    def setup_context(self) -> bool:
        self.log("Récupération company et profil (acteur)...", "TEST")
        try:
            r = supabase.table("companies").select("id").limit(1).execute()
            if not r.data:
                self.add("Setup", False, "Aucune company en base")
                return False
            self.company_id = r.data[0]["id"]

            r = supabase.table("profiles").select("id").limit(1).execute()
            if not r.data:
                self.add("Setup", False, "Aucun profil en base")
                return False
            self.actor_id = r.data[0]["id"]

            self.add("Setup", True, f"company={self.company_id[:8]}..., actor={self.actor_id[:8]}...")
            return True
        except Exception as e:
            self.add("Setup", False, str(e))
            return False

    # ── Tests ─────────────────────────────────────────────────────

    def run_all_tests(self):
        if not self.company_id or not self.actor_id:
            return

        self.test_01_module_enabled()
        self.test_02_create_job()
        self.test_03_list_jobs()
        self.test_04_update_job()
        self.test_05_pipeline_stages()
        self.test_06_create_candidate()
        self.test_07_create_extra_candidates()
        self.test_08_list_candidates()
        self.test_09_list_candidates_search()
        self.test_10_get_candidate_detail()
        self.test_11_update_candidate()
        self.test_12_move_candidate()
        self.test_13_add_note()
        self.test_14_list_notes()
        self.test_15_add_opinion_favorable()
        self.test_16_add_opinion_defavorable()
        self.test_17_list_opinions()
        self.test_18_create_interview()
        self.test_19_add_participant()
        self.test_20_list_interviews()
        self.test_21_update_interview_summary()
        self.test_22_check_participant()
        self.test_23_timeline_events()
        self.test_24_duplicate_candidate()
        self.test_25_reject_candidate()
        self.test_26_hire_candidate()
        self.test_27_duplicate_employee()
        self.test_28_delete_candidate()
        self.test_29_rejection_reasons()

        self.cleanup()

    # ─── 1. Module activé ─────────────────────────────────────────

    def test_01_module_enabled(self):
        self.log("\n--- 01. Module Recrutement activé ---", "TEST")
        try:
            enabled = get_recruitment_setting(self.company_id)
            self.add("Module recrutement activé", enabled is True, f"enabled={enabled}")
        except Exception as e:
            self.add("Module recrutement activé", False, str(e))

    # ─── 2. Créer un poste ────────────────────────────────────────

    def test_02_create_job(self):
        self.log("\n--- 02. Créer un poste + pipeline par défaut ---", "TEST")
        try:
            row = {
                "company_id": self.company_id,
                "title": "[TEST] Développeur Python",
                "description": "Poste de test automatisé",
                "location": "Paris",
                "contract_type": "CDI",
                "status": "active",
                "tags": ["test", "python"],
                "created_by": self.actor_id,
            }
            res = supabase.table("recruitment_jobs").insert(row).execute()
            job = (res.data or [{}])[0]
            job_id = job.get("id")
            if not job_id:
                self.add("Créer un poste", False, "Insert sans id retourné")
                return
            self._job_id = job_id
            self._created_job_ids.append(job_id)

            stages = create_default_pipeline(self.company_id, job_id)
            self._stages = stages

            ok = (
                job.get("title") == "[TEST] Développeur Python"
                and job.get("status") == "active"
                and len(stages) == len(DEFAULT_PIPELINE_STAGES)
            )
            self.add(
                "Créer un poste + pipeline",
                ok,
                f"job={job_id[:8]}..., {len(stages)} étapes créées",
            )
        except Exception as e:
            self.add("Créer un poste + pipeline", False, str(e))

    # ─── 3. Lister les postes ─────────────────────────────────────

    def test_03_list_jobs(self):
        self.log("\n--- 03. Liste des postes ---", "TEST")
        try:
            jobs = _list_jobs(self.company_id)
            found = any(j["id"] == self._job_id for j in jobs)
            self.add("Liste des postes", found, f"{len(jobs)} poste(s), test trouvé={found}")
        except Exception as e:
            self.add("Liste des postes", False, str(e))

    # ─── 4. Modifier un poste ─────────────────────────────────────

    def test_04_update_job(self):
        self.log("\n--- 04. Modifier un poste ---", "TEST")
        if not self._job_id:
            self.add("Modifier un poste", False, "Pas de job créé")
            return
        try:
            supabase.table("recruitment_jobs").update({
                "description": "Poste modifié par test auto"
            }).eq("id", self._job_id).execute()
            updated = supabase.table("recruitment_jobs").select("description").eq("id", self._job_id).single().execute()
            ok = updated.data and updated.data.get("description") == "Poste modifié par test auto"
            self.add("Modifier un poste", ok, "description mise à jour" if ok else "mise à jour non reflétée")
        except Exception as e:
            self.add("Modifier un poste", False, str(e))

    # ─── 5. Étapes du pipeline ────────────────────────────────────

    def test_05_pipeline_stages(self):
        self.log("\n--- 05. Étapes du pipeline ---", "TEST")
        if not self._job_id:
            self.add("Étapes du pipeline", False, "Pas de job créé")
            return
        try:
            stages = _get_stages(self.company_id, self._job_id)
            self._stages = stages
            names = [s["name"] for s in stages]
            expected = [d["name"] for d in DEFAULT_PIPELINE_STAGES]
            ok = names == expected
            has_rejected = any(s["stage_type"] == "rejected" for s in stages)
            has_hired = any(s["stage_type"] == "hired" for s in stages)
            self.add(
                "Étapes du pipeline",
                ok and has_rejected and has_hired,
                f"{len(stages)} étapes: {', '.join(names)} | rejected={has_rejected}, hired={has_hired}",
            )
        except Exception as e:
            self.add("Étapes du pipeline", False, str(e))

    # ─── 6. Créer un candidat ─────────────────────────────────────

    def test_06_create_candidate(self):
        self.log("\n--- 06. Créer un candidat ---", "TEST")
        if not self._job_id or not self._stages:
            self.add("Créer un candidat", False, "Pas de job ou stages")
            return
        try:
            first_stage = self._stages[0]
            row = {
                "company_id": self.company_id,
                "job_id": self._job_id,
                "current_stage_id": first_stage["id"],
                "first_name": "Jean",
                "last_name": "Test-Recrut",
                "email": "jean.test.recrut.auto@example.com",
                "phone": "0600000099",
                "source": "Test automatisé",
                "created_by": self.actor_id,
            }
            res = supabase.table("recruitment_candidates").insert(row).execute()
            c = (res.data or [{}])[0]
            cid = c.get("id")
            if not cid:
                self.add("Créer un candidat", False, "Insert sans id")
                return
            self._candidate_id_main = cid
            self._created_candidate_ids.append(cid)

            add_timeline_event(
                self.company_id, cid, "candidate_created",
                f"Candidat créé : Jean Test-Recrut", self.actor_id,
            )

            ok = c.get("first_name") == "Jean" and c.get("current_stage_id") == first_stage["id"]
            self.add("Créer un candidat", ok, f"id={cid[:8]}..., étape={first_stage['name']}")
        except Exception as e:
            self.add("Créer un candidat", False, str(e))

    # ─── 7. Créer des candidats supplémentaires ──────────────────

    def test_07_create_extra_candidates(self):
        self.log("\n--- 07. Créer candidats supplémentaires (refus, embauche, suppression, doublon) ---", "TEST")
        if not self._job_id or not self._stages:
            self.add("Candidats supplémentaires", False, "Pas de job ou stages")
            return
        try:
            first_stage = self._stages[0]
            extras = [
                {"first_name": "Marie", "last_name": "Refusée", "email": "marie.refusee@example.com", "attr": "_candidate_id_reject"},
                {"first_name": "Paul", "last_name": "Embauché", "email": "paul.embauche@example.com", "attr": "_candidate_id_hire"},
                {"first_name": "Luc", "last_name": "Supprimé", "email": "luc.supprime@example.com", "attr": "_candidate_id_delete"},
                {"first_name": "Jean-Dup", "last_name": "Doublon", "email": "jean.test.recrut.auto@example.com", "attr": "_candidate_id_dup"},
            ]
            created_count = 0
            for ex in extras:
                row = {
                    "company_id": self.company_id,
                    "job_id": self._job_id,
                    "current_stage_id": first_stage["id"],
                    "first_name": ex["first_name"],
                    "last_name": ex["last_name"],
                    "email": ex["email"],
                    "source": "Test auto",
                    "created_by": self.actor_id,
                }
                res = supabase.table("recruitment_candidates").insert(row).execute()
                c = (res.data or [{}])[0]
                cid = c.get("id")
                if cid:
                    setattr(self, ex["attr"], cid)
                    self._created_candidate_ids.append(cid)
                    created_count += 1

            self.add("Candidats supplémentaires", created_count == 4, f"{created_count}/4 créés")
        except Exception as e:
            self.add("Candidats supplémentaires", False, str(e))

    # ─── 8. Lister les candidats ──────────────────────────────────

    def test_08_list_candidates(self):
        self.log("\n--- 08. Liste des candidats (par job) ---", "TEST")
        try:
            all_cands = _list_candidates(self.company_id, job_id=self._job_id)
            our_ids = set(self._created_candidate_ids)
            found = [c for c in all_cands if c["id"] in our_ids]
            self.add("Liste candidats (par job)", len(found) >= 5, f"{len(found)} candidats test trouvés sur {len(all_cands)} total")
        except Exception as e:
            self.add("Liste candidats (par job)", False, str(e))

    # ─── 9. Recherche candidats ───────────────────────────────────

    def test_09_list_candidates_search(self):
        self.log("\n--- 09. Recherche candidats (nom) ---", "TEST")
        try:
            results = _list_candidates(self.company_id, job_id=self._job_id, search="Jean Test-Recrut")
            found = any(c["id"] == self._candidate_id_main for c in results)
            self.add("Recherche candidats (nom)", found, f"{len(results)} résultat(s), principal trouvé={found}")
        except Exception as e:
            self.add("Recherche candidats (nom)", False, str(e))

    # ─── 10. Détail candidat ──────────────────────────────────────

    def test_10_get_candidate_detail(self):
        self.log("\n--- 10. Détail d'un candidat ---", "TEST")
        if not self._candidate_id_main:
            self.add("Détail candidat", False, "Pas de candidat principal")
            return
        try:
            c = _get_candidate(self.company_id, self._candidate_id_main)
            ok = (
                c is not None
                and c.get("first_name") == "Jean"
                and c.get("last_name") == "Test-Recrut"
                and c.get("email") == "jean.test.recrut.auto@example.com"
            )
            stage_name = (c.get("stage") or {}).get("name", "?") if c else "?"
            self.add("Détail candidat", ok, f"Jean Test-Recrut, étape={stage_name}")
        except Exception as e:
            self.add("Détail candidat", False, str(e))

    # ─── 11. Modifier un candidat ─────────────────────────────────

    def test_11_update_candidate(self):
        self.log("\n--- 11. Modifier un candidat ---", "TEST")
        if not self._candidate_id_main:
            self.add("Modifier candidat", False, "Pas de candidat")
            return
        try:
            supabase.table("recruitment_candidates").update({
                "phone": "0611111111",
                "source": "LinkedIn (modifié)",
            }).eq("id", self._candidate_id_main).execute()

            c = _get_candidate(self.company_id, self._candidate_id_main)
            ok = c and c.get("phone") == "0611111111" and c.get("source") == "LinkedIn (modifié)"
            self.add("Modifier candidat", ok, "phone + source mis à jour" if ok else "mise à jour non reflétée")
        except Exception as e:
            self.add("Modifier candidat", False, str(e))

    # ─── 12. Déplacer un candidat dans le pipeline ────────────────

    def test_12_move_candidate(self):
        self.log("\n--- 12. Déplacer un candidat (Premier appel → Entretien RH) ---", "TEST")
        if not self._candidate_id_main or len(self._stages) < 2:
            self.add("Déplacer candidat", False, "Pas de candidat ou pas assez d'étapes")
            return
        try:
            target_stage = self._stages[1]  # "Entretien RH"
            supabase.table("recruitment_candidates").update({
                "current_stage_id": target_stage["id"]
            }).eq("id", self._candidate_id_main).execute()

            add_timeline_event(
                self.company_id, self._candidate_id_main, "stage_changed",
                f"Jean Test-Recrut déplacé vers \"{target_stage['name']}\"",
                self.actor_id,
                {"stage_id": target_stage["id"], "stage_name": target_stage["name"]},
            )

            c = _get_candidate(self.company_id, self._candidate_id_main)
            ok = c and c.get("current_stage_id") == target_stage["id"]
            self.add("Déplacer candidat", ok, f"→ {target_stage['name']}" if ok else "déplacement non reflété")
        except Exception as e:
            self.add("Déplacer candidat", False, str(e))

    # ─── 13. Ajouter une note ─────────────────────────────────────

    def test_13_add_note(self):
        self.log("\n--- 13. Ajouter une note ---", "TEST")
        if not self._candidate_id_main:
            self.add("Ajouter note", False, "Pas de candidat")
            return
        try:
            row = {
                "company_id": self.company_id,
                "candidate_id": self._candidate_id_main,
                "content": "Bon profil, expérience Python solide. À revoir sur le React.",
                "author_id": self.actor_id,
            }
            res = supabase.table("recruitment_notes").insert(row).execute()
            n = (res.data or [{}])[0]
            nid = n.get("id")
            if nid:
                self._created_note_ids.append(nid)

            add_timeline_event(
                self.company_id, self._candidate_id_main, "note_added",
                "Note ajoutée", self.actor_id,
            )

            ok = nid is not None and n.get("content") == row["content"]
            self.add("Ajouter note", ok, f"id={nid[:8]}..." if ok else "insert échoué")
        except Exception as e:
            self.add("Ajouter note", False, str(e))

    # ─── 14. Lister les notes ─────────────────────────────────────

    def test_14_list_notes(self):
        self.log("\n--- 14. Lister les notes ---", "TEST")
        try:
            notes = _list_notes(self.company_id, self._candidate_id_main)
            ok = len(notes) >= 1
            self.add("Lister notes", ok, f"{len(notes)} note(s)")
        except Exception as e:
            self.add("Lister notes", False, str(e))

    # ─── 15. Avis favorable ──────────────────────────────────────

    def test_15_add_opinion_favorable(self):
        self.log("\n--- 15. Ajouter avis favorable ---", "TEST")
        if not self._candidate_id_main:
            self.add("Avis favorable", False, "Pas de candidat")
            return
        try:
            row = {
                "company_id": self.company_id,
                "candidate_id": self._candidate_id_main,
                "rating": "favorable",
                "comment": "Très bon entretien, recommandé pour la suite.",
                "author_id": self.actor_id,
            }
            res = supabase.table("recruitment_opinions").insert(row).execute()
            o = (res.data or [{}])[0]
            oid = o.get("id")
            if oid:
                self._created_opinion_ids.append(oid)

            add_timeline_event(
                self.company_id, self._candidate_id_main, "opinion_added",
                "Avis favorable donné", self.actor_id,
            )

            ok = oid is not None and o.get("rating") == "favorable"
            self.add("Avis favorable", ok, f"id={oid[:8]}..." if ok else "insert échoué")
        except Exception as e:
            self.add("Avis favorable", False, str(e))

    # ─── 16. Avis défavorable ────────────────────────────────────

    def test_16_add_opinion_defavorable(self):
        self.log("\n--- 16. Ajouter avis défavorable ---", "TEST")
        if not self._candidate_id_main:
            self.add("Avis défavorable", False, "Pas de candidat")
            return
        try:
            row = {
                "company_id": self.company_id,
                "candidate_id": self._candidate_id_main,
                "rating": "defavorable",
                "comment": "Manque d'expérience sur l'architecture micro-services.",
                "author_id": self.actor_id,
            }
            res = supabase.table("recruitment_opinions").insert(row).execute()
            o = (res.data or [{}])[0]
            oid = o.get("id")
            if oid:
                self._created_opinion_ids.append(oid)

            add_timeline_event(
                self.company_id, self._candidate_id_main, "opinion_added",
                "Avis défavorable donné", self.actor_id,
            )

            ok = oid is not None and o.get("rating") == "defavorable"
            self.add("Avis défavorable", ok, f"id={oid[:8]}..." if ok else "insert échoué")
        except Exception as e:
            self.add("Avis défavorable", False, str(e))

    # ─── 17. Lister les avis ─────────────────────────────────────

    def test_17_list_opinions(self):
        self.log("\n--- 17. Lister les avis ---", "TEST")
        try:
            opinions = _list_opinions(self.company_id, self._candidate_id_main)
            fav = sum(1 for o in opinions if o.get("rating") == "favorable")
            defav = sum(1 for o in opinions if o.get("rating") == "defavorable")
            ok = fav >= 1 and defav >= 1
            self.add("Lister avis", ok, f"{len(opinions)} avis (favorable={fav}, défavorable={defav})")
        except Exception as e:
            self.add("Lister avis", False, str(e))

    # ─── 18. Planifier un entretien ──────────────────────────────

    def test_18_create_interview(self):
        self.log("\n--- 18. Planifier un entretien ---", "TEST")
        if not self._candidate_id_main:
            self.add("Planifier entretien", False, "Pas de candidat")
            return
        try:
            scheduled = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
            row = {
                "company_id": self.company_id,
                "candidate_id": self._candidate_id_main,
                "interview_type": "Entretien technique",
                "scheduled_at": scheduled,
                "duration_minutes": 45,
                "location": "Salle A2",
                "meeting_link": "https://meet.example.com/test",
                "created_by": self.actor_id,
            }
            res = supabase.table("recruitment_interviews").insert(row).execute()
            i = (res.data or [{}])[0]
            iid = i.get("id")
            if iid:
                self._interview_id = iid
                self._created_interview_ids.append(iid)

            add_timeline_event(
                self.company_id, self._candidate_id_main, "interview_planned",
                f"Entretien \"Entretien technique\" planifié le {scheduled[:10]}",
                self.actor_id,
            )

            ok = (
                iid is not None
                and i.get("interview_type") == "Entretien technique"
                and i.get("duration_minutes") == 45
                and i.get("status") == "planned"
            )
            self.add("Planifier entretien", ok, f"id={iid[:8]}..., {i.get('interview_type')}, {i.get('duration_minutes')}min")
        except Exception as e:
            self.add("Planifier entretien", False, str(e))

    # ─── 19. Ajouter participant ─────────────────────────────────

    def test_19_add_participant(self):
        self.log("\n--- 19. Ajouter participant à l'entretien ---", "TEST")
        if not self._interview_id:
            self.add("Ajouter participant", False, "Pas d'entretien")
            return
        try:
            row = {
                "interview_id": self._interview_id,
                "user_id": self.actor_id,
                "role": "interviewer",
            }
            res = supabase.table("recruitment_interview_participants").insert(row).execute()
            p = (res.data or [{}])[0]
            ok = p.get("id") is not None
            self.add("Ajouter participant", ok, f"user={self.actor_id[:8]}... ajouté comme interviewer")
        except Exception as e:
            self.add("Ajouter participant", False, str(e))

    # ─── 20. Lister entretiens ───────────────────────────────────

    def test_20_list_interviews(self):
        self.log("\n--- 20. Lister les entretiens ---", "TEST")
        try:
            interviews = _list_interviews(self.company_id, self._candidate_id_main)
            ok = len(interviews) >= 1
            if ok:
                i = interviews[0]
                parts = i.get("recruitment_interview_participants") or []
                self.add("Lister entretiens", True, f"{len(interviews)} entretien(s), {len(parts)} participant(s)")
            else:
                self.add("Lister entretiens", False, "Aucun entretien trouvé")
        except Exception as e:
            self.add("Lister entretiens", False, str(e))

    # ─── 21. Mettre à jour entretien (summary) ──────────────────

    def test_21_update_interview_summary(self):
        self.log("\n--- 21. Ajouter compte-rendu à l'entretien ---", "TEST")
        if not self._interview_id:
            self.add("Compte-rendu entretien", False, "Pas d'entretien")
            return
        try:
            supabase.table("recruitment_interviews").update({
                "summary": "Candidat très technique, maîtrise Python/FastAPI. À challenger sur le front.",
                "status": "completed",
            }).eq("id", self._interview_id).execute()

            i = supabase.table("recruitment_interviews").select("summary, status").eq("id", self._interview_id).single().execute()
            ok = i.data and i.data.get("status") == "completed" and "technique" in (i.data.get("summary") or "")
            self.add("Compte-rendu entretien", ok, "summary + status=completed" if ok else "mise à jour non reflétée")
        except Exception as e:
            self.add("Compte-rendu entretien", False, str(e))

    # ─── 22. Vérifier participant ────────────────────────────────

    def test_22_check_participant(self):
        self.log("\n--- 22. Vérifier si l'acteur est participant du candidat ---", "TEST")
        if not self._candidate_id_main:
            self.add("Check participant", False, "Pas de candidat")
            return
        try:
            is_part = is_user_participant_for_candidate(self.actor_id, self._candidate_id_main)
            self.add("Check participant", is_part is True, f"is_participant={is_part}")
        except Exception as e:
            self.add("Check participant", False, str(e))

    # ─── 23. Timeline ────────────────────────────────────────────

    def test_23_timeline_events(self):
        self.log("\n--- 23. Timeline du candidat ---", "TEST")
        if not self._candidate_id_main:
            self.add("Timeline", False, "Pas de candidat")
            return
        try:
            events = _list_timeline(self.company_id, self._candidate_id_main)
            types = [e["event_type"] for e in events]
            has_created = "candidate_created" in types
            has_moved = "stage_changed" in types
            has_note = "note_added" in types
            has_opinion = "opinion_added" in types
            has_interview = "interview_planned" in types

            ok = has_created and has_moved and has_note and has_opinion and has_interview
            self.add(
                "Timeline",
                ok,
                f"{len(events)} événement(s): created={has_created}, moved={has_moved}, note={has_note}, opinion={has_opinion}, interview={has_interview}",
            )
        except Exception as e:
            self.add("Timeline", False, str(e))

    # ─── 24. Détection doublon candidat ──────────────────────────

    def test_24_duplicate_candidate(self):
        self.log("\n--- 24. Détection doublon candidat (même email) ---", "TEST")
        try:
            dup = check_duplicate_candidate(
                self.company_id,
                email="jean.test.recrut.auto@example.com",
                phone=None,
                exclude_id=self._candidate_id_dup,
            )
            ok = dup is not None and dup.get("id") == self._candidate_id_main
            self.add(
                "Doublon candidat",
                ok,
                f"Doublon détecté: {dup.get('first_name')} {dup.get('last_name')} (id={dup['id'][:8]}...)" if ok else "Pas de doublon détecté",
            )
        except Exception as e:
            self.add("Doublon candidat", False, str(e))

    # ─── 25. Refuser un candidat ─────────────────────────────────

    def test_25_reject_candidate(self):
        self.log("\n--- 25. Refuser un candidat ---", "TEST")
        if not self._candidate_id_reject or not self._stages:
            self.add("Refuser candidat", False, "Pas de candidat ou stages")
            return
        try:
            rejected_stage = next((s for s in self._stages if s["stage_type"] == "rejected"), None)
            if not rejected_stage:
                self.add("Refuser candidat", False, "Étape 'rejected' non trouvée")
                return

            supabase.table("recruitment_candidates").update({
                "current_stage_id": rejected_stage["id"],
                "rejection_reason": "Prétentions salariales",
                "rejection_reason_detail": "Budget dépassé de 15k",
            }).eq("id", self._candidate_id_reject).execute()

            add_timeline_event(
                self.company_id, self._candidate_id_reject, "rejected",
                "Marie Refusée déplacée vers \"Refusé\"",
                self.actor_id,
                {"stage_id": rejected_stage["id"], "stage_name": "Refusé"},
            )

            c = _get_candidate(self.company_id, self._candidate_id_reject)
            ok = (
                c is not None
                and c.get("current_stage_id") == rejected_stage["id"]
                and c.get("rejection_reason") == "Prétentions salariales"
            )
            self.add("Refuser candidat", ok, f"raison={c.get('rejection_reason')}" if ok else "refus non reflété")
        except Exception as e:
            self.add("Refuser candidat", False, str(e))

    # ─── 26. Embaucher un candidat → créer salarié ───────────────

    def test_26_hire_candidate(self):
        self.log("\n--- 26. Embaucher candidat → créer salarié ---", "TEST")
        if not self._candidate_id_hire or not self._stages:
            self.add("Embaucher candidat", False, "Pas de candidat ou stages")
            return
        try:
            hired_stage = next((s for s in self._stages if s["stage_type"] == "hired"), None)
            if not hired_stage:
                self.add("Embaucher candidat", False, "Étape 'hired' non trouvée")
                return

            supabase.table("recruitment_candidates").update({
                "current_stage_id": hired_stage["id"],
            }).eq("id", self._candidate_id_hire).execute()

            employee = service_hire_candidate(
                self._candidate_id_hire,
                self.company_id,
                date.today().isoformat(),
                job_title="Développeur Python",
                contract_type="CDI",
                actor_id=self.actor_id,
            )

            emp_id = employee.get("id")
            if emp_id:
                self._created_employee_ids.append(emp_id)

            c = _get_candidate(self.company_id, self._candidate_id_hire)
            ok = (
                emp_id is not None
                and c is not None
                and c.get("employee_id") == emp_id
                and c.get("hired_at") is not None
            )
            self.add(
                "Embaucher candidat",
                ok,
                f"employee_id={emp_id[:8]}..., hired_at={c.get('hired_at')}" if ok else "embauche échouée",
            )
        except Exception as e:
            self.add("Embaucher candidat", False, str(e))

    # ─── 27. Détection doublon salarié ───────────────────────────

    def test_27_duplicate_employee(self):
        self.log("\n--- 27. Détection doublon salarié (même email) ---", "TEST")
        try:
            dup = check_duplicate_employee(self.company_id, email="paul.embauche@example.com", phone=None)
            ok = dup is not None and dup.get("first_name") == "Paul"
            self.add(
                "Doublon salarié",
                ok,
                f"Doublon détecté: {dup.get('first_name')} {dup.get('last_name')}" if ok else "Pas de doublon détecté (salarié créé juste avant)",
            )
        except Exception as e:
            self.add("Doublon salarié", False, str(e))

    # ─── 28. Supprimer candidat (début de pipeline) ──────────────

    def test_28_delete_candidate(self):
        self.log("\n--- 28. Supprimer candidat en début de process ---", "TEST")
        if not self._candidate_id_delete:
            self.add("Supprimer candidat", False, "Pas de candidat")
            return
        try:
            supabase.table("recruitment_candidates").delete().eq("id", self._candidate_id_delete).execute()
            c = _get_candidate(self.company_id, self._candidate_id_delete)
            ok = c is None
            if ok:
                self._created_candidate_ids.remove(self._candidate_id_delete)
                self._candidate_id_delete = None
            self.add("Supprimer candidat", ok, "candidat supprimé" if ok else "candidat encore présent")
        except Exception as e:
            self.add("Supprimer candidat", False, str(e))

    # ─── 29. Motifs de refus (liste statique) ────────────────────

    def test_29_rejection_reasons(self):
        self.log("\n--- 29. Motifs de refus ---", "TEST")
        try:
            ok = len(REJECTION_REASONS) >= 3 and "Autre" in REJECTION_REASONS
            self.add("Motifs de refus", ok, f"{len(REJECTION_REASONS)} motifs: {', '.join(REJECTION_REASONS)}")
        except Exception as e:
            self.add("Motifs de refus", False, str(e))

    # ─── Cleanup ─────────────────────────────────────────────────

    def cleanup(self):
        self.log("\n--- Nettoyage complet ---", "TEST")
        errors = []

        # 1. Supprimer les salariés créés par le test
        for emp_id in self._created_employee_ids:
            try:
                supabase.table("employees").delete().eq("id", emp_id).execute()
                self.log(f"  Salarié supprimé: {emp_id[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Salarié {emp_id[:8]}: {e}")

        # 2. Supprimer les entretiens (participants supprimés en cascade)
        for iid in self._created_interview_ids:
            try:
                supabase.table("recruitment_interviews").delete().eq("id", iid).execute()
                self.log(f"  Entretien supprimé: {iid[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Entretien {iid[:8]}: {e}")

        # 3. Supprimer opinions
        for oid in self._created_opinion_ids:
            try:
                supabase.table("recruitment_opinions").delete().eq("id", oid).execute()
                self.log(f"  Avis supprimé: {oid[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Avis {oid[:8]}: {e}")

        # 4. Supprimer notes
        for nid in self._created_note_ids:
            try:
                supabase.table("recruitment_notes").delete().eq("id", nid).execute()
                self.log(f"  Note supprimée: {nid[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Note {nid[:8]}: {e}")

        # 5. Supprimer timeline events (par candidats)
        for cid in self._created_candidate_ids:
            try:
                supabase.table("recruitment_timeline_events").delete().eq("candidate_id", cid).execute()
            except Exception:
                pass

        # 6. Supprimer candidats (timeline supprimée en cascade normalement)
        for cid in self._created_candidate_ids:
            try:
                supabase.table("recruitment_candidates").delete().eq("id", cid).execute()
                self.log(f"  Candidat supprimé: {cid[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Candidat {cid[:8]}: {e}")

        # 7. Supprimer pipeline stages puis le job
        for jid in self._created_job_ids:
            try:
                supabase.table("recruitment_pipeline_stages").delete().eq("job_id", jid).execute()
                supabase.table("recruitment_jobs").delete().eq("id", jid).execute()
                self.log(f"  Job + pipeline supprimé: {jid[:8]}...", "SUCCESS")
            except Exception as e:
                errors.append(f"Job {jid[:8]}: {e}")

        if errors:
            self.add("Nettoyage", False, f"{len(errors)} erreur(s): {'; '.join(errors)}")
        else:
            self.add("Nettoyage", True, "Toutes les données de test supprimées")

    # ─── Run ─────────────────────────────────────────────────────

    def run_all(self):
        self.log("=" * 70, "INFO")
        self.log("TESTS MODULE RECRUTEMENT (sans connexion, services + DB)", "TEST")
        self.log("=" * 70, "INFO")

        if not self.setup_context():
            return

        self.run_all_tests()

        total = len(self.results)
        success = sum(1 for r in self.results if r.success)
        failed = total - success

        self.log("\n" + "=" * 70, "INFO")
        self.log("RÉSUMÉ", "TEST")
        self.log("=" * 70, "INFO")
        self.log(f"Total: {total} | Réussis: {success} | Échoués: {failed}", "INFO")
        if failed > 0:
            self.log("", "INFO")
            self.log("Détail des échecs :", "ERROR")
            for r in self.results:
                if not r.success:
                    self.log(f"  ✗ {r.name}: {r.message}", "ERROR")
        self.log("=" * 70, "INFO")


# ═══════════════════════════════════════════════════════════════════════

def main():
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("❌ Définir SUPABASE_URL et SUPABASE_KEY dans backend_api/.env")
        sys.exit(1)
    tester = RecruitmentTester()
    tester.run_all()
    failed = sum(1 for r in tester.results if not r.success)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
