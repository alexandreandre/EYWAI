"""Lecture des paramètres prime d'ancienneté (entreprise + CCN)."""

from __future__ import annotations

from typing import Any

from app.modules.collective_agreements.rules.prime_calcul import resolve_prime_anciennete_config
from app.modules.collective_agreements.rules.repository import CCRulesRepository
from app.modules.collective_agreements.rules.resolver import code_postal_from_entreprise
from app.modules.companies.infrastructure.repository import company_repository
from app.modules.prime_anciennete_settings.schemas.responses import (
    PrimeAncienneteCcResolved,
    PrimeAncienneteOverrides,
    PrimeAncienneteSettings,
)


def _read_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    pp = settings.get("parametres_paie") or {}
    if not isinstance(pp, dict):
        pp = {}
    raw = pp.get("prime_anciennete") or {}
    return raw if isinstance(raw, dict) else {}


def _resolve_cc_block(
    *,
    idcc: str | None,
    entreprise: dict[str, Any],
    overrides: dict[str, Any],
) -> PrimeAncienneteCcResolved:
    if not idcc:
        return PrimeAncienneteCcResolved()

    row = CCRulesRepository().get_rules_by_idcc(str(idcc))
    rules = (row or {}).get("rules") or {}
    regles_prime = rules.get("prime_anciennete") or {}
    if not regles_prime:
        return PrimeAncienneteCcResolved(idcc=str(idcc))

    resolved = resolve_prime_anciennete_config(regles_prime, entreprise)
    elig = regles_prime.get("eligibilite") or {}
    prorata = resolved.get("prorata") or regles_prime.get("prorata") or {}

    cp = resolved.get("code_postal") or code_postal_from_entreprise(entreprise)
    vp = resolved.get("valeur_point")
    zone_libelle = None
    if vp is not None:
        for zone in regles_prime.get("valeurs_point") or []:
            if not isinstance(zone, dict):
                continue
            try:
                if float(zone.get("valeur")) == float(vp):
                    zone_libelle = zone.get("zone_libelle")
                    break
            except (TypeError, ValueError):
                continue

    enabled = prorata.get("enabled")
    if enabled is None:
        enabled = bool(prorata.get("mode") and prorata.get("mode") != "none")

    min_annees = overrides.get("min_annees_override")
    if min_annees is None:
        try:
            min_annees = float((elig or {}).get("min_annees") or 0)
        except (TypeError, ValueError):
            min_annees = 0.0

    base = (regles_prime.get("base_de_calcul") or {}).get("methode")

    return PrimeAncienneteCcResolved(
        idcc=str(idcc),
        formule=base,
        valeur_point_zone=float(vp) if vp is not None else None,
        zone_libelle=zone_libelle,
        min_annees=float(min_annees),
        statuts_exclus=list((elig or {}).get("statuts_exclus") or []),
        prorata_enabled=bool(enabled),
        prorata_mode=prorata.get("mode") or "none",
    )


def get_prime_anciennete_settings(company_id: str) -> PrimeAncienneteSettings:
    company = company_repository.get_by_id(company_id)
    if not company:
        raise LookupError("Entreprise non trouvée.")

    settings = company.get("settings") or {}
    overrides_raw = _read_overrides(settings)

    cp = company.get("adresse_code_postal") or ""
    entreprise = {
        "identification": {"adresse": {"code_postal": cp}},
        "adresse_code_postal": cp,
        "parametres_paie": {"prime_anciennete": overrides_raw},
    }

    idcc = company.get("idcc")
    cc_resolved = _resolve_cc_block(
        idcc=str(idcc) if idcc else None,
        entreprise=entreprise,
        overrides=overrides_raw,
    )

    return PrimeAncienneteSettings(
        overrides=PrimeAncienneteOverrides(
            valeur_point_override=overrides_raw.get("valeur_point_override"),
            min_annees_override=overrides_raw.get("min_annees_override"),
            prorata_mode_override=overrides_raw.get("prorata_mode_override"),
        ),
        cc_resolved=cc_resolved,
        code_postal=cp or None,
    )


def get_prime_anciennete_overrides_for_payslip(company_id: str) -> dict[str, Any]:
    """Retourne le bloc prime_anciennete pour entreprise.json (génération bulletin)."""
    company = company_repository.get_by_id(company_id)
    if not company:
        return {}
    settings = company.get("settings") or {}
    return _read_overrides(settings)
