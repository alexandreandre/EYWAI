"""Correspondance libellés Cegid <-> champs payslip_data EYWAI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Mapping générique + extensions CCN
GENERIC_RUBRIC_ALIASES: Dict[str, str] = {
    "salaire de base": "salaire_base",
    "h. supp majorées à 25 %": "heures_sup_25",
    "heures supplémentaires 25": "heures_sup_25",
    "prime exceptionnelle": "prime_exceptionnelle",
    "prime ancienneté": "prime_anciennete",
    "prime anciennete": "prime_anciennete",
    "participation 2025": "participation",
    "acompte sur participation 2025": "acompte_participation",
    "rbst note de frais": "note_de_frais",
    "gan prevoyance non cadre ta": "prevoyance_gan",
    "gan mutuelle isole": "mutuelle_gan",
    "journée de solidarité=25 mai": "journee_solidarite",
    "journee de solidarite=25 mai": "journee_solidarite",
}

CCN_0292_ALIASES: Dict[str, str] = {
    **GENERIC_RUBRIC_ALIASES,
}


def normalize_label(label: str) -> str:
    return " ".join(label.lower().strip().split())


def rubric_field_key(label: str, idcc: str | None = None) -> str:
    norm = normalize_label(label)
    aliases = CCN_0292_ALIASES if idcc == "0292" else GENERIC_RUBRIC_ALIASES
    for alias, key in aliases.items():
        if alias in norm or norm in alias:
            return key
    return norm.replace(" ", "_")


def extract_eywai_metrics(payslip_data: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Extrait les métriques comparables depuis un payslip_data EYWAI."""
    sc = payslip_data.get("structure_cotisations") or {}
    sn = payslip_data.get("synthese_net") or {}
    pas = sn.get("impot_prelevement_a_la_source") or {}
    pied = payslip_data.get("pied_de_page") or {}

    metrics: Dict[str, Optional[float]] = {
        "salaire_brut": _f(payslip_data.get("salaire_brut")),
        "net_a_payer": _f(payslip_data.get("net_a_payer")),
        "net_imposable": _f(sn.get("net_imposable")),
        "montant_net_social": _f(sn.get("montant_net_social")),
        "net_avant_impot": _f(
            sn.get("net_social_avant_impot")
            if sn.get("net_social_avant_impot") is not None
            else sn.get("montant_net_social")
        ),
        "pas_montant": _f(pas.get("montant")),
        "pas_taux": _f(pas.get("taux")),
        "total_cotisations_salariales": _f(sc.get("total_salarial")),
        "total_cotisations_patronales": _f(sc.get("total_patronal")),
        "cout_total_employeur": _f(pied.get("cout_total_employeur")),
        "acompte_participation": _f(sn.get("acompte_verse")),
    }

    # Rubriques brut
    for line in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(line, dict):
            continue
        lib = line.get("libelle") or ""
        key = rubric_field_key(str(lib))
        amount = _f(line.get("montant")) or _f(line.get("montant_salarial"))
        if amount is not None:
            metrics[key] = amount
        qty = _f(line.get("quantite"))
        if qty is not None and "heures" in key:
            metrics[f"{key}_heures"] = qty

    # Participation
    parts = payslip_data.get("participations") or []
    if parts and isinstance(parts[0], dict):
        metrics["participation"] = _f(parts[0].get("brut"))

    # Primes non soumises
    for prime in payslip_data.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        key = rubric_field_key(str(prime.get("libelle") or ""))
        metrics[key] = _f(prime.get("montant"))

    return metrics


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def reference_metrics(ref: Any) -> Dict[str, Optional[float]]:
    """Extrait les métriques d'un ReferenceBulletin."""
    metrics: Dict[str, Optional[float]] = {
        "salaire_brut": ref.salaire_brut,
        "net_imposable": ref.net_imposable,
        "montant_net_social": ref.montant_net_social,
        "net_avant_impot": ref.net_avant_impot or ref.montant_net_social,
        "pas_montant": ref.pas_montant,
        "pas_taux": ref.pas_taux,
        "net_a_payer": ref.net_a_payer,
        "cout_total_employeur": ref.cout_total_employeur,
    }
    for rub in ref.rubriques:
        key = rubric_field_key(rub.libelle)
        amount = rub.montant_salarial
        if amount is not None:
            metrics[key] = amount
        if "participation" in rub.libelle.lower() and amount:
            metrics["participation"] = amount
        if "acompte" in rub.libelle.lower() and amount is not None:
            metrics["acompte_participation"] = abs(amount)
        if "note de frais" in rub.libelle.lower() and amount:
            metrics["note_de_frais"] = amount
        if rub.base is not None and "heures" in key:
            metrics[f"{key}_heures"] = rub.base
    return metrics
