"""
Règles métier COR (Contrepartie Obligatoire en Repos) et extraction des heures sup.

Logique pure, sans FastAPI ni dépendance DB. Comportement identique à
services/repos_compensateur/calcul_cor et extraction_hs.
"""

from __future__ import annotations

from typing import Any

# --- Constantes COR ---
CONTINGENT_DEFAUT = 220.0  # heures
HEURES_PAR_JOUR_REPOS = 7.0


# --- Calcul COR ---
def calculer_heures_cor_mois(
    cumul_hs_fin_mois: float,
    cumul_hs_fin_mois_precedent: float,
    contingent: float = CONTINGENT_DEFAUT,
    taux_cor: float = 1.0,
) -> float:
    """
    Calcule les heures de COR acquises pour un mois donné.

    Formule: (max(0, cumul_N - contingent) - max(0, cumul_N-1 - contingent)) × taux_COR
    """
    heures_au_dela_precedent = max(0.0, cumul_hs_fin_mois_precedent - contingent)
    heures_au_dela_actuel = max(0.0, cumul_hs_fin_mois - contingent)
    heures_cor = (heures_au_dela_actuel - heures_au_dela_precedent) * taux_cor
    return round(max(0.0, heures_cor), 2)


def heures_vers_jours(
    heures: float, heures_par_jour: float = HEURES_PAR_JOUR_REPOS
) -> float:
    """Convertit les heures de repos en jours."""
    if heures_par_jour <= 0:
        return 0.0
    return round(heures / heures_par_jour, 2)


def get_taux_cor_par_effectif(effectif: int | None) -> float:
    """Retourne le taux COR selon l'effectif : 0.5 si <20, 1.0 si >=20."""
    if effectif is None:
        return 1.0
    return 0.5 if effectif < 20 else 1.0


# --- Extraction HS depuis payslip_data (règle métier : quelles lignes = HS) ---
def extraire_heures_hs_du_bulletin(payslip_data: dict[str, Any] | None) -> float:
    """
    Extrait le total des heures supplémentaires d'un bulletin à partir de calcul_du_brut.
    Filtre les lignes dont libelle contient "Heures suppl" ou "suppl" (insensible à la casse).
    """
    if not payslip_data or not isinstance(payslip_data, dict):
        return 0.0

    calcul_du_brut = payslip_data.get("calcul_du_brut")
    if not isinstance(calcul_du_brut, list):
        return 0.0

    total = 0.0
    for ligne in calcul_du_brut:
        if not isinstance(ligne, dict):
            continue
        libelle = ligne.get("libelle") or ""
        libelle_lower = libelle.lower()
        if "heures suppl" in libelle_lower or (
            "suppl" in libelle_lower and "heure" in libelle_lower
        ):
            quantite = ligne.get("quantite")
            if quantite is not None and isinstance(quantite, (int, float)):
                total += float(quantite)

    return round(total, 2)


def cumuler_heures_hs_annee(
    bulletins_par_mois: dict[int, dict[str, Any]],
) -> dict[int, float]:
    """
    Retourne pour chaque mois (1-12) le cumul des heures HS de janvier jusqu'à ce mois inclus.
    bulletins_par_mois: { month: payslip_data }
    """
    cumuls: dict[int, float] = {}
    cumul_annee = 0.0
    for mois in range(1, 13):
        payslip_data = bulletins_par_mois.get(mois)
        hs_mois = extraire_heures_hs_du_bulletin(payslip_data)
        cumul_annee += hs_mois
        cumuls[mois] = round(cumul_annee, 2)
    return cumuls


__all__ = [
    "CONTINGENT_DEFAUT",
    "HEURES_PAR_JOUR_REPOS",
    "calculer_heures_cor_mois",
    "heures_vers_jours",
    "get_taux_cor_par_effectif",
    "extraire_heures_hs_du_bulletin",
    "cumuler_heures_hs_annee",
]
