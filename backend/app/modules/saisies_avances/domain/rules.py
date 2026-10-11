"""
Règles métier pures du domaine saisies et avances.

Aucune dépendance : pas de FastAPI, pas de DB, pas de services externes.
Comportement identique à services.saisies_avances_calculator pour les calculs purs.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Literal, Tuple

AdvanceType = Literal["avance_salaire", "acompte_salaire", "acompte_prime"]


# Constantes métier (alignées domain/enums.py et legacy)
MAX_ADVANCE_DAYS = 10
MAX_ADVANCE_NET_RATIO = Decimal("0.5")  # Plafond : 50 % du salaire net de référence

_CENTIME = Decimal("0.01")


def _centimes(valeur: Decimal) -> Decimal:
    return valeur.quantize(_CENTIME, rounding=ROUND_HALF_UP)


def _fraction(texte: Any) -> Decimal:
    """« 1/20 », « 2/3 », « 1 » ou 0.05 : la fraction saisissable d'une tranche."""
    brut = str(texte).strip()
    if "/" in brut:
        numerateur, denominateur = brut.split("/", 1)
        return Decimal(numerateur.strip()) / Decimal(denominateur.strip())
    return Decimal(brut)


def resoudre_bareme_quotite(
    config: Dict[str, Any] | None, annee: int, mois: int
) -> Tuple[Dict[str, Any] | None, List[str]]:
    """Le barème de la quotité saisissable pour le bulletin, et ce qu'il faut en dire.

    `config` est la ligne `payroll_config.quotite_saisissable` : un barème par
    année (`par_annee`, tranches annuelles et majoration par personne à charge,
    R3252-2 et R3252-3 du Code du travail) et l'historique du solde laissé au
    salarié (`solde_insaisissable`, le RSA d'une personne seule, revalorisé
    chaque 1er avril). Une année nouvelle s'y ajoute sans toucher au code.

    Sans barème pour l'année du bulletin, le plus récent des années d'avant sert,
    et le message le dit. Sans aucun barème : (None, [message]).
    """
    par_annee = (config or {}).get("par_annee") or {}
    annees = sorted(int(a) for a in par_annee if str(a).isdigit())
    if not annees:
        return None, [
            "Barème de la quotité saisissable absent (payroll_config, clé "
            "quotite_saisissable) : aucune saisie sur salaire n'est retenue sur ce "
            "bulletin. Contactez le support."
        ]
    messages: List[str] = []
    anterieures = [a for a in annees if a <= annee]
    retenue = anterieures[-1] if anterieures else annees[0]
    if retenue != annee:
        messages.append(
            f"Barème de la quotité saisissable {annee} non chargé : celui de "
            f"{retenue} est appliqué. Vérifiez la retenue avant de valider."
        )
    bloc = par_annee.get(str(retenue)) or par_annee.get(retenue) or {}
    jour = date(annee, mois, 1)
    solde = None
    for palier in sorted(
        (config or {}).get("solde_insaisissable") or [],
        key=lambda p: str(p.get("date_debut") or ""),
    ):
        debut = _jour(palier.get("date_debut"))
        if debut is not None and debut <= jour:
            solde = Decimal(str(palier.get("montant_mensuel")))
    if solde is None:
        return None, messages + [
            "Solde insaisissable (RSA d'une personne seule) introuvable pour ce mois "
            "dans le barème de la quotité saisissable : aucune saisie sur salaire "
            "n'est retenue sur ce bulletin. Contactez le support."
        ]
    return (
        {
            "annee": retenue,
            "tranches": [
                (
                    None
                    if t.get("jusqu_a_annuel") is None
                    else Decimal(str(t["jusqu_a_annuel"])),
                    _fraction(t.get("fraction")),
                )
                for t in bloc.get("tranches") or []
            ],
            "majoration_annuelle": Decimal(
                str(bloc.get("majoration_annuelle_par_personne_a_charge") or 0)
            ),
            "solde_insaisissable": solde,
        },
        messages,
    )


def calculate_seizable_amount(
    base: Decimal, dependents_count: int, bareme: Dict[str, Any]
) -> Decimal:
    """Quotité saisissable du mois, au barème légal (L3252-2, R3252-2, R3252-3).

    Chaque seuil annuel est relevé de la majoration par personne à charge, puis
    ramené au mois ; chaque tranche est prise à sa fraction et arrondie au
    centime, comme le simulateur justice.fr. Le salarié garde toujours le solde
    insaisissable (RSA d'une personne seule) : rien n'est saisissable en dessous.
    """
    if base <= 0:
        return Decimal("0")
    personnes = max(0, int(dependents_count or 0))
    majoration = bareme["majoration_annuelle"] * personnes
    total = Decimal("0")
    bas = Decimal("0")
    for plafond_annuel, fraction in bareme["tranches"]:
        haut = None if plafond_annuel is None else (plafond_annuel + majoration) / 12
        if base <= bas:
            break
        part = (base if haut is None else min(base, haut)) - bas
        total += _centimes(part * fraction)
        if haut is None:
            break
        bas = haut
    plafond = max(Decimal("0"), base - bareme["solde_insaisissable"])
    return _centimes(max(Decimal("0"), min(total, plafond)))


