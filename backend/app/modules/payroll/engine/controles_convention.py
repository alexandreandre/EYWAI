"""Contrôles non bloquants : convention collective et cohérence paie."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.collective_agreements.rules.resolver import (
    code_postal_from_entreprise,
    resolve_salaires_minima,
)


def _alert(
    *,
    code: str,
    message: str,
    critique: bool = False,
    donnee_non_officielle: bool = False,
) -> Dict[str, Any]:
    return {
        "code": code,
        "critique": critique,
        "severity": "warning" if critique else "info",
        "message": message,
        "donnee_non_officielle": donnee_non_officielle,
    }


def controle_convention_collective(contexte, salaire_brut: float) -> List[Dict[str, Any]]:
    """
    Vérifie la cohérence salaire / convention collective (non bloquant).
    Les alertes sont stockées dans payslip_data.alertes_baremes pour la RH.
    """
    if getattr(contexte, "is_alternant", False):
        return []

    cc = (
        contexte.contrat.get("remuneration", {}).get("convention_collective", {}) or {}
    )
    idcc = str(cc.get("idcc") or "").strip()
    if not idcc:
        return []

    libelle_cc = str(cc.get("libelle") or cc.get("name") or f"IDCC {idcc}").strip()
    regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
        f"idcc_{idcc}", {}
    )
    if not regles_cc and idcc.isdigit():
        for variant in (idcc.zfill(4), idcc.lstrip("0") or "0"):
            regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
                f"idcc_{variant}", {}
            )
            if regles_cc:
                break

    alertes: List[Dict[str, Any]] = []

    if not regles_cc:
        alertes.append(
            _alert(
                code="cc_regles_absentes",
                critique=True,
                message=(
                    f"Aucune règle paie extraite pour {libelle_cc} (IDCC {idcc}). "
                    "Le moteur ne peut pas vérifier les minima conventionnels."
                ),
            )
        )
        return alertes

    classification = (
        contexte.contrat.get("remuneration", {}).get("classification_conventionnelle")
        or {}
    )
    coeff = classification.get("coefficient")
    if coeff is None:
        alertes.append(
            _alert(
                code="cc_classification_manquante",
                critique=True,
                message=(
                    f"Classification conventionnelle absente sur la fiche salarié "
                    f"({libelle_cc}). Impossible de contrôler le minimum conventionnel."
                ),
            )
        )
        return alertes

    try:
        coeff_num = float(coeff)
    except (TypeError, ValueError):
        alertes.append(
            _alert(
                code="cc_coefficient_invalide",
                critique=True,
                message=f"Coefficient conventionnel invalide ({coeff!r}).",
            )
        )
        return alertes

    minima = resolve_salaires_minima(
        regles_cc,
        code_postal=code_postal_from_entreprise(contexte.entreprise),
    )
    if not minima:
        alertes.append(
            _alert(
                code="cc_grille_vide",
                critique=True,
                message=(
                    f"Aucune grille salariale disponible pour {libelle_cc} "
                    f"(IDCC {idcc}). Mettez à jour la convention depuis Légifrance."
                ),
            )
        )
        return alertes

    minimum_applicable: Optional[float] = None
    libelle_poste: Optional[str] = None
    for row in minima:
        if not isinstance(row, dict):
            continue
        row_coeff = row.get("coefficient")
        try:
            if float(row_coeff) == coeff_num:
                minimum_applicable = float(row.get("valeur") or 0)
                libelle_poste = row.get("libelle")
                break
        except (TypeError, ValueError):
            continue

    if minimum_applicable is None:
        alertes.append(
            _alert(
                code="cc_coefficient_hors_grille",
                critique=True,
                message=(
                    f"Coefficient {coeff_num:g} absent de la grille {libelle_cc}. "
                    "Vérifiez la classification ou mettez à jour la convention."
                ),
            )
        )
        return alertes

    if salaire_brut + 0.01 < minimum_applicable:
        poste = f" ({libelle_poste})" if libelle_poste else ""
        alertes.append(
            _alert(
                code="cc_salaire_sous_minimum",
                critique=True,
                message=(
                    f"Salaire brut ({salaire_brut:.2f} €) inférieur au minimum "
                    f"conventionnel{poste} pour le coefficient {coeff_num:g} "
                    f"({minimum_applicable:.2f} € — {libelle_cc})."
                ),
            )
        )

    return alertes


def extraire_alertes_rh_depuis_bulletin(
    payslip_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Agrège les alertes moteur paie pour affichage RH (API / anomalies)."""
    out: List[Dict[str, str]] = []

    for raw in payslip_data.get("alertes_baremes") or []:
        if not isinstance(raw, dict):
            continue
        msg = str(raw.get("message") or "").strip()
        if not msg:
            continue
        out.append(
            {
                "source": "moteur_paie",
                "code": str(raw.get("code") or "alerte_paie"),
                "severite": "bloquant" if raw.get("critique") else "avertissement",
                "message": msg,
            }
        )

    synthese = payslip_data.get("synthese_net") or {}
    if isinstance(synthese, dict):
        for msg in synthese.get("alertes_maintien") or []:
            text = str(msg).strip()
            if text:
                out.append(
                    {
                        "source": "maintien_salaire",
                        "code": "maintien_salaire",
                        "severite": "avertissement",
                        "message": text,
                    }
                )

    return out
