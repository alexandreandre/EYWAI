# Formules de l'état de provision des congés payés.
# Domaine pur : aucun accès base, aucune dépendance FastAPI.
#
# La provision est ce que le salarié toucherait s'il partait à la date demandée (retour d'Elsa
# du 05/11/2026, règle légale annoncée le même jour) :
# - jours provisionnés : CP N-1 + CP N (ancienneté comprise) + repos compensateur, hors RTT ;
# - chaque période de congés vaut le plus élevé du maintien et du dixième (C. trav. L3141-24),
#   la règle du bulletin de sortie (payroll/engine/iccp_fin_contrat) ;
# - dans le dixième, le salaire des absences assimilées à du travail est reconstitué : en entier
#   pour un accident du travail, une maladie professionnelle, une maternité, une paternité ou une
#   adoption ; à 80 % pour une maladie ordinaire (service-public F33359 et F37482) ;
# - le maintien est le salaire du contrat (base et heures sup structurelles) plus les primes
#   versées chaque mois ;
# - un repos compensateur acquis et pas pris est payé au départ (C. trav. D3121-23) : il vaut
#   le maintien.
#
# Avant le 05/11/2026, l'état reproduisait celui de Quadra (moyenne des bruts ÷ 22) : un mois
# d'absence faisait baisser la valeur de tous les jours.
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

#: Le dixième (C. trav. L3141-24).
TAUX_DIXIEME: float = 0.10

#: Jours ouvrés moyens d'un mois (52 semaines de 5 jours ÷ 12) : ramène une prime mensuelle,
#: ou un salaire mensuel sans contrat lisible, à la valeur d'un jour ouvré.
JOURS_OUVRES_PAR_MOIS: float = 260 / 12

# Fenêtre du taux de charges (et du salaire moyen de repli).
FENETRE_REFERENCE_MOIS: int = 12

#: Bulletins regardés pour reconnaître une prime versée chaque mois.
MOIS_PRIMES_RECURRENTES: int = 3


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


# --- Lignes du bulletin ----------------------------------------------------------------------

def _texte(libelle: Any) -> str:
    """Libellé sans accents, en minuscules, sans dates ni montants : « Absence maladie
    240926-280926 » et « Absence arrêt maladie du 01/09 au 30/09 » se lisent pareil."""
    sans_accent = unicodedata.normalize("NFKD", str(libelle or "")).encode("ascii", "ignore").decode()
    texte = re.sub(r"[\d/.,#-]+", " ", sans_accent.lower())
    return re.sub(r"\s+", " ", texte).strip()


_ASSIMILEES_EN_ENTIER = ("accident", "professionnel", "maternite", "paternite", "adoption", "trajet")
_MALADIE_ORDINAIRE = ("maladie", "therapeutique")


def part_reconstituee(libelle: Any) -> float:
    """Part du salaire d'une absence reconstituée dans le dixième (C. trav. L3141-24).

    En entier pour les absences assimilées à du travail effectif (accident du travail ou de
    trajet, maladie professionnelle, maternité, paternité, adoption) ; 80 % pour un arrêt de
    maladie ordinaire ; rien pour les autres (congés payés, absence non rémunérée, entrée ou
    sortie en cours de mois, événement familial déjà payé)."""
    texte = _texte(libelle)
    if any(m in texte for m in _ASSIMILEES_EN_ENTIER):
        return 1.0
    if any(m in texte for m in _MALADIE_ORDINAIRE):
        return 0.8
    return 0.0


def _est_complement_d_arret(texte: str) -> bool:
    """Le complément de salaire versé par l'employeur pendant un arrêt : la reconstitution le
    remplace dans le dixième. Le maintien d'un événement familial n'en est pas un."""
    if "evenement familial" in texte:
        return False
    return (
        texte.startswith("maintien de salaire")
        or texte.startswith("rappel maintien de salaire")
        or texte.startswith("complement employeur")
        or texte.startswith("indemnite complementaire")
        or texte.startswith("garantie nette")
    )


def _montant(ligne: Mapping[str, Any], cle: str) -> float:
    try:
        return float(ligne.get(cle) or 0)
    except (TypeError, ValueError):
        return 0.0


