# Formules de l'état de provision des congés payés.
# Domaine pur : aucun accès base, aucune dépendance FastAPI.
# Les quatre formules reproduisent l'état Cegid « État de provision des congés payés »,
# vérifiées sur les 71 lignes du modèle CARTOL du 21/07/2026.
# Le repos compensateur s'ajoute aux jours provisionnés (retour d'Elsa du 05/11/2026) : un repos
# acquis et pas pris est payé au départ du salarié (C. trav. D3121-23), c'est une dette.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

# Jours ouvrés moyens d'un mois, convention du cabinet. Ce n'est pas une règle légale :
# la règle légale est le maximum entre maintien de salaire et 1/10e de la rémunération
# de la période de référence. On reproduit le modèle demandé.
DIVISEUR_MENSUALISATION: float = 22.0

# Fenêtre du salaire de référence et du taux de charges.
FENETRE_REFERENCE_MOIS: int = 12


def en_jours_ouvres(solde: float, unite: str | None, ratio: float) -> float:
    """Le solde en jours ouvrés. Il est calculé dans l'unité de la société : seul un solde en
    jours ouvrables se convertit (MAJI au 30/09/2026 : 20,50 jours ouvrés, pas 17,08)."""
    if unite == "ouvre":
        return round(float(solde), 2)
    if ratio <= 0:
        return 0.0
    return round(float(solde) / ratio, 2)


#: Heures d'une journée de repos quand la société n'a rien réglé (comme l'écran des soldes).
HEURES_JOURNEE_REPOS_PAR_DEFAUT: float = 7.0


def repos_en_jours(
    heures_acquises: float, heures_prises: float, heures_par_jour: float
) -> tuple[float, str]:
    """Le solde de repos compensateur en jours, et ce qu'il faut signaler.

    Le compteur est en heures (le crédit COR naît en heures) ; une journée de repos vaut le
    réglage de la société. Un repos pris sans crédit laisse un solde négatif : il ne diminue
    pas la dette de congés, il se signale."""
    solde = round(float(heures_acquises) - float(heures_prises), 2)
    if solde < 0:
        return 0.0, f"repos compensateur pris sans crédit : {-solde:g} h"
    diviseur = float(heures_par_jour) if heures_par_jour and heures_par_jour > 0 else HEURES_JOURNEE_REPOS_PAR_DEFAUT
    return round(solde / diviseur, 2), ""


def present_a_la_date(entree: date, sorties: Iterable[date], ref: date) -> bool:
    """Présent à la fin du mois demandé : entré au plus tard ce jour, et pas sorti ce jour ou
    avant au titre du contrat en cours (une sortie d'avant la réembauche ne compte pas).
    Un salarié sorti a été payé de ses congés au solde de tout compte : pas de provision."""
    if entree > ref:
        return False
    return not any(entree <= s <= ref for s in sorties)


def patronal_du_bulletin(donnees: Mapping[str, Any]) -> float:
    """Cotisations patronales d'un bulletin : celles calculées par Martine, sinon le total
    patronal d'un bulletin repris de Quadra (qui n'a pas de `cotisations_officielles`)."""
    officielles = donnees.get("cotisations_officielles") or []
    if officielles:
        return round(sum(float(c.get("total_patronal") or 0) for c in officielles), 2)
    structure = donnees.get("structure_cotisations") or {}
    return round(float(structure.get("total_patronal") or 0), 2) if isinstance(structure, Mapping) else 0.0


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
    solde_repos: float = 0.0


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
    solde_repos: float = 0.0,
) -> LigneProvision:
    """Une ligne de l'état, à partir de données déjà résolues.

    solde_n1 / solde_n sont en jours ouvrés, solde_repos en jours de repos compensateur ;
    les trois sont valorisés au même salaire journalier. taux_charges est en pourcentage
    (25.74), pas en fraction.
    """
    if diviseur <= 0:
        raise ValueError(f"Diviseur de mensualisation invalide : {diviseur}")

    solde_jours = round(solde_n1 + solde_n + solde_repos, 2)
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
        solde_repos=round(solde_repos, 2),
    )


def calculer_totaux(lignes: list[LigneProvision]) -> dict[str, float]:
    """Ligne « Total » de l'état. Le taux est pondéré, jamais une moyenne de taux."""
    provision = round(sum(l.provision for l in lignes), 2)
    montant_charges = round(sum(l.montant_charges for l in lignes), 2)
    return {
        "solde_n1": round(sum(l.solde_n1 for l in lignes), 2),
        "solde_n": round(sum(l.solde_n for l in lignes), 2),
        "solde_repos": round(sum(l.solde_repos for l in lignes), 2),
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


def reference_du_salarie(
    bulletins: dict[tuple[int, int], tuple[float, float]],
    mois_cibles: list[tuple[int, int]],
    salaire_contractuel: float | None,
    entree: date | None,
    taux_societe: float | None = None,
) -> Reference:
    """`resoudre_reference` sans le mois d'entrée quand il est incomplet (entrée après le 1er).

    Un premier bulletin partiel n'est pas un salaire mensuel : F.B., entrée le 09/09/2026,
    172,34 € de brut, aurait valorisé ses jours au tiers. Quand il ne reste aucun autre mois,
    le salaire contractuel le remplace et le taux de charges vient de ce premier bulletin.
    """
    if entree is None or entree.day == 1:
        return resoudre_reference(bulletins, mois_cibles, salaire_contractuel, taux_societe)
    cle = (entree.year, entree.month)
    premier = bulletins.get(cle)
    if not premier or premier[0] <= 0:
        return resoudre_reference(bulletins, mois_cibles, salaire_contractuel, taux_societe)
    autres = {k: v for k, v in bulletins.items() if k != cle}
    if any(k in autres and autres[k][0] > 0 for k in mois_cibles):
        return resoudre_reference(autres, mois_cibles, salaire_contractuel, taux_societe)
    if not salaire_contractuel:
        return resoudre_reference(bulletins, mois_cibles, salaire_contractuel, taux_societe)
    brut, patronal = premier
    return Reference(
        salaire_reference=round(float(salaire_contractuel), 2),
        taux_charges=round(patronal / brut * 100, 2),
        mois_retenus=f"0/{len(mois_cibles)}",
        anomalie="premier mois incomplet : salaire contractuel utilisé, taux du premier bulletin",
    )
