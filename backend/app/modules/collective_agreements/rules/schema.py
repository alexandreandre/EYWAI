"""Schéma JSON v1 et modèles Pydantic pour les règles CC paie."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.collective_agreements.rules.constants import (
    BASE_CALCUL_METHODS,
    CONFIDENCE_LEVELS,
    SCHEMA_VERSION,
)


class PalierAnciennete(BaseModel):
    annees_min: float
    taux: float


class BaseCalculPrime(BaseModel):
    methode: Optional[str] = None
    valeur: Optional[float] = None

    @field_validator("methode")
    @classmethod
    def validate_methode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BASE_CALCUL_METHODS:
            raise ValueError(f"methode invalide: {v}")
        return v


class PrimeAnciennete(BaseModel):
    bareme: list[PalierAnciennete] = Field(default_factory=list)
    base_de_calcul: Optional[BaseCalculPrime] = None


class SalaireMinimum(BaseModel):
    coefficient: float
    valeur: float
    libelle: Optional[str] = None


class Citation(BaseModel):
    article: str
    extrait: str


class RulesMeta(BaseModel):
    extracted_at: str
    model: str
    source_agreement_id: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"
    citations: list[Citation] = Field(default_factory=list)


class CCRulesDocument(BaseModel):
    schema_version: int = SCHEMA_VERSION
    idcc: str
    prime_anciennete: Optional[PrimeAnciennete] = None
    salaires_minima: list[SalaireMinimum] = Field(default_factory=list)
    meta: Optional[RulesMeta] = None


# --- JSON Schema pour OpenRouter (strict mode) ---

_PALIER_SCHEMA = {
    "type": "object",
    "properties": {
        "annees_min": {"type": "number"},
        "taux": {"type": "number"},
    },
    "required": ["annees_min", "taux"],
    "additionalProperties": False,
}

_SALAIRE_MINIMUM_SCHEMA = {
    "type": "object",
    "properties": {
        "coefficient": {"type": "number"},
        "valeur": {"type": "number"},
        "libelle": {"type": ["string", "null"]},
    },
    "required": ["coefficient", "valeur", "libelle"],
    "additionalProperties": False,
}

_CITATION_SCHEMA = {
    "type": "object",
    "properties": {
        "article": {"type": "string"},
        "extrait": {"type": "string"},
    },
    "required": ["article", "extrait"],
    "additionalProperties": False,
}

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "idcc": {"type": "string"},
        "prime_anciennete": {
            "type": ["object", "null"],
            "properties": {
                "bareme": {
                    "type": "array",
                    "items": _PALIER_SCHEMA,
                },
                "base_de_calcul": {
                    "type": ["object", "null"],
                    "properties": {
                        "methode": {"type": ["string", "null"]},
                        "valeur": {"type": ["number", "null"]},
                    },
                    "required": ["methode", "valeur"],
                    "additionalProperties": False,
                },
            },
            "required": ["bareme", "base_de_calcul"],
            "additionalProperties": False,
        },
        "salaires_minima": {
            "type": "array",
            "items": _SALAIRE_MINIMUM_SCHEMA,
        },
        "confidence": {"type": "string", "enum": sorted(CONFIDENCE_LEVELS)},
        "citations": {
            "type": "array",
            "items": _CITATION_SCHEMA,
        },
    },
    "required": [
        "idcc",
        "prime_anciennete",
        "salaires_minima",
        "confidence",
        "citations",
    ],
    "additionalProperties": False,
}

SCOUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "article_references": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["article_references"],
    "additionalProperties": False,
}


def parse_extraction_result(data: dict[str, Any]) -> CCRulesDocument:
    """Convertit la sortie IA brute en document validé Pydantic."""
    prime_raw = data.get("prime_anciennete")
    prime = None
    if isinstance(prime_raw, dict):
        bareme = [
            PalierAnciennete(**p)
            for p in prime_raw.get("bareme", [])
            if isinstance(p, dict)
        ]
        base_raw = prime_raw.get("base_de_calcul")
        base = BaseCalculPrime(**base_raw) if isinstance(base_raw, dict) else None
        prime = PrimeAnciennete(bareme=bareme, base_de_calcul=base)

    minima = [
        SalaireMinimum(**m)
        for m in data.get("salaires_minima", [])
        if isinstance(m, dict)
    ]
    citations = [
        Citation(**c) for c in data.get("citations", []) if isinstance(c, dict)
    ]
    confidence = data.get("confidence", "medium")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "medium"

    return CCRulesDocument(
        schema_version=SCHEMA_VERSION,
        idcc=str(data.get("idcc", "")).strip(),
        prime_anciennete=prime,
        salaires_minima=minima,
        meta=RulesMeta(
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            model="",
            confidence=confidence,  # type: ignore[arg-type]
            citations=citations,
        ),
    )


def document_to_engine_rules(doc: CCRulesDocument) -> dict[str, Any]:
    """Format consommé par le moteur de paie (sans meta)."""
    out: dict[str, Any] = {
        "schema_version": doc.schema_version,
        "idcc": doc.idcc,
    }
    if doc.prime_anciennete:
        prime_dict: dict[str, Any] = {
            "bareme": [
                {"annees_min": p.annees_min, "taux": p.taux}
                for p in doc.prime_anciennete.bareme
            ],
        }
        if doc.prime_anciennete.base_de_calcul:
            base = doc.prime_anciennete.base_de_calcul
            prime_dict["base_de_calcul"] = {
                "methode": base.methode,
                "valeur": base.valeur,
            }
        out["prime_anciennete"] = prime_dict
    if doc.salaires_minima:
        out["salaires_minima"] = [
            {
                "coefficient": m.coefficient,
                "valeur": m.valeur,
                **({"libelle": m.libelle} if m.libelle else {}),
            }
            for m in doc.salaires_minima
        ]
    if doc.meta:
        out["meta"] = doc.meta.model_dump()
    return out
