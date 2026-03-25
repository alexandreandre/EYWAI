"""
Règles métier pures pour collective_agreements.

Sans dépendance à FastAPI, DB ou infrastructure. Comportement identique au legacy.
"""

from __future__ import annotations

from typing import Any, List


def idcc_variants(idcc_raw: str) -> List[str]:
    """
    Retourne les variantes d'un IDCC pour la recherche dans convention_classifications.
    Ordre : brut, sans zéros en tête, zfill(4).
    """
    raw = (idcc_raw or "").strip()
    second = (raw.lstrip("0") or "0") if raw else ""
    return [raw, second, raw.zfill(4)]


def build_catalog_update_dict(update_dict_raw: dict[str, Any]) -> dict[str, Any]:
    """
    Construit le dictionnaire de mise à jour catalogue à partir d'un model_dump(exclude_unset=True).
    - Champs PDF (rules_pdf_path, rules_pdf_filename) : on garde la valeur y compris None.
    - Autres champs : on ignore les None (pas de mise à jour).
    """
    update_dict: dict[str, Any] = {}
    for k, v in update_dict_raw.items():
        if k in ("rules_pdf_path", "rules_pdf_filename"):
            update_dict[k] = v
        elif v is not None:
            update_dict[k] = v
    return update_dict


def generate_upload_path(filename: str) -> str:
    """
    Génère un chemin unique pour l'upload d'un PDF catalogue.
    Format : catalog/{iso_datetime}-{uuid_hex}{extension}
    """
    from datetime import datetime
    from uuid import uuid4
    import os

    _root, ext = os.path.splitext(filename)
    unique = f"{datetime.now().isoformat()}-{uuid4().hex}{ext}"
    return f"catalog/{unique}"
