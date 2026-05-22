"""Schémas de réponse — Analytics Paie."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ItemsAIntegrer(BaseModel):
    ndf: int = 0
    absences: int = 0
    primes: int = 0
    avances: int = 0
    total: int = 0


class PayrollAnalyticsSummary(BaseModel):
    period: str
    statut_cycle: Literal["brouillon", "en_cours", "clos"] = "brouillon"
    nb_bulletins_valides: int = 0
    nb_bulletins_attendus: int = 0
    anomalies_bloquantes: int = 0
    anomalies_warnings: int = 0
    masse_brute: float = 0.0
    cout_employeur_total: float = 0.0
    net_verse: float = 0.0
    effectif_paye: int = 0
    effectif_actif: int = 0
    delta_brut_m1_pct: Optional[float] = None
    delta_cout_m1_pct: Optional[float] = None
    items_a_integrer: ItemsAIntegrer = Field(default_factory=ItemsAIntegrer)
    cycle_closed_at: Optional[str] = None


class PayrollTrendPoint(BaseModel):
    period: str
    masse_brute: float = 0.0
    cotisations_salariales: float = 0.0
    cotisations_patronales: float = 0.0
    net_verse: float = 0.0
    cout_employeur: float = 0.0
    effectif_paye: int = 0
    is_closed: bool = False


class PayrollAnalyticsTrends(BaseModel):
    end_period: str
    months: int
    points: List[PayrollTrendPoint] = Field(default_factory=list)


class PayrollBreakdownItem(BaseModel):
    key: str
    label: str
    masse_brute: float = 0.0
    cout_employeur: float = 0.0
    effectif: int = 0


class PayrollAnalyticsBreakdown(BaseModel):
    period: str
    group_by: Literal["team", "service", "contract_type"]
    items: List[PayrollBreakdownItem] = Field(default_factory=list)
    total_masse_brute: float = 0.0


class PayrollPeriodItem(BaseModel):
    year: int
    month: int
    period: str
    status: Literal["open", "closed", "locked"] = "open"
    closed_at: Optional[str] = None
    closed_by: Optional[str] = None


class PayrollPeriodsResponse(BaseModel):
    year: int
    periods: List[PayrollPeriodItem] = Field(default_factory=list)
