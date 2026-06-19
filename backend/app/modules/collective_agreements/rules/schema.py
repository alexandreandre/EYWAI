"""Schéma JSON v1 et modèles Pydantic pour les règles CC paie."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.collective_agreements.rules.constants import (
    BASE_CALCUL_METHODS,
    CONFIDENCE_LEVELS,
    PRORATA_MODES,
    SANS_POINTAGE_POLICIES,
    SCHEMA_VERSION,
    ZONE_TYPES,
)


def normalize_base_calcul_methode(value: Optional[str]) -> Optional[str]:
    """Normalise les libellés IA (ex. « valeur de point » → valeur_du_point)."""
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    normalized = (
        raw.replace(" ", "_")
        .replace("'", "")
        .replace("-", "_")
        .replace("é", "e")
        .replace("è", "e")
    )
    aliases = {
        "valeur_de_point": "valeur_du_point",
        "valeur_du_point": "valeur_du_point",
        "point": "valeur_du_point",
        "salaire_minimum_conventionnel": "salaire_minimum_conventionnel",
        "minimum_conventionnel": "salaire_minimum_conventionnel",
        "pourcentage_salaire_de_base": "pourcentage_salaire_de_base",
        "pourcentage_du_salaire_de_base": "pourcentage_salaire_de_base",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in BASE_CALCUL_METHODS:
        return normalized
    # Libellés IA verbeux (ex. « valeur de point multiplié par le taux en pourcentage »)
    if "valeur" in raw and "point" in raw:
        return "valeur_du_point"
    if "minimum" in raw and "conventionnel" in raw:
        return "salaire_minimum_conventionnel"
    if "pourcentage" in raw or ("salaire" in raw and "base" in raw):
        return "pourcentage_salaire_de_base"
    if "metallurgie" in raw and "prime" in raw:
        return "metallurgie_prime_anciennete"
    return None


def parse_base_calcul_safe(raw: Any) -> Optional[BaseCalculPrime]:
    """Parse base_de_calcul en ignorant les méthodes IA non reconnues."""
    if not isinstance(raw, dict):
        return None
    try:
        return BaseCalculPrime(**raw)
    except Exception:
        methode = normalize_base_calcul_methode(raw.get("methode"))
        valeur = raw.get("valeur")
        if methode is None and valeur is None:
            return None
        try:
            return BaseCalculPrime(methode=methode, valeur=valeur)
        except Exception:
            return None


class PalierAnciennete(BaseModel):
    annees_min: float
    taux: float


class BaseCalculPrime(BaseModel):
    methode: Optional[str] = None
    valeur: Optional[float] = None

    @field_validator("methode")
    @classmethod
    def validate_methode(cls, v: Optional[str]) -> Optional[str]:
        normalized = normalize_base_calcul_methode(v)
        if normalized is not None and normalized not in BASE_CALCUL_METHODS:
            raise ValueError(f"methode invalide: {v}")
        return normalized


class PrimeAncienneteEligibilite(BaseModel):
    min_annees: float = 0.0
    statuts_exclus: list[str] = Field(default_factory=list)
    classe_max_taux: int = 10


class PrimeAncienneteProrata(BaseModel):
    enabled: bool = False
    mode: Literal["heures_contrat", "jours_forfait", "none"] = "heures_contrat"
    inclure_heures_sup: bool = True
    maladie_si_maintien: bool = True
    sans_pointage_policy: Literal["plein_mois", "zero"] = "plein_mois"
    ratio_plafond: Optional[float] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in PRORATA_MODES:
            return "heures_contrat"
        return v

    @field_validator("sans_pointage_policy")
    @classmethod
    def validate_sans_pointage(cls, v: str) -> str:
        if v not in SANS_POINTAGE_POLICIES:
            return "plein_mois"
        return v


class ValeurPointZone(BaseModel):
    zone_type: Literal["national", "regional", "departemental", "local", "inconnu"] = (
        "inconnu"
    )
    zone_libelle: str = ""
    departements: list[str] = Field(default_factory=list)
    valeur: float

    @field_validator("zone_type")
    @classmethod
    def validate_zone_type(cls, v: str) -> str:
        if v not in ZONE_TYPES:
            return "inconnu"
        return v


class PrimeAnciennete(BaseModel):
    bareme: list[PalierAnciennete] = Field(default_factory=list)
    base_de_calcul: Optional[BaseCalculPrime] = None
    taux_par_classe: Optional[dict[str, float]] = None
    eligibilite: Optional[PrimeAncienneteEligibilite] = None
    prorata: Optional[PrimeAncienneteProrata] = None
    valeurs_point: list[ValeurPointZone] = Field(default_factory=list)


class CpAncienneteTier(BaseModel):
    category: Literal["ouvrier_etam", "cadre", "forfait", "all"]
    min_years: float
    days: float
    min_age: Optional[float] = None
    max_years: Optional[float] = None


class CpAnciennete(BaseModel):
    """Congés payés supplémentaires d'ancienneté (jours, distinct de prime_anciennete)."""

    mode: Literal["tier_total", "cumulative_rules"] = "tier_total"
    seniority_reference: str = "cp_period_end"
    tiers: list[CpAncienneteTier] = Field(default_factory=list)


class SalaireMinimum(BaseModel):
    coefficient: float
    valeur: float
    libelle: Optional[str] = None


