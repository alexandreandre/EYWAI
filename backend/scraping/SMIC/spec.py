"""Spécification orchestrateur SMIC."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from core.cotisation_helpers import equal_sections_keys
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import (
    normalize_smic_sections,
    smic_hourly_rate,
    validate_smic_sections,
    ValidationResult,
)

_DIR = Path(__file__).resolve().parent


def _extract_sig(payload: dict) -> dict:
    # La date d'effet suit la signature (elle date le palier de l'historique) ;
    # `_equal` ne la compare pas.
    sections = payload.get("sections", {})
    skip = {"source"}
    raw = {
        k: v
        for k, v in sections.items()
        if k not in skip and (k != "annee" or v is not None)
    }
    return normalize_smic_sections(raw)


def _equal(a: dict, b: dict) -> bool:
    a_n = normalize_smic_sections(a)
    b_n = normalize_smic_sections(b)
    if not equal_sections_keys(
        {"h": smic_hourly_rate(a_n)},
        {"h": smic_hourly_rate(b_n)},
        ["h"],
        abs_tol=0.01,
    ):
        return False
    for key in ("jeune_17_ans", "jeune_moins_17_ans", "smic_mensuel_brut"):
        va, vb = a_n.get(key), b_n.get(key)
        if va is None and vb is None:
            continue
        if not equal_sections_keys({key: va}, {key: vb}, [key], abs_tol=0.02):
            return False
    return True


def _validate(sig: dict) -> ValidationResult:
    full = {**sig}
    if "annee" not in full:
        from core.year_utils import current_year

        full["annee"] = current_year()
    return validate_smic_sections(full)


def _date_d_effet(sig: dict, courant: dict, annee: int) -> str:
    """Date du palier : celle de la source, sinon le 1er janvier d'une année
    nouvelle (revalorisation annuelle), sinon le jour du relevé."""
    try:
        return date.fromisoformat(str(sig.get("effective_from"))[:10]).isoformat()
    except ValueError:
        pass
    try:
        annee_courante = int(courant.get("annee"))
    except (TypeError, ValueError):
        annee_courante = None
    if annee_courante is not None and annee > annee_courante:
        return date(annee, 1, 1).isoformat()
    return date.today().isoformat()


def _build(sig: dict, current_row: Optional[dict]) -> dict:
    """Le barème à écrire : les taux relevés, et l'historique gardé.

    L'historique porte un palier par revalorisation (date d'effet, SMIC
    horaire). La réduction générale y lit le SMIC du 1er janvier de l'année du
    bulletin, et un bulletin d'un mois passé le SMIC de ce mois : le réécrire
    sans lui effacerait 2026 au premier SMIC de 2027. Un SMIC inchangé n'ajoute
    pas de palier (le barème reste identique, aucune revue n'est déposée).
    """
    from core.year_utils import current_year

    out = normalize_smic_sections(
        {
            k: v
            for k, v in sig.items()
            if k not in ("smic_horaire", "effective_from", "source")
        }
    )
    out["annee"] = current_year()

    courant = (current_row or {}).get("config_data") or {}
    if not isinstance(courant, dict):
        courant = {}
    historique = [dict(p) for p in courant.get("historique") or [] if isinstance(p, dict)]
    taux = smic_hourly_rate(out)
    if taux is not None:
        debut = _date_d_effet(sig, courant, out["annee"])
        historique = [p for p in historique if str(p.get("date_debut"))[:10] != debut]
        precedent = max(historique, key=lambda p: str(p.get("date_debut")), default=None)
        if precedent is None or smic_hourly_rate(precedent) != taux:
            historique.append({"date_debut": debut, "cas_general": taux})
    out["historique"] = sorted(historique, key=lambda p: str(p.get("date_debut")))
    return out


SPEC = RateSpec(
    scraper_name="SMIC",
    config_key="smic",
    scripts=[
        ScraperScript("SMIC.py", str(_DIR / "SMIC.py"), blocking=True),
        ScraperScript("SMIC_AI.py", str(_DIR / "SMIC_AI.py"), blocking=False),
    ],
    extract_signature=_extract_sig,
    signatures_equal=_equal,
    validate_signature=_validate,
    build_config_data=_build,
    persistence_mode=PersistenceMode.FULL,
    comment="Mise à jour automatique: smic",
    primary_label="SMIC.py",
    script_timeout=180,
)
