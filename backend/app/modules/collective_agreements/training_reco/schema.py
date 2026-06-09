"""Schéma JSON pour l'extraction des formations conventionnelles."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ObligationLevel = Literal["obligatoire", "recommandee"]


class CcTrainingRecommendationItem(BaseModel):
    title: str
    obligation_level: ObligationLevel = "recommandee"
    pedagogical_objective: Optional[str] = None
    legal_reference: Optional[str] = None
    target_roles: list[str] = Field(default_factory=list)
    periodicity: Optional[str] = None


class CcTrainingExtractionDocument(BaseModel):
    idcc: str
    formations: list[CcTrainingRecommendationItem] = Field(default_factory=list)


EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "idcc": {"type": "string"},
        "formations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "obligation_level": {
                        "type": "string",
                        "enum": ["obligatoire", "recommandee"],
                    },
                    "pedagogical_objective": {"type": ["string", "null"]},
                    "legal_reference": {"type": ["string", "null"]},
                    "target_roles": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "periodicity": {"type": ["string", "null"]},
                },
                "required": [
                    "title",
                    "obligation_level",
                    "pedagogical_objective",
                    "legal_reference",
                    "target_roles",
                    "periodicity",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["idcc", "formations"],
    "additionalProperties": False,
}


def parse_extraction_result(data: dict[str, Any], *, expected_idcc: str) -> CcTrainingExtractionDocument:
    doc = CcTrainingExtractionDocument.model_validate(data)
    if not doc.idcc:
        doc.idcc = expected_idcc
    cleaned: list[CcTrainingRecommendationItem] = []
    seen: set[str] = set()
    for item in doc.formations:
        title = (item.title or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            CcTrainingRecommendationItem(
                title=title,
                obligation_level=item.obligation_level
                if item.obligation_level in ("obligatoire", "recommandee")
                else "recommandee",
                pedagogical_objective=(item.pedagogical_objective or "").strip() or None,
                legal_reference=(item.legal_reference or "").strip() or None,
                target_roles=[str(x).strip() for x in item.target_roles if str(x).strip()],
                periodicity=(item.periodicity or "").strip() or None,
            )
        )
    return CcTrainingExtractionDocument(idcc=expected_idcc, formations=cleaned)
