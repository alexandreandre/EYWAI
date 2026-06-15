"""Validation NIR / SIRET partagée (export DSN et import DSN)."""

from __future__ import annotations

from typing import Optional, Tuple


def _clean_digits(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.replace(" ", "").replace("-", "").replace(".", "")


def validate_nir(nir: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Valide un NIR complet (15 chiffres avec clé)."""
    if not nir:
        return False, "NIR manquant"
    nir_clean = _clean_digits(nir)
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


def validate_nir_dsn(nir: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Valide un NIR tel que déclaré en DSN (13 chiffres sans clé, ou 15 avec clé).
    La DSN ne déclare en général que les 13 premiers chiffres (S21.G00.30.001).
    """
    if not nir:
        return False, "NIR manquant"
    nir_clean = _clean_digits(nir)
    if not nir_clean.isdigit():
        return False, "NIR invalide : doit contenir uniquement des chiffres"
    if len(nir_clean) == 15:
        return validate_nir(nir_clean)
    if len(nir_clean) == 13:
        if nir_clean[0] not in ("1", "2"):
            return False, "NIR invalide : doit commencer par 1 ou 2"
        return True, None
    return (
        False,
        f"NIR invalide : attendu 13 ou 15 chiffres (actuellement {len(nir_clean)})",
    )


def normalize_nir_for_storage(nir: Optional[str]) -> str:
    """Normalise pour stockage (13 chiffres DSN conservés tels quels)."""
    return _clean_digits(nir)


def build_siret_from_siren_nic(siren: Optional[str], nic: Optional[str]) -> str:
    siren_clean = _clean_digits(siren)
    nic_clean = _clean_digits(nic)
    if len(siren_clean) == 9 and nic_clean:
        return siren_clean + nic_clean.zfill(5)[:5]
    return ""


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
