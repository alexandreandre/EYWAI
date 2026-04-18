"""
Repository Supabase pour interview_templates, sections et questions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from app.core.database import supabase

from app.modules.interview_templates.schemas.requests import (
    InterviewTemplateCreate,
    InterviewTemplateUpdate,
    QuestionType,
    TemplateQuestionCreate,
    TemplateSectionCreate,
)
from app.modules.interview_templates.schemas.responses import (
    InterviewTemplate,
    TemplateQuestion,
    TemplateSection,
)


def _sort_sections_and_questions(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for s in sections:
        qs = s.get("questions") or []
        s["questions"] = sorted(qs, key=lambda q: (q.get("position") or 0, q.get("id") or ""))
    return sorted(sections, key=lambda s: (s.get("position") or 0, s.get("id") or ""))


def _template_row_to_model(
    row: Dict[str, Any], sections: List[Dict[str, Any]]
) -> InterviewTemplate:
    sections_sorted = _sort_sections_and_questions(sections)
    sec_models: List[TemplateSection] = []
    for s in sections_sorted:
        q_models = [
            TemplateQuestion(
                id=str(q["id"]),
                section_id=str(q["section_id"]),
                label=q.get("label") or "",
                question_type=q.get("question_type") or "text",
                options=q.get("options"),
                is_required=bool(q.get("is_required", False)),
                is_self_evaluation=bool(q.get("is_self_evaluation", False)),
                position=int(q.get("position") or 0),
            )
            for q in (s.get("questions") or [])
        ]
        sec_models.append(
            TemplateSection(
                id=str(s["id"]),
                template_id=str(s["template_id"]),
                title=s.get("title") or "",
                position=int(s.get("position") or 0),
                questions=q_models,
            )
        )
    return InterviewTemplate(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        name=row.get("name") or "",
        interview_type=row["interview_type"],
        status=row.get("status") or "active",
        created_by=row.get("created_by"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
        sections=sec_models,
    )


def _fetch_sections_and_questions(template_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Retourne template_id -> liste de sections avec clé 'questions'."""
    out: Dict[str, List[Dict[str, Any]]] = {tid: [] for tid in template_ids}
    if not template_ids:
        return out

    sec_resp = (
        supabase.table("interview_template_sections")
        .select("*")
        .in_("template_id", template_ids)
        .execute()
    )
    sections = list(sec_resp.data or [])
    section_ids = [str(s["id"]) for s in sections]
    questions_by_section: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in section_ids}
    if section_ids:
        q_resp = (
            supabase.table("interview_template_questions")
            .select("*")
            .in_("section_id", section_ids)
            .execute()
        )
        for q in list(q_resp.data or []):
            sid = str(q["section_id"])
            if sid in questions_by_section:
                questions_by_section[sid].append(dict(q))

    for s in sections:
        sid = str(s["id"])
        tid = str(s["template_id"])
        s_dict = dict(s)
        s_dict["questions"] = questions_by_section.get(sid, [])
        if tid in out:
            out[tid].append(s_dict)
    return out