class GrilleSalaires(BaseModel):
    """Grille de minima pour une zone géographique ou un accord local."""

    zone_type: Literal["national", "regional", "departemental", "local", "inconnu"] = (
        "inconnu"
    )
    zone_libelle: str = ""
    departements: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    date_effet: Optional[str] = None
    source_titre: Optional[str] = None
    minima: list[SalaireMinimum] = Field(default_factory=list)

    @field_validator("zone_type")
    @classmethod
    def validate_zone_type(cls, v: str) -> str:
        if v not in ZONE_TYPES:
            return "inconnu"
        return v


class CompletudeExtraction(BaseModel):
    niveau: Literal["partiel", "complet", "inconnu"] = "inconnu"
    avertissements: list[str] = Field(default_factory=list)
    grilles_count: int = 0
    idcc_multi_zones: bool = False


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
    cp_anciennete: Optional[CpAnciennete] = None
    salaires_minima: list[SalaireMinimum] = Field(default_factory=list)
    grilles_salaires: list[GrilleSalaires] = Field(default_factory=list)
    completude: Optional[CompletudeExtraction] = None
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

_GRILLE_SALAIRES_SCHEMA = {
    "type": "object",
    "properties": {
        "zone_type": {
            "type": "string",
            "enum": sorted(ZONE_TYPES),
        },
        "zone_libelle": {"type": "string"},
        "departements": {
            "type": "array",
            "items": {"type": "string"},
        },
        "regions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "date_effet": {"type": ["string", "null"]},
        "source_titre": {"type": ["string", "null"]},
        "minima": {
            "type": "array",
            "items": _SALAIRE_MINIMUM_SCHEMA,
        },
    },
    "required": [
        "zone_type",
        "zone_libelle",
        "departements",
        "regions",
        "date_effet",
        "source_titre",
        "minima",
    ],
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
        "grilles_salaires": {
            "type": "array",
            "items": _GRILLE_SALAIRES_SCHEMA,
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
        "grilles_salaires",
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
        base = parse_base_calcul_safe(base_raw)
        taux_raw = prime_raw.get("taux_par_classe")
        taux_par_classe = None
        if isinstance(taux_raw, dict):
            taux_par_classe = {
                str(k): float(v) for k, v in taux_raw.items() if v is not None
            }
        elig_raw = prime_raw.get("eligibilite")
        elig = (
            PrimeAncienneteEligibilite(**elig_raw)
            if isinstance(elig_raw, dict)
            else None
        )
        prorata_raw = prime_raw.get("prorata")
        prorata = (
            PrimeAncienneteProrata(**prorata_raw)
            if isinstance(prorata_raw, dict)
            else None
        )
        vp_list = [
            ValeurPointZone(**v)
            for v in prime_raw.get("valeurs_point", [])
            if isinstance(v, dict)
        ]
        prime = PrimeAnciennete(
            bareme=bareme,
            base_de_calcul=base,
            taux_par_classe=taux_par_classe or None,
            eligibilite=elig,
            prorata=prorata,
            valeurs_point=vp_list,
        )

    minima = [
        SalaireMinimum(**m)
        for m in data.get("salaires_minima", [])
        if isinstance(m, dict)
    ]
    grilles = [
        GrilleSalaires(**g)
        for g in data.get("grilles_salaires", [])
        if isinstance(g, dict)
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
        grilles_salaires=grilles,
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
        if doc.prime_anciennete.taux_par_classe:
            prime_dict["taux_par_classe"] = dict(doc.prime_anciennete.taux_par_classe)
        if doc.prime_anciennete.eligibilite:
            prime_dict["eligibilite"] = doc.prime_anciennete.eligibilite.model_dump()
        if doc.prime_anciennete.prorata:
            prime_dict["prorata"] = doc.prime_anciennete.prorata.model_dump()
        if doc.prime_anciennete.valeurs_point:
            prime_dict["valeurs_point"] = [
                {
                    "zone_type": v.zone_type,
                    "zone_libelle": v.zone_libelle,
                    "departements": v.departements,
                    "valeur": v.valeur,
                }
                for v in doc.prime_anciennete.valeurs_point
            ]
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
    if doc.grilles_salaires:
        out["grilles_salaires"] = [
            {
                "zone_type": g.zone_type,
                "zone_libelle": g.zone_libelle,
                "departements": g.departements,
                "regions": g.regions,
                **({"date_effet": g.date_effet} if g.date_effet else {}),
                **({"source_titre": g.source_titre} if g.source_titre else {}),
                "minima": [
                    {
                        "coefficient": m.coefficient,
                        "valeur": m.valeur,
                        **({"libelle": m.libelle} if m.libelle else {}),
                    }
                    for m in g.minima
                ],
            }
            for g in doc.grilles_salaires
        ]
    if doc.cp_anciennete:
        out["cp_anciennete"] = {
            "mode": doc.cp_anciennete.mode,
            "seniority_reference": doc.cp_anciennete.seniority_reference,
            "tiers": [
                {
                    "category": t.category,
                    "min_years": t.min_years,
                    "days": t.days,
                    **({"min_age": t.min_age} if t.min_age is not None else {}),
                    **({"max_years": t.max_years} if t.max_years is not None else {}),
                }
                for t in doc.cp_anciennete.tiers
            ],
        }
    if doc.completude:
        out["completude"] = doc.completude.model_dump()
    if doc.meta:
        out["meta"] = doc.meta.model_dump()
    return out
