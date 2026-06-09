"""Constantes métier OETH."""

from __future__ import annotations

BOETH_CODES = frozenset(
    {"01", "02", "03", "04", "05", "06", "07", "08", "09", "11", "12"}
)

EXTERNAL_TYPES = frozenset({"01", "02", "03", "04"})

DEDUCTION_TYPES = frozenset({"060", "061", "062", "063", "064"})

SEUIL_ASSUJETTISSEMENT = 20

DEFAULT_OETH_CONFIG: dict = {
    "actif": True,
    "taux_obligation": 0.06,
    "taux_obligation_mayotte": 0.05,
    "seuil_assujettissement": 20,
    "coefficients": {
        "20_249": 400,
        "250_749": 500,
        "750_plus": 600,
        "surcontribution": 1500,
    },
    "boeth_50_plus_factor": 1.5,
    "ecap_deduction_factor": 17,
    "neutralisation_years": 5,
    "surcontribution_years": 3,
}
