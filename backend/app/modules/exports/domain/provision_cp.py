# Formules de l'état de provision des congés payés.
# Domaine pur : aucun accès base, aucune dépendance FastAPI.
# Les quatre formules reproduisent l'état Cegid « État de provision des congés payés »,
# vérifiées sur les 71 lignes du modèle CARTOL du 21/07/2026.
from __future__ import annotations

from dataclasses import dataclass

# Jours ouvrés moyens d'un mois, convention du cabinet. Ce n'est pas une règle légale :
# la règle légale est le maximum entre maintien de salaire et 1/10e de la rémunération
# de la période de référence. On reproduit le modèle demandé.
DIVISEUR_MENSUALISATION: float = 22.0

# Fenêtre du salaire de référence et du taux de charges.
FENETRE_REFERENCE_MOIS: int = 12


@dataclass(frozen=True)
class LigneProvision:
    matricule: str
    nom: str
    date_entree: str
    solde_n1: float
    solde_n: float
    solde_jours: float
    salaire_reference: float
    taux_charges: float
    montant_charges: float
    provision: float
    total: float
    mois_retenus: str
    anomalie: str


def calculer_ligne(
    matricule: str,
    nom: str,
    date_entree: str,
    solde_n1: float,
    solde_n: float,
    salaire_reference: float,
    taux_charges: float,
    mois_retenus: str,
    anomalie: str = "",
    diviseur: float = DIVISEUR_MENSUALISATION,
) -> LigneProvision:
    """Une ligne de l'état, à partir de données déjà résolues.

    solde_n1 / solde_n sont en jours ouvrés. taux_charges est en pourcentage (25.74),
    pas en fraction.
    """
    if diviseur <= 0:
        raise ValueError(f"Diviseur de mensualisation invalide : {diviseur}")

    solde_jours = round(solde_n1 + solde_n, 2)
    provision = round(solde_jours * salaire_reference / diviseur, 2)
    montant_charges = round(provision * taux_charges / 100, 2)
    total = round(provision + montant_charges, 2)

    return LigneProvision(
        matricule=matricule,
        nom=nom,
        date_entree=date_entree,
        solde_n1=round(solde_n1, 2),
        solde_n=round(solde_n, 2),
        solde_jours=solde_jours,
        salaire_reference=round(salaire_reference, 2),
        taux_charges=round(taux_charges, 2),
        montant_charges=montant_charges,
        provision=provision,
        total=total,
        mois_retenus=mois_retenus,
        anomalie=anomalie,
    )


def calculer_totaux(lignes: list[LigneProvision]) -> dict[str, float]:
    """Ligne « Total » de l'état. Le taux est pondéré, jamais une moyenne de taux."""
    provision = round(sum(l.provision for l in lignes), 2)
    montant_charges = round(sum(l.montant_charges for l in lignes), 2)
    return {
        "solde_n1": round(sum(l.solde_n1 for l in lignes), 2),
        "solde_n": round(sum(l.solde_n for l in lignes), 2),
        "solde_jours": round(sum(l.solde_jours for l in lignes), 2),
        "salaire_reference": round(sum(l.salaire_reference for l in lignes), 2),
        "taux_charges": round(montant_charges / provision * 100, 2) if provision else 0.0,
        "montant_charges": montant_charges,
        "provision": provision,
        "total": round(provision + montant_charges, 2),
    }


def mois_de_reference(
    annee: int, mois: int, fenetre: int = FENETRE_REFERENCE_MOIS
) -> list[tuple[int, int]]:
    """Les `fenetre` couples (année, mois) qui se terminent au mois donné, inclus."""
    couples: list[tuple[int, int]] = []
    a, m = annee, mois
    for _ in range(fenetre):
        couples.append((a, m))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return list(reversed(couples))


@dataclass(frozen=True)
class Reference:
    salaire_reference: float
    taux_charges: float
    mois_retenus: str
    anomalie: str


def resoudre_reference(
    bulletins: dict[tuple[int, int], tuple[float, float]],
    mois_cibles: list[tuple[int, int]],
    salaire_contractuel: float | None,
    taux_societe: float | None,
) -> Reference:
    """Salaire moyen et taux de charges sur la fenêtre de référence.

    `bulletins` associe (année, mois) à (brut, cotisations patronales). Un mois sans
    bulletin ou à brut nul n'est pas retenu : il ne doit pas tirer la moyenne vers le bas.
    """
    retenus = [
        bulletins[cle]
        for cle in mois_cibles
        if cle in bulletins and bulletins[cle][0] > 0
    ]
    total_mois = len(mois_cibles)

    if not retenus:
        if salaire_contractuel:
            return Reference(
                salaire_reference=round(float(salaire_contractuel), 2),
                taux_charges=round(float(taux_societe or 0.0), 2),
                mois_retenus=f"0/{total_mois}",
                anomalie="aucun bulletin : salaire contractuel et taux société utilisés",
            )
        return Reference(
            salaire_reference=0.0,
            taux_charges=0.0,
            mois_retenus=f"0/{total_mois}",
            anomalie="aucun bulletin et aucun salaire contractuel",
        )

    somme_brut = sum(b for b, _ in retenus)
    somme_patronal = sum(p for _, p in retenus)
    return Reference(
        salaire_reference=round(somme_brut / len(retenus), 2),
        taux_charges=round(somme_patronal / somme_brut * 100, 2),
        mois_retenus=f"{len(retenus)}/{total_mois}",
        anomalie="",
    )
