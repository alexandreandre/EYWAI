"""Seuils intelligents multi-tiers pour le backtest paie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Set


KNOWN_GAP_FIELDS: FrozenSet[str] = frozenset(
    {
        "cumul_heures",
        "cumul_brut",
        "cumul_h_sup",
        "journee_solidarite",
        "cumuls_annuels",
        "code_naf",
        "date_paiement",
    }
)


@dataclass
class TierConfig:
    floor_eur: float
    pct: float = 0.0


@dataclass
class ThresholdConfig:
    tier_s: TierConfig = field(default_factory=lambda: TierConfig(floor_eur=0.01))
    tier_a: TierConfig = field(default_factory=lambda: TierConfig(floor_eur=0.02))
    tier_b: TierConfig = field(default_factory=lambda: TierConfig(floor_eur=0.02, pct=0.02))
    tier_c: TierConfig = field(default_factory=lambda: TierConfig(floor_eur=0.50, pct=0.10))
    rounding_base_eur: float = 0.01
    rounding_per_line_eur: float = 0.005
    systemic_min_employees: int = 3
    systemic_delta_match_eur: float = 0.01
    human_alert_tier_s_eur: float = 1.00
    max_correction_attempts: int = 3
    max_iterations: int = 12
    plateau_stop_after: int = 2
    known_gap_fields: Set[str] = field(default_factory=lambda: set(KNOWN_GAP_FIELDS))

    def tolerance(self, tier: str, reference_value: float | None = None) -> float:
        cfg = {
            "S": self.tier_s,
            "A": self.tier_a,
            "B": self.tier_b,
            "C": self.tier_c,
        }.get(tier, self.tier_c)
        ref = abs(reference_value or 0.0)
        relative = (cfg.pct / 100.0) * ref if ref > 0 else 0.0
        return max(cfg.floor_eur, relative)

    def aggregate_rounding_budget(self, line_count: int) -> float:
        return self.rounding_base_eur + self.rounding_per_line_eur * max(line_count, 0)


def default_thresholds() -> ThresholdConfig:
    return ThresholdConfig()


FIELD_TIERS: dict[str, str] = {
    "salaire_brut": "S",
    "net_a_payer": "S",
    "net_imposable": "S",
    "montant_net_social": "S",
    "net_avant_impot": "S",
    "pas_montant": "S",
    "pas_taux": "S",
    "salaire_base": "A",
    "heures_sup": "A",
    "prime_anciennete": "A",
    "prime_exceptionnelle": "A",
    "participation": "A",
    "total_cotisations_salariales": "B",
    "total_cotisations_patronales": "B",
    "cout_total_employeur": "C",
    "reduction_generale": "C",
    "cumuls_annuels": "C",
}
