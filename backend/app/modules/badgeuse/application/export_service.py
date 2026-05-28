"""Exports CSV badgeuse."""
from __future__ import annotations

from app.modules.badgeuse.application.deps import deps
from app.modules.badgeuse.application._internals import *  # noqa: F403
def build_company_summary_csv(
    *,
    company_id: str,
    start: date,
    end: date,
    employee_ids: Iterable[str] | None = None,
) -> Tuple[str, str]:
    """
    Construit le CSV de synthèse badgeuse pour une entreprise sur une période.
    Retourne (filename, contenu_csv).
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    rows = deps.time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=list(employee_ids) if employee_ids else None,
    )

    grouped: Dict[str, Dict[date, List[TimeEntry]]] = {}
    for row in rows:
        emp_id = str(row["employee_id"])
        ts = datetime.fromisoformat(row["timestamp"])
        d = ts.date()
        grouped.setdefault(emp_id, {}).setdefault(d, []).append(
            deps.time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        )

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "employe_id",
            "date",
            "total_heures",
            "nombre_sequences",
            "anomalie",
        ]
    )

    for emp_id, days in grouped.items():
        for d, entries in sorted(days.items(), key=lambda x: x[0]):
            summary = deps.compute_day_summary(entries)
            total_hours = summary.total_duration.total_seconds() / 3600.0
            writer.writerow(
                [
                    emp_id,
                    d.isoformat(),
                    f"{total_hours:.2f}",
                    len(summary.sequences),
                    "oui" if summary.anomalies else "non",
                ]
            )

    output.seek(0)
    filename = f"badgeuse_{company_id}_{start.isoformat()}_{end.isoformat()}.csv"
    return filename, output.read()
