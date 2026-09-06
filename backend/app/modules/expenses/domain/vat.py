"""Calcul et validation TVA pour les notes de frais."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Taux usuels en France (notes de frais / comptabilité)
STANDARD_VAT_RATES: tuple[float, ...] = (20.0, 10.0, 5.5, 2.1, 0.0)

MIN_VAT_RATE = 0.0
MAX_VAT_RATE = 100.0


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_vat_breakdown(amount_ttc: float, vat_rate: float) -> tuple[float, float]:
    """
    Déduit HT et montant TVA à partir du TTC et du taux (%).
    amount_ttc = amount_ht + vat_amount (arrondi au centime).
    """
    if amount_ttc < 0:
        raise ValueError("Le montant TTC doit être positif ou nul.")
    rate = Decimal(str(vat_rate))
    ttc = Decimal(str(amount_ttc))
    if rate <= 0:
        return _money(ttc), 0.0
    ht = ttc / (Decimal("1") + rate / Decimal("100"))
    ht_money = _money(ht)
    vat_money = _money(ttc - Decimal(str(ht_money)))
    return ht_money, vat_money


def validate_vat_rate(vat_rate: float) -> str | None:
    """Retourne un message d'erreur si le taux est invalide."""
    if vat_rate < MIN_VAT_RATE or vat_rate > MAX_VAT_RATE:
        return f"Le taux de TVA doit être compris entre {MIN_VAT_RATE} et {MAX_VAT_RATE} %."
    return None


# Types de frais hors champ de la TVA (barèmes) : taux TOUJOURS forcé à 0,
# à la création comme à l'édition — source unique de la règle.
VAT_EXEMPT_EXPENSE_TYPES: frozenset[str] = frozenset({"Indemnités kilométriques"})


def taux_tva_effectif(type_value: str | None, vat_rate: float | None) -> float | None:
    """Taux réellement applicable compte tenu du type (exonérations)."""
    if type_value in VAT_EXEMPT_EXPENSE_TYPES:
        return 0.0
    return vat_rate