_MOTS_FRAIS = (
    "frais",
    "rembours",
    "panier",
    "repas",
    "transport",
    "trajet",
    "kilom",
    "déplacement",
    "deplacement",
)


def _est_un_remboursement_de_frais(prime: Dict[str, Any]) -> bool:
    # Marquée par le générateur : note de frais, panier, déplacement forfaitaire.
    if prime.get("frais_professionnels"):
        return True
    prime_id = str(prime.get("prime_id") or "")
    if prime_id.startswith("remb_"):
        return True
    texte = f"{prime_id} {prime.get('libelle') or ''}".lower()
    return any(mot in texte for mot in _MOTS_FRAIS)


def base_saisissable(bulletin: Dict[str, Any]) -> Decimal:
    """Ce sur quoi se calcule la quotité saisissable (L3252-3 du Code du travail).

    La rémunération, ses accessoires et les avantages en nature, après
    cotisations et prélèvement à la source, sans les remboursements de frais.
    On part du net à payer du moteur :
    - l'acompte retenu y est rajouté (c'est déjà du salaire) ; un ajout sur le
      net porté en acompte négatif (panier, déplacement, avance versée) en sort ;
    - l'avantage en nature, retiré du net à payer, y revient ;
    - le remboursement de transport et les notes de frais en sortent.
    """
    synthese = bulletin.get("synthese_net") or {}

    def _d(valeur: Any) -> Decimal:
        try:
            return Decimal(str(valeur or 0))
        except Exception:  # noqa: BLE001 — une valeur illisible ne compte pas
            return Decimal("0")

    base = _d(bulletin.get("net_a_payer"))
    base += _d(synthese.get("acompte_verse"))
    base += _d(synthese.get("avantages_en_nature"))
    base -= _d(synthese.get("remboursement_transport"))
    base -= _d(synthese.get("indemnite_transport_fixe"))
    for prime in bulletin.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        montant = _d(prime.get("montant"))
        if montant > 0 and _est_un_remboursement_de_frais(prime):
            base -= montant
    return _centimes(base)