class SupabaseInterviewTemplateRepository:
    """Accès DB aux modèles de trames d'entretien."""

    def get_all(self, company_id: str) -> List[InterviewTemplate]:
        t_resp = (
            supabase.table("interview_templates")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = list(t_resp.data or [])
        if not rows:
            return []
        tids = [str(r["id"]) for r in rows]
        nested = _fetch_sections_and_questions(tids)
        return [_template_row_to_model(dict(r), nested.get(str(r["id"]), [])) for r in rows]

    def get_by_id(self, template_id: str, company_id: str) -> Optional[InterviewTemplate]:
        t_resp = (
            supabase.table("interview_templates")
            .select("*")
            .eq("id", template_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = t_resp.data if t_resp.data else None
        if not row:
            return None
        nested = _fetch_sections_and_questions([str(row["id"])])
        return _template_row_to_model(dict(row), nested.get(str(row["id"]), []))

    def _delete_sections_questions(self, template_id: str) -> None:
        sec_resp = (
            supabase.table("interview_template_sections")
            .select("id")
            .eq("template_id", template_id)
            .execute()
        )
        for s in list(sec_resp.data or []):
            sid = str(s["id"])
            supabase.table("interview_template_questions").delete().eq(
                "section_id", sid
            ).execute()
        supabase.table("interview_template_sections").delete().eq(
            "template_id", template_id
        ).execute()

    def _insert_sections_questions(
        self, template_id: str, sections: List[Any]
    ) -> None:
        for sec in sections:
            sec_payload = {
                "template_id": template_id,
                "title": sec.title,
                "position": sec.position,
            }
            ins_sec = (
                supabase.table("interview_template_sections")
                .insert(sec_payload)
                .execute()
            )
            if not ins_sec.data:
                raise RuntimeError("Erreur lors de la création d'une section.")
            section_id = str(ins_sec.data[0]["id"])
            for q in sec.questions or []:
                q_payload = {
                    "section_id": section_id,
                    "label": q.label,
                    "question_type": q.question_type,
                    "options": q.options,
                    "is_required": q.is_required,
                    "is_self_evaluation": q.is_self_evaluation,
                    "position": q.position,
                }
                ins_q = (
                    supabase.table("interview_template_questions")
                    .insert(q_payload)
                    .execute()
                )
                if not ins_q.data:
                    raise RuntimeError("Erreur lors de la création d'une question.")

    def create(
        self, company_id: str, data: InterviewTemplateCreate, created_by: str
    ) -> InterviewTemplate:
        ins = (
            supabase.table("interview_templates")
            .insert(
                {
                    "company_id": company_id,
                    "name": data.name,
                    "interview_type": data.interview_type,
                    "status": "active",
                    "created_by": created_by,
                }
            )
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Erreur lors de la création du modèle.")
        template_id = str(ins.data[0]["id"])
        self._insert_sections_questions(template_id, data.sections)
        loaded = self.get_by_id(template_id, company_id)
        if not loaded:
            raise RuntimeError("Erreur lors du rechargement du modèle créé.")
        return loaded

    def update(self, template_id: str, company_id: str, data: InterviewTemplateUpdate) -> InterviewTemplate:
        existing = self.get_by_id(template_id, company_id)
        if not existing:
            raise LookupError("Modèle non trouvé.")

        upd: Dict[str, Any] = {}
        if data.name is not None:
            upd["name"] = data.name
        if data.status is not None:
            upd["status"] = data.status
        if upd:
            u = (
                supabase.table("interview_templates")
                .update(upd)
                .eq("id", template_id)
                .eq("company_id", company_id)
                .execute()
            )
            if not u.data:
                raise RuntimeError("Erreur lors de la mise à jour du modèle.")

        if data.sections is not None:
            self._delete_sections_questions(template_id)
            self._insert_sections_questions(template_id, data.sections)

        loaded = self.get_by_id(template_id, company_id)
        if not loaded:
            raise LookupError("Modèle non trouvé.")
        return loaded

    def archive(self, template_id: str, company_id: str) -> None:
        u = (
            supabase.table("interview_templates")
            .update({"status": "archived"})
            .eq("id", template_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not u.data:
            raise LookupError("Modèle non trouvé.")

    def duplicate(self, template_id: str, company_id: str, created_by: str) -> InterviewTemplate:
        src = self.get_by_id(template_id, company_id)
        if not src:
            raise LookupError("Modèle non trouvé.")
        new_name = f"Copie de {src.name}"
        sections_payload: List[TemplateSectionCreate] = []
        for s in src.sections:
            questions_payload = [
                TemplateQuestionCreate(
                    label=q.label,
                    question_type=cast(QuestionType, q.question_type),
                    options=q.options,
                    is_required=q.is_required,
                    is_self_evaluation=q.is_self_evaluation,
                    position=q.position,
                )
                for q in s.questions
            ]
            sections_payload.append(
                TemplateSectionCreate(
                    title=s.title,
                    position=s.position,
                    questions=questions_payload,
                )
            )
        create_payload = InterviewTemplateCreate(
            name=new_name,
            interview_type=src.interview_type,
            sections=sections_payload,
        )
        return self.create(company_id, create_payload, created_by)

    def count_annual_reviews_using_template(
        self, template_id: str, company_id: str
    ) -> int:
        r = (
            supabase.table("annual_reviews")
            .select("id")
            .eq("template_id", template_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return len(r.data or [])


interview_template_repository = SupabaseInterviewTemplateRepository()
