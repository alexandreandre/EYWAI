"""Notifications e-mail après génération d'exports (dispatch, planifications)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.core.logging import get_logger
from app.modules.exports.application import service as export_service
from app.modules.exports.infrastructure.storage import (
    create_signed_url,
    download_export_file,
)
from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

logger = get_logger("modules.exports.notifications")

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
EMAIL_LINK_EXPIRES_SEC = 7 * 24 * 3600

CHANNEL_LABELS = {
    "compta": "Comptabilité",
    "banque": "Banque",
}


@dataclass
class NotifyResult:
    status: str  # sent, partial, skipped_no_smtp, skipped_no_recipients
    sent_count: int = 0
    failed_count: int = 0
    message: str = ""


def _guess_mime(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".xml"):
        return "application/xml"
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".zip"):
        return "application/zip"
    return "application/octet-stream"


def _collect_export_files(
    company_id: str, export_ids: Sequence[str]
) -> tuple[list[tuple[str, bytes, str]], list[tuple[str, str]]]:
    """Retourne (pièces jointes, liens de secours filename+url)."""
    attachments: list[tuple[str, bytes, str]] = []
    link_fallbacks: list[tuple[str, str]] = []

    for export_id in export_ids:
        try:
            for file_info in export_service.get_export_download_files(company_id, export_id):
                path_entry = file_info.get("path")
                filename = str(file_info.get("filename") or "export")
                if path_entry:
                    try:
                        content = download_export_file(str(path_entry))
                        if len(content) <= MAX_ATTACHMENT_BYTES:
                            attachments.append(
                                (filename, content, _guess_mime(filename))
                            )
                            continue
                    except Exception:
                        logger.debug(
                            "Pièce jointe indisponible pour %s, bascule lien",
                            filename,
                            exc_info=True,
                        )
                link_fallbacks.append(
                    (filename, str(file_info.get("download_url") or ""))
                )
        except Exception:
            logger.exception("Collecte fichiers export %s échouée", export_id)

    return attachments, link_fallbacks


def _build_email_bodies(
    *,
    company_name: str,
    period: str,
    export_type_label: str,
    channel: Optional[str],
    link_fallbacks: Sequence[tuple[str, str]],
) -> tuple[str, str]:
    channel_part = ""
    if channel:
        channel_part = f" ({CHANNEL_LABELS.get(channel, channel)})"

    text_lines = [
        "Bonjour,",
        "",
        f"Un export{channel_part} a été généré pour {company_name or 'votre entreprise'}.",
        f"Période : {period}",
        f"Type : {export_type_label}",
        "",
    ]
    if link_fallbacks:
        text_lines.append("Fichiers (liens de téléchargement) :")
        for name, url in link_fallbacks:
            if url:
                text_lines.append(f"- {name} : {url}")
        text_lines.append("")
    text_lines.extend(["Cordialement,", "L'équipe EYWAI"])
    text_content = "\n".join(text_lines)

    links_html = ""
    if link_fallbacks:
        items = "".join(
            f'<li><a href="{url}">{name}</a></li>'
            for name, url in link_fallbacks
            if url
        )
        if items:
            links_html = f"<p>Fichiers disponibles en ligne :</p><ul>{items}</ul>"

    html_content = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
  <p>Bonjour,</p>
  <p>Un export{channel_part} a été généré pour <strong>{company_name or 'votre entreprise'}</strong>.</p>
  <ul>
    <li><strong>Période :</strong> {period}</li>
    <li><strong>Type :</strong> {export_type_label}</li>
  </ul>
  {links_html}
  <p>Cordialement,<br>L'équipe EYWAI</p>
</body></html>
"""
    return text_content, html_content


def notify_export_recipients(
    company_id: str,
    recipients: Sequence[str],
    export_ids: Sequence[str],
    *,
    export_type_label: str = "Export",
    period: str = "",
    channel: Optional[str] = None,
    company_name: str = "",
) -> NotifyResult:
    """Envoie les fichiers générés aux destinataires configurés."""
    clean = [r.strip() for r in recipients if r and str(r).strip()]
    if not clean:
        return NotifyResult(
            status="skipped_no_recipients",
            message="Aucun destinataire configuré.",
        )

    from app.modules.platform_settings.application.email_config import (
        get_resolved_email_config,
    )

    if not get_resolved_email_config().is_configured:
        return NotifyResult(
            status="skipped_no_smtp",
            message="SMTP non configuré — fichiers générés mais e-mail non envoyé.",
        )

    attachments, link_fallbacks = _collect_export_files(company_id, export_ids)
    if not attachments and not link_fallbacks:
        for export_id in export_ids:
            try:
                for file_info in export_service.get_export_download_files(
                    company_id, export_id
                ):
                    url = str(file_info.get("download_url") or "")
                    name = str(file_info.get("filename") or "export")
                    if url:
                        link_fallbacks.append((name, url))
            except Exception:
                continue

    subject_channel = f" — {CHANNEL_LABELS.get(channel, channel)}" if channel else ""
    subject = f"[EYWAI] Export {export_type_label}{subject_channel} — {period}"
    text_content, html_content = _build_email_bodies(
        company_name=company_name,
        period=period,
        export_type_label=export_type_label,
        channel=channel,
        link_fallbacks=link_fallbacks,
    )

    sender = get_smtp_mail_sender()
    ok, err = sender.send_email_with_attachments(
        clean,
        subject,
        text_content,
        html_content,
        attachments,
        require_delivery=False,
    )
    if ok:
        return NotifyResult(
            status="sent",
            sent_count=len(clean),
            message=f"E-mail envoyé à {len(clean)} destinataire(s).",
        )
    return NotifyResult(
        status="partial",
        failed_count=len(clean),
        message=err or "Échec partiel de l'envoi e-mail.",
    )


def signed_links_for_exports(
    company_id: str, export_ids: Sequence[str], *, expires_sec: int = EMAIL_LINK_EXPIRES_SEC
) -> list[tuple[str, str]]:
    """Génère des liens signés longue durée pour le corps d'e-mail."""
    links: list[tuple[str, str]] = []
    for export_id in export_ids:
        try:
            exp = export_service.get_export_download_files(company_id, export_id)
            for f in exp:
                path = f.get("path")
                name = str(f.get("filename") or "export")
                if path:
                    links.append((name, create_signed_url(str(path), expires_sec)))
                elif f.get("download_url"):
                    links.append((name, str(f["download_url"])))
        except Exception:
            continue
    return links
