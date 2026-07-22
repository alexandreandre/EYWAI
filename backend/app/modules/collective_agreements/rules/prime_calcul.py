"""Calcul de la prime d'ancienneté (formules conventionnelles)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional



@dataclass(frozen=True)
class PrimeAncienneteResult:
    base_plein_mois: float
    montant_plein_mois: float
    libelle: str
    meta: dict[str, Any]


def _classification_classe_emploi(contrat: dict[str, Any]) -> Optional[int]:
    cc = contrat.get("remuneration", {}).get("classification_conventionnelle", {})
    if not isinstance(cc, dict):
        return None
    for key in ("classe_emploi", "classe", "coefficient"):
        raw = cc.get(key)
        if raw is not None:
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                continue
    return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def compute_anciennete_annees(
    date_entree: date | str | None,
    date_reference: date,
    *,
    mode: str = "floor",
) -> float:
    """Calcule l'ancienneté en années à partir de la date d'entrée."""
    entree = _parse_date(date_entree)
    if entree is None:
        return 0.0
    delta_days = max(0, (date_reference - entree).days)
    annees = delta_days / 365.25
    if mode == "floor":
        return float(int(annees))
    return round(annees, 2)


def _normalize_statut_label(statut: str) -> str:
    return statut.strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def _statut_exclu(statut: str | None, statuts_exclus: list[str]) -> bool:
    if not statuts_exclus or not statut:
        return False
    statut_n = _normalize_statut_label(statut)
    for exclu in statuts_exclus:
        exclu_n = _normalize_statut_label(str(exclu))
        if not exclu_n:
            continue
        # « Non-cadre » ne doit pas matcher l'exclusion « Cadre ».
        if exclu_n == "cadre":
            if statut_n in ("cadre", "cadres"):
                return True
            continue
        if exclu_n == statut_n:
            return True
    return False


def _eligibilite_config(regles_prime: dict[str, Any]) -> dict[str, Any]:
    raw = regles_prime.get("eligibilite") or {}
    if not isinstance(raw, dict):
        raw = {}
    max_raw = raw.get("max_annees")
    try:
        max_annees = float(max_raw) if max_raw is not None else None
    except (TypeError, ValueError):
        max_annees = None
    return {
        "min_annees": float(raw.get("min_annees") or 0),
        "max_annees": max_annees,
        "statuts_exclus": list(raw.get("statuts_exclus") or []),
        "classe_max_taux": int(raw.get("classe_max_taux") or 10),
    }


def cap_anciennete_annees(
    anciennete_annees: float,
    regles_prime: dict[str, Any],
) -> float:
    """Plafonne les années retenues pour le calcul (ex. métallurgie : 15 ans max)."""
    elig = _eligibilite_config(regles_prime)
    max_annees = elig.get("max_annees")
    if max_annees is not None and max_annees > 0:
        return min(float(anciennete_annees), float(max_annees))
    return anciennete_annees


# Codes de motif de non-éligibilité (stables, contrairement au libellé FR).
MOTIF_ANCIENNETE_INSUFFISANTE = "anciennete_insuffisante"
MOTIF_STATUT_EXCLU = "statut_exclu"
MOTIF_CLASSIFICATION_MANQUANTE = "classification_manquante"


def check_eligibilite_prime_anciennete(
    *,
    regles_prime: dict[str, Any],
    contrat: dict[str, Any],
    anciennete_annees: float,
    statut: str | None = None,
    min_annees_override: float | None = None,
) -> tuple[bool, str | None, str | None]:
    """Retourne (eligible, motif_refus, code_motif)."""
    elig = _eligibilite_config(regles_prime)
    min_annees = (
        float(min_annees_override)
        if min_annees_override is not None
        else elig["min_annees"]
    )
    if anciennete_annees < min_annees:
        return (
            False,
            f"Ancienneté insuffisante ({anciennete_annees:.0f} < {min_annees:.0f} ans)",
            MOTIF_ANCIENNETE_INSUFFISANTE,
        )

    statut_effectif = statut
    if statut_effectif is None:
        statut_effectif = (contrat.get("contrat") or {}).get("statut")
    if _statut_exclu(statut_effectif, elig["statuts_exclus"]):
        return False, "Statut non éligible à la prime d'ancienneté", MOTIF_STATUT_EXCLU

    methode = (regles_prime.get("base_de_calcul") or {}).get("methode")
    taux_par_classe = regles_prime.get("taux_par_classe") or {}
    if methode in ("metallurgie_prime_anciennete",) or (
        methode == "valeur_du_point" and taux_par_classe
    ):
        if _classification_classe_emploi(contrat) is None:
            return (
                False,
                "Classification conventionnelle (classe) manquante",
                MOTIF_CLASSIFICATION_MANQUANTE,
            )

    return True, None, None


def calculer_montant_prime_anciennete(
    *,
    regles_prime: dict[str, Any],
    contrat: dict[str, Any],
    anciennete_annees: float,
    salaire_base_mensuel: float,
    minima_applicables: list[dict[str, Any]],
    valeur_point: float | None = None,
    statut: str | None = None,
    min_annees_override: float | None = None,
) -> tuple[float, float, str] | None:
    """
    Retourne (base_de_calcul, montant_prime, libelle) ou None si non applicable.

    Formule métallurgie (3248) : (valeur_point × taux_classe × 100) × années.
    """
    eligible, _, _ = check_eligibilite_prime_anciennete(
        regles_prime=regles_prime,
        contrat=contrat,
        anciennete_annees=anciennete_annees,
        statut=statut,
        min_annees_override=min_annees_override,
    )
    if not eligible:
        return None

    result = calculer_prime_anciennete_plein_mois(
        regles_prime=regles_prime,
        contrat=contrat,
        anciennete_annees=anciennete_annees,
        salaire_base_mensuel=salaire_base_mensuel,
        minima_applicables=minima_applicables,
        valeur_point=valeur_point,
    )
    if result is None:
        return None
    return result.base_plein_mois, result.montant_plein_mois, result.libelle


def calculer_prime_anciennete_plein_mois(
    *,
    regles_prime: dict[str, Any],
    contrat: dict[str, Any],
    anciennete_annees: float,
    salaire_base_mensuel: float,
    minima_applicables: list[dict[str, Any]],
    valeur_point: float | None = None,
) -> PrimeAncienneteResult | None:
    """Calcule la prime plein mois (avant prorata)."""
    regle_base = regles_prime.get("base_de_calcul") or {}
    methode = regle_base.get("methode")
    taux_par_classe = regles_prime.get("taux_par_classe") or {}
    elig = _eligibilite_config(regles_prime)
    classe_max = elig["classe_max_taux"]
    anciennete_annees = cap_anciennete_annees(anciennete_annees, regles_prime)

    if methode == "metallurgie_prime_anciennete" or (
        methode == "valeur_du_point" and taux_par_classe
    ):
        classe = _classification_classe_emploi(contrat)
        vp = valeur_point if valeur_point is not None else regle_base.get("valeur")
        if classe is None or vp is None:
            return None
        taux_key = str(min(classe, classe_max))
        taux_classe = taux_par_classe.get(taux_key)
        if taux_classe is None:
            taux_classe = taux_par_classe.get(str(classe))
        if taux_classe is None:
            return None
        try:
            vp_f = float(vp)
            taux = float(taux_classe)
        except (TypeError, ValueError):
            return None
        base_specifique = vp_f * taux * 100
        montant = base_specifique * anciennete_annees
        libelle = (
            f"Prime d'ancienneté métallurgie "
            f"({anciennete_annees:.0f} ans, classe {classe}, "
            f"{taux * 100:.2f} %)"
        )
        return PrimeAncienneteResult(
            base_plein_mois=round(base_specifique, 2),
            montant_plein_mois=round(montant, 2),
            libelle=libelle,
            meta={
                "methode": methode,
                "classe": classe,
                "taux_classe": taux,
                "valeur_point": vp_f,
                "annees": anciennete_annees,
            },
        )

    taux_applicable = 0.0
    for palier in regles_prime.get("bareme", []):
        if palier.get("annees_min", 0) <= anciennete_annees:
            taux_applicable = palier.get("taux", 0.0)
    if taux_applicable == 0.0:
        return None

    base_de_calcul = 0.0
    if methode == "salaire_minimum_conventionnel":
        coeff_salarie = (
            contrat.get("remuneration", {})
            .get("classification_conventionnelle", {})
            .get("coefficient")
        )
        for minima in minima_applicables:
            if minima.get("coefficient") == coeff_salarie:
                base_de_calcul = minima.get("valeur", 0.0)
                break
    elif methode == "valeur_du_point":
        coeff_salarie = (
            contrat.get("remuneration", {})
            .get("classification_conventionnelle", {})
            .get("coefficient")
        )
        vp = valeur_point if valeur_point is not None else regle_base.get("valeur")
        if coeff_salarie is not None and vp is not None:
            try:
                base_de_calcul = float(coeff_salarie) * float(vp)
            except (TypeError, ValueError):
                base_de_calcul = 0.0
    elif methode == "pourcentage_salaire_de_base":
        pourcentage = regle_base.get("valeur", 0.0)
        base_de_calcul = salaire_base_mensuel * pourcentage
    else:
        base_de_calcul = salaire_base_mensuel

    if base_de_calcul == 0.0:
        return None

    montant = base_de_calcul * taux_applicable
    libelle = (
        f"Prime d'ancienneté ({anciennete_annees:.0f} ans, "
        f"{taux_applicable * 100:.0f} %)"
    )
    return PrimeAncienneteResult(
        base_plein_mois=round(base_de_calcul, 2),
        montant_plein_mois=round(montant, 2),
        libelle=libelle,
        meta={
            "methode": methode,
            "taux": taux_applicable,
            "annees": anciennete_annees,
        },
    )


def resolve_prime_anciennete_config(
    regles_prime: dict[str, Any],
    entreprise: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fusionne règles CCN et surcharges entreprise (parametres_paie.prime_anciennete)."""
    from app.modules.collective_agreements.rules.resolver import (
        code_postal_from_entreprise,
        resolve_valeur_point,
    )

    entreprise = entreprise or {}
    overrides = (
        (entreprise.get("parametres_paie") or {}).get("prime_anciennete") or {}
    )
    if not isinstance(overrides, dict):
        overrides = {}

    cp = code_postal_from_entreprise(entreprise)
    vp_override = overrides.get("valeur_point_override")
    try:
        vp_override_f = float(vp_override) if vp_override is not None else None
    except (TypeError, ValueError):
        vp_override_f = None

    vp = resolve_valeur_point(
        regles_prime,
        code_postal=cp,
        override=vp_override_f,
    )

    prorata_raw = dict(regles_prime.get("prorata") or {})
    if not isinstance(prorata_raw, dict):
        prorata_raw = {}
    mode_override = overrides.get("prorata_mode_override")
    if mode_override in ("heures_contrat", "jours_forfait", "none"):
        prorata_raw["mode"] = mode_override

    min_override = overrides.get("min_annees_override")
    try:
        min_override_f = float(min_override) if min_override is not None else None
    except (TypeError, ValueError):
        min_override_f = None

    return {
        "valeur_point": vp,
        "min_annees_override": min_override_f,
        "prorata": prorata_raw,
        "code_postal": cp,
    }
