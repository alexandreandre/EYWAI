"""Export PDF — planning hebdomadaire collaborateur."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _shift_label(shift: Dict[str, Any]) -> str:
    st = shift.get("shift_type") or {}
    label = st.get("label") if isinstance(st, dict) else None
    if label:
        return str(label)
    return f"{shift.get('start_time', '')} – {shift.get('end_time', '')}"


def generate_employee_week_planning_pdf(planning: Dict[str, Any]) -> bytes:
    """Génère un PDF lisible à partir du payload get_my_planning_week."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    story: List[Any] = []

    ws = planning.get("week_start")
    we = planning.get("week_end")
    status = planning.get("status") or ""
    if hasattr(ws, "isoformat"):
        ws = ws.isoformat()
    if hasattr(we, "isoformat"):
        we = we.isoformat()

    story.append(Paragraph("Mon planning — semaine", styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            f"Période : {ws} au {we} — statut : {status}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    shifts: List[Dict[str, Any]] = planning.get("shifts") or []
    if not shifts:
        story.append(
            Paragraph("Aucun créneau publié pour cette semaine.", styles["Normal"])
        )
    else:
        rows = [["Date", "Horaires", "Type / poste", "Lieu"]]
        for s in sorted(
            shifts,
            key=lambda x: (str(x.get("shift_date") or ""), str(x.get("start_time") or "")),
        ):
            sd = s.get("shift_date")
            if hasattr(sd, "isoformat"):
                sd = sd.isoformat()
            rows.append(
                [
                    str(sd or ""),
                    f"{s.get('start_time', '')} – {s.get('end_time', '')}",
                    _shift_label(s),
                    str(s.get("location") or s.get("post") or "—"),
                ]
            )
        table = Table(rows, colWidths=[3 * cm, 4 * cm, 5 * cm, 4 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return buffer.getvalue()