def ajustement_dixieme(lignes: Iterable[Mapping[str, Any]]) -> float:
    """Ce qu'il faut ajouter au brut d'un bulletin pour la base du dixième.

    Plus la part reconstituée de chaque absence (sa retenue × 100 % ou 80 %) ; une retenue
    annexe qui ne dit pas sa nature (« Réduction HS structurelles (jours d'absence) »,
    « Complément retenue absence intégrale du mois ») suit celle des absences du mois. Moins le
    complément employeur versé pendant un arrêt, que la reconstitution remplace."""
    absences: list[tuple[float, float]] = []
    annexes = 0.0
    complement = 0.0
    for ligne in lignes or []:
        if not isinstance(ligne, Mapping):
            continue
        texte = _texte(ligne.get("libelle"))
        perte = _montant(ligne, "perte")
        gain = _montant(ligne, "gain")
        if texte.startswith("absence") and perte > 0:
            absences.append((perte, part_reconstituee(texte)))
        elif "absence" in texte and perte > 0:
            annexes += perte
        elif gain > 0 and _est_complement_d_arret(texte):
            complement += gain
    retenues = sum(p for p, _ in absences)
    reconstitue = sum(p * part for p, part in absences)
    if annexes and retenues:
        reconstitue += annexes * reconstitue / retenues
    return round(reconstitue - complement, 2)


_PONCTUELLES = (
    "exception", "regul", "rappel", "precarite", "fin d annee", "fin d'annee", "annuel",
    "bilan", "ppv", "partage", "interessement", "participation", "eme mois", "e mois",
)


def primes_recurrentes(mois: Sequence[Iterable[Mapping[str, Any]]]) -> float:
    """Montant mensuel des primes versées chaque mois, pour le maintien.

    Sur les derniers bulletins (au plus trois, au moins deux) : une prime au même libellé sur
    chacun, au montant moyen. Une prime ponctuelle (exceptionnelle, régularisation, rappel, de
    fin d'année, annuelle) n'en est pas une, même versée deux fois."""
    derniers = [list(m or []) for m in list(mois)[-MOIS_PRIMES_RECURRENTES:]]
    if len(derniers) < 2:
        return 0.0
    par_mois: list[dict[str, float]] = []
    for lignes in derniers:
        primes: dict[str, float] = {}
        for ligne in lignes:
            if not isinstance(ligne, Mapping):
                continue
            texte = _texte(ligne.get("libelle"))
            gain = _montant(ligne, "gain")
            if gain <= 0 or not texte.startswith("prime") or any(m in texte for m in _PONCTUELLES):
                continue
            primes[texte] = primes.get(texte, 0.0) + gain
        par_mois.append(primes)
    communes = set(par_mois[0]).intersection(*par_mois[1:])
    return round(sum(sum(m[p] for m in par_mois) / len(par_mois) for p in communes), 2)


# --- Valorisation -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodeProvision:
    """Une période de congés, en jours ouvrés : les jours restants, les jours légaux acquis
    (sans l'ancienneté : le dixième leur est proportionné, L3141-24) et la base du dixième
    (None si la rémunération de la période est inconnue)."""

    restants: float
    droits: float
    base: float | None


@dataclass(frozen=True)
class Valorisation:
    montant: float
    methode: str  # dixième | maintien | maintien seul | pris d'avance | rien


def valoriser_periode(
    periode: PeriodeProvision, *, valeur_jour: float, taux: float = TAUX_DIXIEME
) -> Valorisation:
    """Le plus élevé du maintien et du dixième sur les jours restants : la règle du bulletin de
    sortie (`payroll/engine/iccp_fin_contrat.indemnite_par_periode`, que les tests comparent ;
    l'importer chargerait le moteur et sa base dans ce domaine pur). Des congés pris d'avance
    (solde négatif) diminuent la dette au maintien."""
    restants = round(float(periode.restants), 2)
    if restants < 0:
        return Valorisation(round(restants * valeur_jour, 2), "pris d'avance")
    if restants == 0:
        return Valorisation(0.0, "rien")
    maintien = round(restants * float(valeur_jour), 2)
    droits = float(periode.droits or 0.0)
    if periode.base is None or droits <= 0:
        return Valorisation(maintien, "maintien seul")
    dixieme = round(float(periode.base) * float(taux) * restants / droits, 2)
    if dixieme >= maintien:
        return Valorisation(dixieme, "dixième")
    return Valorisation(maintien, "maintien")


@dataclass(frozen=True)
class LigneProvision:
    matricule: str
    nom: str
    date_entree: str
    solde_n1: float
    solde_n: float
    solde_repos: float
    solde_jours: float
    valeur_jour: float
    primes_recurrentes: float
    base_n1: float | None
    base_n: float | None
    reconstitution: float
    provision_n1: float
    provision_n: float
    provision_repos: float
    methode: str
    provision: float
    taux_charges: float
    montant_charges: float
    total: float
    mois_retenus: str
    anomalie: str


