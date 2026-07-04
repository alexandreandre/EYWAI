"""Orchestration prime d'ancienneté CCN (base + prorata mensuel)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set

from app.modules.collective_agreements.rules.prime_calcul import (
    cap_anciennete_annees,
    check_eligibilite_prime_anciennete,
    compute_anciennete_annees,
    calculer_prime_anciennete_plein_mois,
    resolve_prime_anciennete_config,
)
from app.modules.collective_agreements.rules.resolver import (
    code_postal_from_entreprise,
    resolve_salaires_minima,
)
from app.modules.payroll.engine.contexte import ContextePaie
from app.modules.payroll.engine.temps_travail_mois import compute_temps_retenu_mois
from app.shared.seniority_reference import resolve_date_anciennete_from_contrat
from app.modules.payroll.engine.salaire_contractuel import (
    salaire_contractuel_total_hors_hs_mode,
    salaire_hors_hs_structurelles,
)


def _salaire_base_prime_anciennete(contexte: ContextePaie) -> float:
    """Base prime : contractuel total (base + HS struct) si salaire hors HS struct."""
    sb = contexte.salaire_base_mensuel
    if not salaire_hors_hs_structurelles(contexte.contrat):
        return sb
    from app.modules.payroll.engine.calcul_brut import _taux_majoration_hs

    maj = _taux_majoration_hs(contexte, 0) or 0.25
    return salaire_contractuel_total_hors_hs_mode(
        sb, contexte.duree_hebdo_contrat, maj
    )


def _prorata_config(regles_prime: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    raw = dict(resolved.get("prorata") or regles_prime.get("prorata") or {})
    if not isinstance(raw, dict):
        raw = {}
    enabled = raw.get("enabled")
    if enabled is None:
        enabled = bool(raw.get("mode") and raw.get("mode") != "none")
    return {
        "enabled": bool(enabled),
        "mode": raw.get("mode") or "none",
        "inclure_heures_sup": bool(raw.get("inclure_heures_sup", True)),
        "maladie_si_maintien": bool(raw.get("maladie_si_maintien", True)),
        "sans_pointage_policy": raw.get("sans_pointage_policy") or "plein_mois",
        "ratio_plafond": raw.get("ratio_plafond"),
    }


def _resolve_date_entree(contexte: ContextePaie | Any) -> str:
    """Date d'ancienneté pour la prime — reprise prioritaire sur date d'embauche."""
    contrat = getattr(contexte, "contrat", None) or {}
    if isinstance(contrat, dict):
        ref = resolve_date_anciennete_from_contrat(contrat)
        if ref:
            return ref
    direct = getattr(contexte, "date_entree", None)
    if direct:
        return str(direct)
    if isinstance(contrat, dict):
        return contrat.get("contrat", {}).get("date_entree") or ""
    return ""


def calculer_ligne_prime_anciennete(
    contexte: ContextePaie,
    *,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    jours_maintien: Optional[Set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any] | None:
    """Calcule la ligne bulletin prime d'ancienneté (avec prorata si activé)."""
    date_entree = _resolve_date_entree(contexte)
    if not date_entree:
        return None

    idcc = (
        contexte.contrat.get("remuneration", {})
        .get("convention_collective", {})
        .get("idcc")
    )
    if not idcc:
        return None

    regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
        f"idcc_{idcc}", {}
    )
    if not regles_cc and str(idcc).isdigit():
        for variant in (str(idcc).zfill(4), str(idcc).lstrip("0") or "0"):
            regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
                f"idcc_{variant}", {}
            )
            if regles_cc:
                break

    regles_prime = regles_cc.get("prime_anciennete", {})
    if not regles_prime:
        return None

    resolved = resolve_prime_anciennete_config(regles_prime, contexte.entreprise)
    anciennete_annees = compute_anciennete_annees(
        date_entree, date_fin_periode, mode="floor"
    )
    anciennete_annees = cap_anciennete_annees(anciennete_annees, regles_prime)

    eligible, motif = check_eligibilite_prime_anciennete(
        regles_prime=regles_prime,
        contrat=contexte.contrat,
        anciennete_annees=anciennete_annees,
        statut=contexte.statut_salarie,
        min_annees_override=resolved.get("min_annees_override"),
    )
    if not eligible:
        if motif and hasattr(contexte, "alertes_baremes"):
            if isinstance(contexte.alertes_baremes, list):
                contexte.alertes_baremes.append(
                    {
                        "code": "prime_anciennete_non_eligible",
                        "message": motif,
                        "critique": False,
                        "severity": "info",
                    }
                )
        return None

    regle_base = regles_prime.get("base_de_calcul") or {}
    methode = regle_base.get("methode")
    taux_par_classe = regles_prime.get("taux_par_classe") or {}
    needs_vp = methode in ("metallurgie_prime_anciennete",) or (
        methode == "valeur_du_point" and taux_par_classe
    )

    if needs_vp and resolved.get("valeur_point") is None:
        cp = resolved.get("code_postal") or code_postal_from_entreprise(
            contexte.entreprise
        )
        if isinstance(contexte.alertes_baremes, list):
            contexte.alertes_baremes.append(
                {
                    "code": "prime_anciennete_vp_zone_introuvable",
                    "message": (
                        f"Valeur du point prime d'ancienneté introuvable "
                        f"pour le code postal {cp or 'inconnu'}."
                    ),
                    "critique": False,
                    "severity": "warning",
                }
            )
        return None

    minima_applicables = resolve_salaires_minima(
        regles_cc,
        code_postal=code_postal_from_entreprise(contexte.entreprise),
    )

    plein_mois = calculer_prime_anciennete_plein_mois(
        regles_prime=regles_prime,
        contrat=contexte.contrat,
        anciennete_annees=anciennete_annees,
        salaire_base_mensuel=_salaire_base_prime_anciennete(contexte),
        minima_applicables=minima_applicables,
        valeur_point=resolved.get("valeur_point"),
    )
    if plein_mois is None:
        if isinstance(contexte.alertes_baremes, list):
            contexte.alertes_baremes.append(
                {
                    "code": "prime_anciennete_classification_manquante",
                    "message": (
                        "Prime d'ancienneté non calculée : classification "
                        "conventionnelle (classe) manquante ou incomplète."
                    ),
                    "critique": False,
                    "severity": "warning",
                }
            )
        return None

    prorata_cfg = _prorata_config(regles_prime, resolved)
    ratio = 1.0
    temps_detail: dict[str, Any] = {}

    if prorata_cfg["enabled"]:
        plafond = prorata_cfg.get("ratio_plafond")
        try:
            plafond_f = float(plafond) if plafond is not None else None
        except (TypeError, ValueError):
            plafond_f = None

        mode = prorata_cfg["mode"]
        if mode == "heures_contrat" and getattr(contexte, "is_forfait_jour", False):
            mode = "jours_forfait"

        temps = compute_temps_retenu_mois(
            mode=mode,
            calendrier_saisie=calendrier_saisie,
            duree_hebdo=contexte.duree_hebdo_contrat,
            date_debut=date_debut_periode,
            date_fin=date_fin_periode,
            jours_maintien=jours_maintien,
            inclure_heures_sup=prorata_cfg["inclure_heures_sup"],
            maladie_si_maintien=prorata_cfg["maladie_si_maintien"],
            sans_pointage_policy=prorata_cfg["sans_pointage_policy"],
            ratio_plafond=plafond_f,
            actual_hours_raw=actual_hours_raw,
        )
        ratio = temps.ratio
        temps_detail = {
            "temps_retenu": temps.temps_retenu,
            "reference": temps.reference,
            "ratio": temps.ratio,
            "mode": temps.mode,
            **temps.detail,
        }

        if ratio <= 0 and isinstance(contexte.alertes_baremes, list):
            contexte.alertes_baremes.append(
                {
                    "code": "prime_anciennete_prorata_zero",
                    "message": (
                        "Prime d'ancienneté nulle : temps de travail du mois insuffisant "
                        "(sans maintien de salaire)."
                    ),
                    "critique": False,
                    "severity": "info",
                }
            )

    montant_final = round(plein_mois.montant_plein_mois * ratio, 2)
    if montant_final <= 0:
        return None

    taux_affichage = (
        montant_final / plein_mois.base_plein_mois
        if plein_mois.base_plein_mois
        else ratio
    )

    return {
        "libelle": plein_mois.libelle,
        "quantite": plein_mois.base_plein_mois,
        "taux": round(taux_affichage, 6),
        "gain": montant_final,
        "perte": None,
        "meta": {
            "plein_mois": plein_mois.montant_plein_mois,
            "ratio_prorata": ratio,
            "valeur_point": resolved.get("valeur_point"),
            **plein_mois.meta,
            **temps_detail,
        },
    }
