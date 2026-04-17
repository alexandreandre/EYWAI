"""Lecture compétences, évaluations, matrice."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.modules.competencies.infrastructure.repository import competencies_repository
from app.modules.competencies.schemas.responses import (
    CompetencyMatrix,
    CompetencyRef,
    EmployeeCompetency,
    MatrixCell,
)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def competency_ref_from_row(row: Dict[str, Any]) -> CompetencyRef:
    r = dict(row)
    rl = r.get("required_level")
    return CompetencyRef(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        name=str(r.get("name") or ""),
        category=str(r.get("category") or ""),
        description=r.get("description"),
        required_level=int(rl) if rl is not None else None,
        status=str(r.get("status") or "active"),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
    )


def employee_competency_from_row(row: Dict[str, Any]) -> EmployeeCompetency:
    r = dict(row)
    return EmployeeCompetency(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        employee_id=str(r["employee_id"]),
        competency_id=str(r["competency_id"]),
        score=int(r.get("score") or 0),
        evaluation_date=_parse_date(r.get("evaluation_date")) or date.today(),
        evaluated_by=str(r["evaluated_by"]) if r.get("evaluated_by") else None,
        comment=r.get("comment"),
        created_at=_parse_dt(r.get("created_at")),
        competency_name=r.get("_competency_name"),
        competency_category=r.get("_competency_category"),
        required_level=int(r["_required_level"]) if r.get("_required_level") is not None else None,
        employee_name=r.get("_employee_name"),
        is_gap=bool(r.get("_is_gap")),
    )


def get_competency_refs(
    company_id: str, include_archived: bool = False
) -> List[CompetencyRef]:
    rows = competencies_repository.get_all_refs(company_id, include_archived)
    return [competency_ref_from_row(x) for x in rows]


def get_competency_ref(ref_id: str, company_id: str) -> Optional[CompetencyRef]:
    row = competencies_repository.get_ref_by_id(ref_id, company_id)
    return competency_ref_from_row(row) if row else None


def get_evaluations(
    company_id: str,
    employee_id: Optional[str] = None,
    competency_id: Optional[str] = None,
) -> List[EmployeeCompetency]:
    rows = competencies_repository.get_all_evaluations(
        company_id, employee_id=employee_id, competency_id=competency_id
    )
    return [employee_competency_from_row(x) for x in rows]


def get_latest_evaluations(
    company_id: str, employee_id: Optional[str] = None
) -> List[EmployeeCompetency]:
    rows = competencies_repository.get_latest_evaluations(company_id, employee_id)
    return [employee_competency_from_row(x) for x in rows]


def get_matrix(
    company_id: str,
    service_id: Optional[str] = None,
    category: Optional[str] = None,
) -> CompetencyMatrix:
    payload = competencies_repository.get_matrix_payload(company_id, service_id, category)
    cells = [MatrixCell(**c) for c in payload["cells"]]
    gaps = [MatrixCell(**c) for c in payload["gaps"]]
    gap_cids = list({g.competency_id for g in gaps})
    tmap = competencies_repository.get_trainings_by_competency_ids(company_id, gap_cids)
    gap_trainings: List[dict] = []
    for cid in gap_cids:
        t = tmap.get(cid)
        if t:
            gap_trainings.append(
                {
                    "competency_id": cid,
                    "training_id": str(t.get("id")),
                    "training_title": str(t.get("title") or ""),
                }
            )
    return CompetencyMatrix(
        employees=payload["employees"],
        competencies=payload["competencies"],
        cells=cells,
        gaps=gaps,
        gap_trainings=gap_trainings,
    )