def apply_priority_order(seizures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trie les saisies par ordre de priorité légal (priority puis start_date).
    """
    return sorted(
        seizures,
        key=lambda s: (s.get("priority", 4), s.get("start_date", date.min)),
    )


def calculate_seizure_deduction(
    seizure: Dict[str, Any],
    net_salary: Decimal,
    seizable_amount: Decimal,
    dependents_count: int = 0,
) -> Decimal:
    """
    Calcule le montant à prélever pour une saisie selon son mode (fixe, pourcentage, barème_legal).
    """
    calculation_mode = seizure.get("calculation_mode", "barème_legal")

    # Une saisie au barème n'a pas de montant : la colonne arrive à None, que
    # `Decimal(str(None))` refusait.
    if calculation_mode == "fixe":
        amount = Decimal(str(seizure.get("amount") or 0))
        return min(amount, seizable_amount)

    if calculation_mode == "pourcentage":
        percentage = Decimal(str(seizure.get("percentage") or 0))
        amount = net_salary * (percentage / Decimal("100"))
        return min(amount, seizable_amount)

    # barème_legal
    amount = Decimal(str(seizure.get("amount") or 0))
    if amount > 0:
        return min(amount, seizable_amount)
    return seizable_amount


def _jour(valeur: Any) -> date | None:
    """Une date de la base (« 2026-10-06 », horodatage ou `date`), ou None."""
    if valeur is None:
        return None
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur).strip()[:10]
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


def date_de_versement_de_l_avance(
    advance: Dict[str, Any], premier_versement: Any = None
) -> date | None:
    """Le jour où l'avance a été versée au salarié.

    Le premier versement enregistré (avec sa preuve) d'abord, puis la date de
    versement de l'avance, puis la date de la demande.
    """
    for valeur in (
        premier_versement,
        advance.get("payment_date"),
        advance.get("requested_date"),
    ):
        jour = _jour(valeur)
        if jour is not None:
            return jour
    return None


def avance_retenable_sur_le_mois(
    advance: Dict[str, Any], annee: int, mois: int, premier_versement: Any = None
) -> bool:
    """Une avance se retient sur le bulletin du mois de son versement ou d'après.

    Une avance versée en octobre ne peut pas être retenue sur septembre, ni sur
    une reprise de janvier (enquête du 11/10/2026, [G7]). Sans aucune date, on
    garde l'ancienne conduite : retenable.
    """
    versement = date_de_versement_de_l_avance(advance, premier_versement)
    if versement is None:
        return True
    return (versement.year, versement.month) <= (annee, mois)


def compute_max_advance_from_net(reference_net_salary: Decimal) -> Decimal:
    """Plafond légal interne : 50 % du salaire net de référence."""
    return reference_net_salary * MAX_ADVANCE_NET_RATIO


def is_employee_right(advance_type: AdvanceType) -> bool:
    """L'acompte sur salaire (travail déjà effectué) est un droit du salarié mensualisé."""
    return advance_type == "acompte_salaire"


def compute_prime_solde(
    prime_final_amount: Decimal, total_acompte_verse: Decimal
) -> Decimal:
    """Solde net à payer après déduction de l'acompte sur prime déjà versé."""
    return max(Decimal("0"), prime_final_amount - total_acompte_verse)


def compute_available_by_advance_type(
    advance_type: AdvanceType,
    daily_salary: Decimal,
    days_worked: Decimal,
    total_outstanding: Decimal,
    reference_net_salary: Decimal = Decimal("0"),
    max_advance_days: int = MAX_ADVANCE_DAYS,
) -> Tuple[Decimal, Decimal]:
    """
    Montant disponible selon la nature de la demande.
    Retourne (available_amount, max_advance_amount_cap).
    """
    max_from_net = compute_max_advance_from_net(reference_net_salary)
    net_cap_remaining = max(Decimal("0"), max_from_net - total_outstanding)

    if advance_type == "acompte_salaire":
        return compute_advance_available_from_figures(
            daily_salary,
            days_worked,
            total_outstanding,
            max_advance_days,
            reference_net_salary,
        )

    if advance_type == "avance_salaire":
        available = net_cap_remaining
        return available, max_from_net

    # acompte_prime : pas de plafond automatique (montant libre RH)
    return Decimal("999999999"), Decimal("999999999")


def advance_type_label(advance_type: str, prime_label: str | None = None) -> str:
    """Libellé affichage bulletin / UI."""
    labels = {
        "avance_salaire": "Avance sur salaire",
        "acompte_salaire": "Acompte sur salaire",
        "acompte_prime": "Acompte sur prime",
    }
    base = labels.get(advance_type, "Avance")
    if advance_type == "acompte_prime" and prime_label:
        return f"{base} ({prime_label})"
    return base


def seizure_type_label(seizure_type: str) -> str:
    """Libellé affichage saisie sur salaire."""
    labels = {
        "saisie_arret": "Saisie sur salaire (arrêt)",
        "pension_alimentaire": "Pension alimentaire",
        "atd": "ATD (Avis à tiers détenteur)",
        "satd": "SATD (Avis simplifié à tiers détenteur)",
    }
    return labels.get(seizure_type, "Saisie sur salaire")


def compute_advance_available_from_figures(
    daily_salary: Decimal,
    days_worked: Decimal,
    total_outstanding: Decimal,
    max_advance_days: int = MAX_ADVANCE_DAYS,
    reference_net_salary: Decimal = Decimal("0"),
) -> Tuple[Decimal, Decimal]:
    """
    À partir des données déjà récupérées, calcule le montant disponible pour une avance.
    Retourne (available_amount, max_advance_amount_cap).
    """
    gross_available = daily_salary * days_worked
    available_amount = max(Decimal("0"), gross_available - total_outstanding)
    max_advance_amount = daily_salary * Decimal(str(max_advance_days))
    available_amount = min(available_amount, max_advance_amount)

    if reference_net_salary > 0:
        max_from_net = compute_max_advance_from_net(reference_net_salary)
        net_cap_remaining = max(Decimal("0"), max_from_net - total_outstanding)
        available_amount = min(available_amount, net_cap_remaining)

    return available_amount, max_advance_amount


def initial_advance_status(is_employee_request: bool) -> str:
    """
    Détermine le statut initial d'une demande d'avance.
    - Employé qui demande pour lui-même : toujours 'pending'
    - RH/Admin : 'approved' — la saisie enregistre un accord déjà donné ;
      les plafonds contrôlés à la création font office de garde-fou.
    """
    return "pending" if is_employee_request else "approved"


def remaining_to_pay_value(approved_amount: Decimal, total_paid: Decimal) -> float:
    """
    Montant restant à verser à l'employé (pour affichage).
    """
    remaining = approved_amount - total_paid
    if approved_amount > 0 and total_paid >= approved_amount:
        return 0.0
    if approved_amount > 0:
        return float(max(Decimal("0"), remaining))
    return 0.0
