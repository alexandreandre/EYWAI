"""
Règles métier du module bonus_types.

- seuil_heures requis si type = selon_heures, interdit sinon (aligné legacy).
- calcul du montant selon le type (montant_fixe / selon_heures) : logique pure, pas de FastAPI.
"""

from __future__ import annotations

from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.domain.value_objects import BonusAmountComputation


def validate_seuil_heures_for_kind(
    kind: BonusTypeKind,
    seuil_heures: float | None,
) -> None:
    """
    Lève ValueError si :
    - kind == SELON_HEURES et seuil_heures est None ;
    - kind != SELON_HEURES et seuil_heures est renseigné.
    """
    if kind == BonusTypeKind.SELON_HEURES:
        if seuil_heures is None:
            raise ValueError("seuil_heures est requis pour le type 'selon_heures'")
    elif seuil_heures is not None:
        raise ValueError(
            "seuil_heures ne doit être renseigné que pour le type 'selon_heures'"
        )


def compute_bonus_amount(
    bonus: BonusType, total_hours: float
) -> BonusAmountComputation:
    """
    Calcule le montant d'une prime à partir du total d'heures réalisées (règle métier pure).

    - montant_fixe : retourne le montant de la prime, pas de seuil.
    - selon_heures : si total_hours >= seuil_heures alors montant, sinon 0.

    Lève ValueError si le type de prime n'est pas supporté.
    """
    if bonus.type == BonusTypeKind.MONTANT_FIXE:
        return BonusAmountComputation(
            amount=float(bonus.montant),
            total_hours=None,
            seuil=None,
            condition_met=None,
        )
    if bonus.type == BonusTypeKind.SELON_HEURES:
        seuil = float(bonus.seuil_heures or 0)
        condition_met = total_hours >= seuil
        amount = float(bonus.montant) if condition_met else 0.0
        return BonusAmountComputation(
            amount=amount,
            total_hours=total_hours,
            seuil=seuil,
            condition_met=condition_met,
        )
    raise ValueError(f"Type de prime non supporté: {bonus.type.value}")
