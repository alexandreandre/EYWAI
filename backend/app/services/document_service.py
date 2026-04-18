"""
Service central Documents : résolution template, fusion, PDF, traçabilité generated_documents.

Le bucket Storage `generated_documents` doit exister (privé) ; optionnel `document_templates`
pour les chemins relatifs dans document_template_versions.file_url.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from app.core.database import supabase
from app.services.common_attestation_generator import common_attestation_generator
from app.services.document_engine import document_engine
from app.services.document_variables import build_variables

logger = logging.getLogger(__name__)

BUCKET_GENERATED = "generated_documents"
BUCKET_DOC_TEMPLATES = "document_templates"

_ALLOWED_STATUS = frozenset({"brouillon", "envoye", "signe", "archive"})


def _exec_data(resp: Any) -> Any:
    if not resp:
        return None
    return resp.data if hasattr(resp, "data") else None


def _exec_list(resp: Any) -> List[Dict[str, Any]]:
    data = _exec_data(resp)
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


class DocumentService:
    """Orchestration templates Supabase + moteur + persistance."""

    def get_active_template(
        self,
        company_id: str,
        document_type: str,
    ) -> Optional[Dict[str, Any]]:
        t_resp = (
            supabase.table("document_templates")
            .select("*")
            .eq("company_id", company_id)
            .eq("document_type", document_type)
            .eq("status", "active")
            .eq("is_default", True)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        template = _exec_data(t_resp)
        if not template:
            return None

        tid = template["id"]
        v_resp = (
            supabase.table("document_template_versions")
            .select("*")
            .eq("template_id", tid)
            .order("version", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        version = _exec_data(v_resp)
        if not version:
            return None

        file_url = version.get("file_url") or ""
        file_format = (version.get("file_format") or "").lower().strip()
        file_bytes = self._download_template_file(file_url)
        if not file_bytes:
            logger.warning(
                "Téléchargement template impossible company=%s type=%s file_url=%s",
                company_id,
                document_type,
                file_url[:120] if file_url else "",
            )
            return None

        return {
            "template": template,
            "version": version,
            "file_bytes": file_bytes,
            "file_format": file_format,
        }

    def get_template_bundle_by_id(
        self, company_id: str, template_id: str
    ) -> Optional[Dict[str, Any]]:
        """Charge un modèle client précis (entreprise + actif) avec sa dernière version."""
        t_resp = (
            supabase.table("document_templates")
            .select("*")
            .eq("id", template_id)
            .eq("company_id", company_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        template = _exec_data(t_resp)
        if not template:
            return None
        tid = template["id"]
        v_resp = (
            supabase.table("document_template_versions")
            .select("*")
            .eq("template_id", tid)
            .order("version", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        version = _exec_data(v_resp)
        if not version:
            return None
        file_url = version.get("file_url") or ""
        file_format = (version.get("file_format") or "").lower().strip()
        file_bytes = self._download_template_file(file_url)
        if not file_bytes:
            return None
        return {
            "template": template,
            "version": version,
            "file_bytes": file_bytes,
            "file_format": file_format,
        }

    def _download_template_file(self, file_url: str) -> Optional[bytes]:
        if not file_url:
            return None
        url = file_url.strip()
        if url.lower().startswith("http://") or url.lower().startswith("https://"):
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                return r.content
            except requests.RequestException as e:
                logger.warning("HTTP download template: %s", e)
                return None
        try:
            raw = supabase.storage.from_(BUCKET_DOC_TEMPLATES).download(url)
            return bytes(raw) if raw is not None else None
        except Exception as e:
            logger.warning("Storage download template path=%s: %s", url, e)
            return None

    def _generate_fallback_pdf(self, document_type: str, variables: Dict[str, str]) -> bytes:
        """
        PDF minimal ReportLab (variables injectées) si aucune conversion docx/html n’a abouti.
        Utilisé pour le rendu « modèle EYWAI » de secours.
        """
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        def esc(x: str) -> str:
            t = x or ""
            return (
                t.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        nom_e = (variables.get("nom_entreprise") or "").strip()
        dt_title = document_type.replace("_", " ").title()
        if nom_e:
            title_text = f"{nom_e} — {dt_title}"
        else:
            title_text = dt_title

        siret = (variables.get("siret") or "").strip()
        header_line = f"<b>{esc(nom_e or 'Entreprise')}</b>"
        if siret:
            header_line += f"<br/>SIRET : {esc(siret)}"

        body_keys = (
            "prenom",
            "nom",
            "poste",
            "date_debut_contrat",
            "salaire_brut_mensuel",
            "type_contrat",
            "duree_hebdomadaire",
            "nom_entreprise",
            "siret",
        )
        lines_html = []
        for k in body_keys:
            lab = k.replace("_", " ").title()
            val = variables.get(k, "") or ""
            lines_html.append(f"<b>{esc(lab)} :</b> {esc(val)}")

        date_gen = (variables.get("date_generation") or "").strip()
        footer = f"<i>Date de génération : {esc(date_gen)}</i>"

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="FbTitle",
            parent=styles["Heading1"],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=14,
            textColor=colors.HexColor("#1e293b"),
        )
        body_style = ParagraphStyle(
            name="FbBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#334155"),
        )
        story: List[Any] = []
        story.append(Paragraph(header_line, body_style))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(esc(title_text), title_style))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("<br/>".join(lines_html), body_style))
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(footer, body_style))
        doc.build(story)
        return buf.getvalue()

    def generate_document(
        self,
        company_id: str,
        employee_id: str,
        document_type: str,
        category: str,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        generated_by: Optional[str] = None,
        template_id_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        ctx = context or {}
        if template_id_override:
            tpl_bundle = self.get_template_bundle_by_id(company_id, template_id_override)
        else:
            tpl_bundle = self.get_active_template(company_id, document_type)
        variables = build_variables(employee_data, company_data, ctx)

        template_id: Optional[str] = None
        template_version_id: Optional[str] = None
        is_eywai_template = True
        pdf_bytes: Optional[bytes] = None
        file_format = ""

        if tpl_bundle:
            file_format = tpl_bundle["file_format"]
            file_bytes: bytes = tpl_bundle["file_bytes"]
            template_id = tpl_bundle["template"]["id"]
            template_version_id = tpl_bundle["version"]["id"]
            is_eywai_template = False

            if file_format == "docx":
                docx_result = document_engine.inject_docx(file_bytes, variables)
                pdf_bytes = document_engine.docx_to_pdf(docx_result)
            elif file_format == "html":
                html_src = file_bytes.decode("utf-8", errors="replace")
                html_out = document_engine.inject_html(html_src, variables)
                pdf_bytes = document_engine.html_to_pdf(html_out)
            else:
                is_eywai_template = True
                pdf_bytes = None
                template_id = None
                template_version_id = None

        if not pdf_bytes and document_type in frozenset(
            common_attestation_generator.ATTESTATION_TYPES
        ):
            try:
                pdf_bytes = common_attestation_generator.generate(
                    document_type, employee_data, company_data, ctx
                )
                is_eywai_template = True
                template_id = None
                template_version_id = None
            except Exception as e:
                logger.warning("CommonAttestationGenerator: %s", e)
                pdf_bytes = None

        if not pdf_bytes and (is_eywai_template or tpl_bundle is not None):
            try:
                fb = self._generate_fallback_pdf(document_type, variables)
                if fb:
                    pdf_bytes = fb
                    is_eywai_template = True
                    template_id = None
                    template_version_id = None
            except Exception as e:
                logger.warning("ReportLab fallback PDF (EYWAI): %s", e)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_type = re.sub(r"[^\w\-]+", "_", document_type)[:80]
        filename = f"{safe_type}_{ts}.pdf"
        storage_path = f"{company_id}/{employee_id}/{filename}"

        file_url_db: Optional[str] = None
        file_name_db: Optional[str] = None

        if pdf_bytes:
            supabase.storage.from_(BUCKET_GENERATED).upload(
                storage_path,
                pdf_bytes,
                {"content-type": "application/pdf"},
            )
            file_url_db = storage_path
            file_name_db = filename

        row = {
            "company_id": company_id,
            "employee_id": employee_id,
            "document_type": document_type,
            "category": category,
            "template_id": template_id,
            "template_version_id": template_version_id,
            "is_eywai_template": is_eywai_template,
            "file_url": file_url_db,
            "file_name": file_name_db,
            "status": "brouillon",
            "generation_context": ctx,
            "generated_by": generated_by,
        }

        ins = supabase.table("generated_documents").insert(row).execute()
        rows = _exec_list(ins)
        if not rows:
            raise RuntimeError("Échec insertion generated_documents")
        doc_id = rows[0]["id"]

        signed_file_url = ""
        if file_url_db:
            try:
                sur = supabase.storage.from_(BUCKET_GENERATED).create_signed_url(
                    file_url_db, 3600
                )
                if sur:
                    signed_file_url = sur.get("signedURL") or sur.get("signedUrl") or ""
            except Exception as e:
                logger.warning("Signed URL generated_documents: %s", e)
                signed_file_url = file_url_db

        return {
            "document_id": str(doc_id),
            "file_url": signed_file_url or (file_url_db or ""),
            "is_eywai_template": is_eywai_template,
            "document_type": document_type,
            "status": "brouillon",
        }

    def get_documents(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("generated_documents").select("*").eq("company_id", company_id)
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if document_type:
            q = q.eq("document_type", document_type)
        if status:
            q = q.eq("status", status)
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)
        resp = q.order("created_at", desc=True).execute()
        rows = _exec_list(resp)

        emp_ids = list({r["employee_id"] for r in rows if r.get("employee_id")})
        names: Dict[str, tuple[str, str]] = {}
        for eid in emp_ids:
            er = (
                supabase.table("employees")
                .select("id, first_name, last_name")
                .eq("id", eid)
                .maybe_single()
                .execute()
            )
            ed = _exec_data(er)
            if ed:
                names[eid] = (ed.get("first_name") or "", ed.get("last_name") or "")
        for r in rows:
            eid = r.get("employee_id")
            fn, ln = names.get(eid, ("", "")) if eid else ("", "")
            r["employee_first_name"] = fn
            r["employee_last_name"] = ln

        return rows

    def update_status(
        self,
        document_id: str,
        company_id: str,
        status: str,
    ) -> Dict[str, Any]:
        if status not in _ALLOWED_STATUS:
            raise ValueError(f"Statut invalide: {status}")

        upd = (
            supabase.table("generated_documents")
            .update({"status": status})
            .eq("id", document_id)
            .eq("company_id", company_id)
            .execute()
        )
        rows = _exec_list(upd)
        if not rows:
            raise LookupError("Document non trouvé ou non mis à jour")
        return rows[0]

    def trace_existing_document(
        self,
        company_id: str,
        employee_id: str,
        document_type: str,
        category: str,
        file_url: str,
        file_name: str,
        is_eywai_template: bool = True,
        generation_context: Optional[Dict[str, Any]] = None,
        generated_by: Optional[str] = None,
    ) -> str:
        """
        Trace un PDF déjà stocké (ex. bucket exit_documents) dans generated_documents.
        Retourne l'id inséré (str) ou chaîne vide si échec (ne lève pas).
        """
        ctx = generation_context if generation_context is not None else {}
        row: Dict[str, Any] = {
            "company_id": company_id,
            "employee_id": employee_id,
            "document_type": document_type,
            "category": category,
            "template_id": None,
            "template_version_id": None,
            "is_eywai_template": is_eywai_template,
            "file_url": file_url,
            "file_name": file_name,
            "status": "brouillon",
            "generation_context": ctx,
            "generated_by": generated_by,
        }
        try:
            ins = supabase.table("generated_documents").insert(row).execute()
            rows = _exec_list(ins)
            if rows and rows[0].get("id"):
                return str(rows[0]["id"])
            logger.warning("trace_existing_document: insert sans id retourné")
            return ""
        except Exception as e:
            logger.warning("trace_existing_document: %s", e)
            return ""

    def delete_generated_document(self, document_id: str, sb: Any = None) -> None:
        """Supprime une ligne generated_documents (ex. stub sans fichier). Ne lève pas."""
        client = sb if sb is not None else supabase
        try:
            client.table("generated_documents").delete().eq("id", document_id).execute()
        except Exception as e:
            logger.warning("delete_generated_document: %s", e)


document_service = DocumentService()
