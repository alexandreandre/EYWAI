from __future__ import annotations


def resolve_effective_seconds(
    computed_seconds: int, accounted_seconds: int | None
) -> int:
    """Heures effectives : override RH si présent, sinon brut pointages."""
    if accounted_seconds is not None:
        return accounted_seconds
    return computed_seconds


def has_accounting_override(accounted_seconds: int | None) -> bool:
    return accounted_seconds is not None


def override_differs_from_computed(
    computed_seconds: int, accounted_seconds: int | None
) -> bool:
    return (
        accounted_seconds is not None and accounted_seconds != computed_seconds
    )
