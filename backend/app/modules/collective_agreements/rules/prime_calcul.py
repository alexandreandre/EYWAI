"""Calcul de la prime d'ancienneté (formules conventionnelles)."""

from __future__ import annotations

from typing import Any, Optional


def _classification_classe_emploi(contrat: dict[str, Any]) -> Optional[int]:
    cc = (
        contrat.get("remuneration", {})
        .get("classification_conventionnelle", {})
    )
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


def calculer_montant_prime_anciennete(
    *,
    regles_prime: dict[str, Any],
    contrat: dict[str, Any],
    anciennete_annees: float,
    salaire_base_mensuel: float,
    minima_applicables: list[dict[str, Any]],
) -> tuple[float, float, str] | None:
    """
    Retourne (base_de_calcul, montant_prime, libelle) ou None si non applicable.

    Formule métallurgie (3248) : (valeur_point × taux_classe × 100) × années.
    """
    regle_base = regles_prime.get("base_de_calcul") or {}
    methode = regle_base.get("methode")
    taux_par_classe = regles_prime.get("taux_par_classe") or {}

    if methode == "metallurgie_prime_anciennete" or (
        methode == "valeur_du_point" and taux_par_classe
    ):
        classe = _classification_classe_emploi(contrat)
        valeur_point = regle_base.get("valeur")
        if classe is None or valeur_point is None:
            return None
        taux_key = str(min(classe, 10))
        taux_classe = taux_par_classe.get(taux_key)
        if taux_classe is None:
            taux_classe = taux_par_classe.get(str(classe))
        if taux_classe is None:
            return None
        try:
            vp = float(valeur_point)
            taux = float(taux_classe)
        except (TypeError, ValueError):
            return None
        base_specifique = vp * taux * 100
        montant = base_specifique * anciennete_annees
        libelle = (
            f"Prime d'ancienneté métallurgie "
            f"({anciennete_annees:.0f} ans, classe {classe}, "
            f"{taux * 100:.2f} %)"
        )
        return base_specifique, round(montant, 2), libelle

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
        valeur_point = regle_base.get("valeur")
        if coeff_salarie is not None and valeur_point is not None:
            try:
                base_de_calcul = float(coeff_salarie) * float(valeur_point)
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
    return base_de_calcul, round(montant, 2), libelle
