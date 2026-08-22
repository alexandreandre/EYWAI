"""Exports CSV badgeuse."""
from __future__ import annotations

from app.shared.domain.temps_local import date_locale, fenetre_jour_local

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
    start_dt = fenetre_jour_local(start)[0]
    end_dt = fenetre_jour_local(end)[1]
    rows = deps.time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=list(employee_ids) if employee_ids else None,
    )

    accounting_map = deps.day_accounting_repository.get_for_company_between(
        company_id=company_id,
        start=start,
        end=end,
        employee_ids=list(employee_ids) if employee_ids else None,
    )

    grouped: Dict[str, Dict[date, List[TimeEntry]]] = {}
    for row in rows:
        emp_id = str(row["employee_id"])
        ts = datetime.fromisoformat(row["timestamp"])
        d = date_locale(ts)
        grouped.setdefault(emp_id, {}).setdefault(d, []).append(
            deps.time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        )

    for (emp_id, d), _ in accounting_map.items():
        grouped.setdefault(emp_id, {}).setdefault(d, [])

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "employe_id",
            "date",
            "heures_brutes",
            "heures_comptabilisees",
            "heures_effectives",
            "override",
            "nombre_sequences",
            "anomalie",
        ]
    )

    for emp_id, days in grouped.items():
        for d, entries in sorted(days.items(), key=lambda x: x[0]):
            if entries:
                summary = deps.compute_day_summary(entries)
                computed = summary.total_duration.total_seconds()
                sequences = len(summary.sequences)
                has_anomaly = bool(summary.anomalies)
            else:
                computed = 0.0
                sequences = 0
                has_anomaly = False
            accounted = accounting_map.get((emp_id, d))
            effective = deps.resolve_effective_seconds(int(computed), accounted)
            brut_h = computed / 3600.0
            effective_h = effective / 3600.0
            compt_h = (
                accounted / 3600.0 if accounted is not None else effective_h
            )
            writer.writerow(
                [
                    emp_id,
                    d.isoformat(),
                    f"{brut_h:.2f}",
                    f"{compt_h:.2f}" if accounted is not None else "",
                    f"{effective_h:.2f}",
                    "oui" if accounted is not None else "non",
                    sequences,
                    "oui" if has_anomaly else "non",
                ]
            )

    output.seek(0)
    filename = f"badgeuse_{company_id}_{start.isoformat()}_{end.isoformat()}.csv"
    return filename, output.read()
