"""Validation NIR / SIRET partagée (export DSN et import DSN)."""

from __future__ import annotations

from typing import Optional, Tuple


def validate_nir(nir: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not nir:
        return False, "NIR manquant"
    nir_clean = nir.replace(" ", "").replace("-", "").replace(".", "")
    if len(nir_clean) != 15:
        return (
            False,
            f"NIR invalide : doit contenir 15 chiffres (actuellement {len(nir_clean)})",
        )
    if not nir_clean.isdigit():
        return False, "NIR invalide : doit contenir uniquement des chiffres"
    try:
        nir_digits = [int(d) for d in nir_clean[:13]]
        key = int(nir_clean[13:15])
        total = sum(nir_digits[i] * (2 if i % 2 == 0 else 1) for i in range(13))
        calculated_key = 97 - (total % 97)
        if calculated_key != key:
            return False, "NIR invalide : clé de contrôle incorrecte"
        return True, None
    except (ValueError, IndexError):
        return False, "NIR invalide : format incorrect"
    return True, None


def validate_siret(siret: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not siret:
        return False, "SIRET manquant"
    siret_clean = siret.replace(" ", "").replace("-", "")
    if len(siret_clean) != 14:
        return (
            False,
            f"SIRET invalide : doit contenir 14 chiffres (actuellement {len(siret_clean)})",
        )
    if not siret_clean.isdigit():
        return False, "SIRET invalide : doit contenir uniquement des chiffres"

    def luhn_check(number: str) -> bool:
        digits = [int(d) for d in number]
        checksum = sum(
            d if i % 2 == 0 else (d * 2 if d < 5 else d * 2 - 9)
            for i, d in enumerate(reversed(digits))
        )
        return checksum % 10 == 0

    if not luhn_check(siret_clean):
        return False, "SIRET invalide : clé de contrôle incorrecte"
    return True, None


def validate_siren(siren: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not siren:
        return False, "SIREN manquant"
    siren_clean = siren.replace(" ", "").replace("-", "")
    if len(siren_clean) != 9:
        return False, f"SIREN invalide : doit contenir 9 chiffres (actuellement {len(siren_clean)})"
    if not siren_clean.isdigit():
        return False, "SIREN invalide : doit contenir uniquement des chiffres"
    return True, None
