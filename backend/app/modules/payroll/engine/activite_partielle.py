"""Activité partielle : les heures et le taux imprimés sur le bulletin."""

from __future__ import annotations

from typing import Dict


def heures_et_taux(montant: float, heures: float) -> Dict[str, float]:
    """Colonnes « base » et « taux » d'une ligne d'activité partielle.

    Rien sans heures saisies : le taux ne s'invente pas.
    """
    if heures <= 0:
        return {}
    return {"quantite": round(heures, 2), "taux": round(abs(montant) / heures, 4)}


#: Identifiant de l'indemnité dans le bulletin : le coût employeur et la
#: déclaration la reconnaissent par lui (`engine.bulletin`).
PRIME_ID_INDEMNITE = "indemnite_activite_partielle"


def _texte(prime_id: object, libelle: object) -> str:
    return f"{prime_id} {libelle}".lower()


def heures_chomees_de_la_retenue(
    prime_id: object, libelle: object, montant: float, quantite: object
) -> float:
    """Heures chômées portées par la retenue « Heures chômées (act. part.) ».

    Le Smic de référence de la réduction générale en est diminué : le montant
    seul ne les donne pas, la saisie les porte (`quantity`). 0 pour toute
    autre ligne.
    """
    texte = _texte(prime_id, libelle)
    if montant < 0 and ("chôm" in texte or "chom" in texte) and "act" in texte and "part" in texte:
        try:
            return abs(float(quantite or 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def heures_chomees_des_saisies(saisies: object) -> float:
    """Heures chômées d'activité partielle des saisies du mois, telles que le
    moteur les reçoit (`libelle`, `montant`, `quantite` posée par
    `heures_et_taux`) : calendrier et saisie à la main passent par là."""
    total = 0.0
    for saisie in saisies or []:
        if not isinstance(saisie, dict):
            continue
        try:
            montant = float(saisie.get("montant") or 0.0)
        except (TypeError, ValueError):
            continue
        total += heures_chomees_de_la_retenue(
            saisie.get("prime_id"),
            saisie.get("libelle") or saisie.get("name"),
            montant,
            saisie.get("quantite", saisie.get("quantity")),
        )
    return round(total, 2)


def est_l_indemnite(prime_id: object, libelle: object) -> bool:
    """La ligne est l'indemnité d'activité partielle (revenu de remplacement)."""
    texte = _texte(prime_id, libelle)
    return "indemn" in texte and "activit" in texte and "partiel" in texte


def ligne_d_indemnite(libelle: object, montant: float) -> dict[str, object] | None:
    """L'indemnité, rangée hors des primes : exonérée de cotisations, imposable,
    reconnue par son identifiant. Rien pour un montant nul ou négatif."""
    if montant <= 0:
        return None
    return {
        "prime_id": PRIME_ID_INDEMNITE,
        "libelle": libelle,
        "montant": round(montant, 2),
    }


# CSG/CRDS de l'indemnité légale (Urssaf, « Activité partielle », publié le
# 25/03/2026) : revenu de remplacement exclu des cotisations, soumis à la CSG
# au seul taux de 6,20 % (dont 3,80 % déductible, service-public F2971) et à la
# CRDS de 0,50 %, après un abattement de 1,75 %. Le prélèvement est écrêté
# pour ne pas faire descendre l'indemnité nette, cumulée avec le salaire net,
# sous le Smic brut d'un temps plein ; il se précompte dans l'ordre CSG
# déductible, CSG non déductible, CRDS. Les bulletins Quadra de LEWIS (juin
# 2026) font de même : 3,80 % et 2,90 % sur 98,25 %, annulés à 100 % sous le Smic.
TAUX_CSG_DEDUCTIBLE = 0.038
TAUX_CSG_CRDS_NON_DEDUCTIBLE = 0.029
ASSIETTE_APRES_ABATTEMENT = 0.9825
HEURES_SMIC_TEMPS_PLEIN = 35 * 52 / 12


def lignes_csg_de_l_indemnite(
    indemnites: list[dict[str, object]],
    *,
    salaire_brut: float,
    total_salarial: float,
    smic_horaire: float,
) -> list[dict[str, object]]:
    """Les lignes de CSG/CRDS des indemnités d'activité partielle du mois.

    `total_salarial` : les retenues salariales du salaire, déjà calculées. Rien
    si le net (salaire net + indemnité) reste sous le Smic brut temps plein ;
    entre les deux, le prélèvement est réduit à l'excédent.
    """
    indemnite = round(sum(float(i.get("montant") or 0.0) for i in indemnites), 2)
    if indemnite <= 0:
        return []
    base = round(indemnite * ASSIETTE_APRES_ABATTEMENT, 2)
    deductible = round(base * TAUX_CSG_DEDUCTIBLE, 2)
    non_deductible = round(base * TAUX_CSG_CRDS_NON_DEDUCTIBLE, 2)
    smic_mensuel = float(smic_horaire or 0.0) * HEURES_SMIC_TEMPS_PLEIN
    marge = round(float(salaire_brut) - float(total_salarial) + indemnite - smic_mensuel, 2)
    if smic_mensuel > 0:
        disponible = max(0.0, marge)
        deductible = min(deductible, disponible)
        non_deductible = min(non_deductible, round(disponible - deductible, 2))
    lignes: list[dict[str, object]] = []
    for libelle, taux, montant in (
        ("CSG déductible activité partielle", TAUX_CSG_DEDUCTIBLE, deductible),
        (
            "CSG/CRDS non déductible activité partielle",
            TAUX_CSG_CRDS_NON_DEDUCTIBLE,
            non_deductible,
        ),
    ):
        if montant > 0:
            lignes.append(
                {
                    "libelle": libelle,
                    "base": base,
                    "taux_salarial": taux,
                    "montant_salarial": round(montant, 2),
                    "taux_patronal": 0.0,
                    "montant_patronal": 0.0,
                    "is_csg_activite_partielle": True,
                }
            )
    return lignes
