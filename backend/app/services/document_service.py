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
from app.modules.document_library.schemas.requests import CLIENT_TEMPLATE_ONLY_TYPES
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
        PDF ReportLab de secours si aucune conversion docx/html n'a abouti.
        Rédige un document structuré plutôt qu'une simple liste de variables.
        """
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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
        dt_title = document_type.replace("_", " ").strip().capitalize()
        prenom = variables.get("prenom", "")
        nom = variables.get("nom", "")
        poste = variables.get("poste", "")
        type_ct = variables.get("type_contrat", "")
        deb = variables.get("date_debut_contrat", "")
        salaire = variables.get("salaire_brut_mensuel", "")
        siret = (variables.get("siret") or "").strip()
        adresse_e = variables.get("adresse_entreprise", "")
        date_gen = variables.get("date_generation", "")
        lieu = variables.get("signature_lieu", "")

        header_line = f"<b>{esc(nom_e or 'Entreprise')}</b>"
        if siret:
            header_line += f"<br/>SIRET : {esc(siret)}"
        if adresse_e:
            header_line += f"<br/>{esc(adresse_e)}"

        corps_parts = [
            f"Nous soussignés, <b>{esc(nom_e or 'Entreprise')}</b>, attestons que "
            f"<b>{esc(prenom)} {esc(nom)}</b>"
        ]
        if poste:
            corps_parts.append(f" est employé(e) en qualité de <b>{esc(poste)}</b>")
        if deb:
            corps_parts.append(f" depuis le <b>{esc(deb)}</b>")
        if type_ct:
            corps_parts.append(f" en contrat <b>{esc(type_ct)}</b>")
        corps_parts.append(".")
        if salaire:
            corps_parts.append(
                f" Rémunération brute mensuelle : <b>{esc(salaire)}</b>."
            )
        corps_parts.append(
            " Le présent document est établi pour servir et valoir ce que de droit."
        )
        corps_html = "".join(corps_parts)

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
            fontSize=11,
            leading=16,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#334155"),
        )
        small_style = ParagraphStyle(
            name="FbSmall",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_LEFT,
        )
        story: List[Any] = []
        story.append(Paragraph(header_line, body_style))
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(esc(dt_title), title_style))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(corps_html, body_style))
        story.append(Spacer(1, 1.2 * cm))
        story.append(
            Paragraph(
                f"Fait à {esc(lieu or '…………………')}, le {esc(date_gen)}.",
                small_style,
            )
        )
        story.append(Spacer(1, 1.5 * cm))
        signatory = variables.get("nom_signataire_rh") or "Le service RH"
        qual = variables.get("qualite_signataire_rh") or ""
        sig = f"<b>{esc(signatory)}</b>"
        if qual:
            sig += f"<br/><i>{esc(qual)}</i>"
        sig += "<br/><i>Signature</i>"
        story.append(Paragraph(sig, body_style))
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph(
                f"<i>Document généré automatiquement le {esc(date_gen)} — modèle EYWAI</i>",
                ParagraphStyle(
                    name="FbFooter",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=colors.HexColor("#9ca3af"),
                    alignment=TA_CENTER,
                ),
            )
        )
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
        persist: bool = True,
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
        docx_bytes: Optional[bytes] = None
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
                if not pdf_bytes and document_type in CLIENT_TEMPLATE_ONLY_TYPES:
                    raise ValueError(
                        "La conversion du modèle Word en PDF a échoué. "
                        "Vérifiez le fichier ou contactez le support."
                    )
                if pdf_bytes:
                    docx_bytes = docx_result
            elif file_format == "html":
                html_src = file_bytes.decode("utf-8", errors="replace")
                html_out = document_engine.inject_html(html_src, variables)
                pdf_bytes = document_engine.html_to_pdf(html_out)
            else:
                is_eywai_template = True
                pdf_bytes = None
                template_id = None
                template_version_id = None

        if not pdf_bytes and document_type in frozenset({"cdi", "cdd"}):
            try:
                from app.shared.infrastructure.pdf import generate_contract_pdf

                contract_type = document_type.upper()
                employee_for_contract = dict(employee_data)
                employee_for_contract.setdefault(
                    "contract_type", contract_type
                )
                pdf_bytes = generate_contract_pdf(
                    employee_data=employee_for_contract,
                    company_data=company_data,
                    logo_path="",
                )
                is_eywai_template = True
                template_id = None
                template_version_id = None
                try:
                    from app.shared.infrastructure.pdf.contract_docx import (
                        generate_contract_docx,
                    )

                    docx_bytes = generate_contract_docx(
                        employee_data=employee_for_contract,
                        company_data=company_data,
                    )
                except Exception as e:
                    logger.warning("generate_contract_docx (bibliothèque): %s", e)
            except Exception as e:
                logger.warning("generate_contract_pdf (bibliothèque): %s", e)
                pdf_bytes = None

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

        if not pdf_bytes and document_type.startswith("avenant"):
            try:
                from app.shared.infrastructure.pdf import generate_avenant_pdf

                pdf_bytes = generate_avenant_pdf(
                    employee_data=employee_data,
                    company_data=company_data,
                    context=ctx,
                    logo_path="",
                )
                is_eywai_template = True
                template_id = None
                template_version_id = None
                try:
                    from app.shared.infrastructure.pdf.avenant_docx import (
                        generate_avenant_docx,
                    )

                    docx_bytes = generate_avenant_docx(
                        employee_data=employee_data,
                        company_data=company_data,
                        context=ctx,
                    )
                except Exception as e:
                    logger.warning("generate_avenant_docx (bibliothèque): %s", e)
            except Exception as e:
                logger.warning("generate_avenant_pdf (bibliothèque): %s", e)
                pdf_bytes = None

        if (
            not pdf_bytes
            and document_type in CLIENT_TEMPLATE_ONLY_TYPES
            and not tpl_bundle
        ):
            if document_type == "fiche_poste":
                raise ValueError(
                    "Aucun modèle de fiche de poste configuré — importez un fichier "
                    "dans la bibliothèque de documents."
                )
            if document_type in ("bulletin_participation", "bulletin_interessement"):
                raise ValueError(
                    "Aucun modèle de bulletin d'option configuré — importez un fichier "
                    "dans la bibliothèque de documents."
                )
            raise ValueError(
                "Aucun modèle personnalisé configuré pour ce type de document."
            )

        if not pdf_bytes and document_type in CLIENT_TEMPLATE_ONLY_TYPES and tpl_bundle:
            raise ValueError(
                "La génération du document a échoué avec le modèle importé."
            )

        if not pdf_bytes and (is_eywai_template or tpl_bundle is not None):
            if document_type in CLIENT_TEMPLATE_ONLY_TYPES:
                raise ValueError(
                    "La génération du document a échoué avec le modèle importé."
                )
            try:
                fb = self._generate_fallback_pdf(document_type, variables)
                if fb:
                    pdf_bytes = fb
                    is_eywai_template = True
                    template_id = None
                    template_version_id = None
            except Exception as e:
                logger.warning("ReportLab fallback PDF (EYWAI): %s", e)

        if not pdf_bytes:
            raise ValueError("Impossible de générer le document PDF.")

        if not persist:
            return {
                "pdf_bytes": pdf_bytes,
                "docx_bytes": docx_bytes,
                "is_eywai_template": is_eywai_template,
                "document_type": document_type,
                "template_id": template_id,
                "template_version_id": template_version_id,
            }

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

        docx_file_url_db: Optional[str] = None
        docx_file_name_db: Optional[str] = None

        if docx_bytes:
            docx_filename = f"{safe_type}_{ts}.docx"
            docx_storage_path = f"{company_id}/{employee_id}/{docx_filename}"
            try:
                supabase.storage.from_(BUCKET_GENERATED).upload(
                    docx_storage_path,
                    docx_bytes,
                    {
                        "content-type": (
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document"
                        )
                    },
                )
                docx_file_url_db = docx_storage_path
                docx_file_name_db = docx_filename
            except Exception as e:
                logger.warning("Upload docx generated_documents: %s", e)

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
            "docx_file_url": docx_file_url_db,
            "docx_file_name": docx_file_name_db,
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