def calculer_ligne(
    matricule: str,
    nom: str,
    date_entree: str,
    n1: PeriodeProvision,
    n: PeriodeProvision,
    *,
    valeur_jour: float,
    taux_charges: float,
    mois_retenus: str,
    solde_repos: float = 0.0,
    primes_recurrentes: float = 0.0,
    reconstitution: float = 0.0,
    anomalie: str = "",
) -> LigneProvision:
    """Une ligne de l'état, à partir de données déjà résolues (jours en ouvrés, valeur d'un
    jour au maintien en euros, taux de charges en pourcentage : 25.74, pas 0.2574)."""
    v_n1 = valoriser_periode(n1, valeur_jour=valeur_jour)
    v_n = valoriser_periode(n, valeur_jour=valeur_jour)
    provision_repos = round(max(float(solde_repos), 0.0) * valeur_jour, 2)
    morceaux = [
        f"{nom_periode} : {v.methode}"
        for nom_periode, v in (("N-1", v_n1), ("N", v_n))
        if v.methode != "rien"
    ]
    if provision_repos:
        morceaux.append("repos : maintien")
    provision = round(v_n1.montant + v_n.montant + provision_repos, 2)
    montant_charges = round(provision * taux_charges / 100, 2)
    return LigneProvision(
        matricule=matricule,
        nom=nom,
        date_entree=date_entree,
        solde_n1=round(n1.restants, 2),
        solde_n=round(n.restants, 2),
        solde_repos=round(solde_repos, 2),
        solde_jours=round(n1.restants + n.restants + solde_repos, 2),
        valeur_jour=round(valeur_jour, 2),
        primes_recurrentes=round(primes_recurrentes, 2),
        base_n1=None if n1.base is None else round(n1.base, 2),
        base_n=None if n.base is None else round(n.base, 2),
        reconstitution=round(reconstitution, 2),
        provision_n1=v_n1.montant,
        provision_n=v_n.montant,
        provision_repos=provision_repos,
        methode=" ; ".join(morceaux),
        provision=provision,
        taux_charges=round(taux_charges, 2),
        montant_charges=montant_charges,
        total=round(provision + montant_charges, 2),
        mois_retenus=mois_retenus,
        anomalie=anomalie,
    )


def calculer_totaux(lignes: list[LigneProvision]) -> dict[str, float]:
    """Ligne « Total » de l'état. Le taux est pondéré, jamais une moyenne de taux."""
    def somme(champ: str) -> float:
        return round(sum(getattr(l, champ) for l in lignes), 2)

    provision = somme("provision")
    montant_charges = somme("montant_charges")
    return {
        "solde_n1": somme("solde_n1"),
        "solde_n": somme("solde_n"),
        "solde_repos": somme("solde_repos"),
        "solde_jours": somme("solde_jours"),
        "reconstitution": somme("reconstitution"),
        "provision_n1": somme("provision_n1"),
        "provision_n": somme("provision_n"),
        "provision_repos": somme("provision_repos"),
        "taux_charges": round(montant_charges / provision * 100, 2) if provision else 0.0,
        "montant_charges": montant_charges,
        "provision": provision,
        "total": round(provision + montant_charges, 2),
    }


# --- Périodes et taux de charges --------------------------------------------------------------

def bornes_des_periodes(ref: date, mois_debut: int = 6) -> tuple[tuple[date, date], tuple[date, date]]:
    """((début, fin) de la période N-1, (début, fin) de la période N) à la date ref : la période
    N commence au `mois_debut` (juin par défaut) qui précède ou contient ref."""
    annee = ref.year if ref.month >= mois_debut else ref.year - 1
    debut_n = date(annee, mois_debut, 1)
    debut_n1 = date(annee - 1, mois_debut, 1)
    return (debut_n1, date.fromordinal(debut_n.toordinal() - 1)), (debut_n, ref)


def mois_entre(debut: date, fin: date) -> list[tuple[int, int]]:
    """Les (année, mois) de debut à fin inclus."""
    couples: list[tuple[int, int]] = []
    a, m = debut.year, debut.month
    while (a, m) <= (fin.year, fin.month):
        couples.append((a, m))
        a, m = (a, m + 1) if m < 12 else (a + 1, 1)
    return couples


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
    Le taux de charges de l'état en vient ; le salaire moyen ne sert plus que de repli à la
    valeur d'un jour quand la fiche n'a pas de salaire contractuel.
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
