"""
Règles métier pures du domaine monthly_inputs.

Aucune dépendance FastAPI, DB ou infrastructure. Utilisables par l'application si besoin.
Comportement actuel des routeurs inchangé (validation Pydantic côté API).
"""


def is_valid_period(year: int, month: int) -> bool:
    """Période (année, mois) valide pour une saisie mensuelle. Règle pure, sans I/O."""
    return (
        isinstance(year, int)
        and isinstance(month, int)
        and 1 <= month <= 12
        and year > 0
    )


#: Début de la description des saisies écrites par la génération automatique
#: des variables (`payroll_variables.application.generate_monthly`).
PREFIXE_SAISIE_GENEREE = "Auto:"

#: Ce que devient une saisie générée qu'on retire : supprimée, la génération
#: suivante la recréerait ; à 0 et protégée, elle n'y revient pas.
RETRAIT_SAISIE_GENEREE = {"amount": 0, "manual_override": True}


def est_saisie_generee(saisie: dict) -> bool:
    """Saisie écrite par une règle automatique de la société."""
    return str(saisie.get("description") or "").startswith(PREFIXE_SAISIE_GENEREE)


def est_saisie_retiree(saisie: dict) -> bool:
    """Saisie générée que la RH a retirée (à 0, protégée) : pas une ligne du bulletin."""
    return (
        est_saisie_generee(saisie)
        and bool(saisie.get("manual_override"))
        and float(saisie.get("amount") or 0) == 0
    )


CODE_ALERTE_DOUBLON_PRIME = "doublon_prime_regle_auto"
CODE_ALERTE_JOURS_SANS_HEURE_D_ARRIVEE = "jours_sans_heure_d_arrivee"

#: Entre « Auto: <code> » et la remarque que la génération laisse sur la saisie.
SEPARATEUR_REMARQUE = " — "


def description_de_saisie_generee(code: object, remarque: str | None = None) -> str:
    """« Auto: PANIER », ou « Auto: PANIER — <remarque> » quand la génération a
    quelque chose à dire (jours non comptés, L19 du 26/11)."""
    base = f"{PREFIXE_SAISIE_GENEREE} {code}"
    return f"{base}{SEPARATEUR_REMARQUE}{remarque}" if remarque else base


def remarque_de_saisie_generee(saisie: dict) -> str | None:
    """La remarque laissée par la génération sur une saisie générée, ou None."""
    if not est_saisie_generee(saisie):
        return None
    _, sep, remarque = str(saisie.get("description") or "").partition(SEPARATEUR_REMARQUE)
    return remarque.strip() or None if sep else None


def remarque_jours_sans_heure_d_arrivee(dates: list[str], libelle: object) -> str | None:
    """« 2 jours travaillés sans heure d'arrivée, non comptés pour « Panier » :
    05/10, 06/10 », ou None sans jour."""
    if not dates:
        return None
    n = len(dates)
    jours = "jour travaillé" if n == 1 else "jours travaillés"
    comptes = "non compté" if n == 1 else "non comptés"
    liste = ", ".join(f"{d[8:10]}/{d[5:7]}" for d in dates)
    return f"{n} {jours} sans heure d'arrivée, {comptes} pour « {libelle} » : {liste}"


def alertes_de_jours_sans_heure_d_arrivee(saisies: list[dict]) -> list[dict]:
    """Une prime par jour travaillé (panier) versée au mois, mais sans les jours
    travaillés dont l'heure d'arrivée manque : la génération le note sur la
    saisie, le bulletin le dit (L19, 26/11 : rien ne le montrait quand le
    panier du mois restait positif)."""
    alertes: list[dict] = []
    for saisie in saisies:
        if est_saisie_retiree(saisie):
            continue
        remarque = remarque_de_saisie_generee(saisie)
        if not remarque or "sans heure d'arrivée" not in remarque:
            continue
        alertes.append(
            {
                "code": CODE_ALERTE_JOURS_SANS_HEURE_D_ARRIVEE,
                "critique": False,
                "severity": "warning",
                "message": (
                    f"{remarque}. Corrigez l'heure d'arrivée au calendrier (ou posez "
                    "l'absence), puis relancez les variables du mois ; sinon, ajustez "
                    "la saisie dans « Primes du mois »."
                ),
            }
        )
    return alertes


def _montant(saisie: dict) -> float:
    try:
        return round(float(saisie.get("amount") or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _euros(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",")


def alertes_de_doublon_de_prime(saisies: list[dict]) -> list[dict]:
    """Une prime saisie à la main au même montant qu'une prime de règle automatique.

    Le même libellé est déjà géré par la génération des variables (saisie protégée) :
    seul un libellé différent passe, et les deux lignes s'ajoutent au bulletin.
    Une alerte, jamais un retrait : les deux primes peuvent être dues.
    """
    automatiques = [s for s in saisies if est_saisie_generee(s) and not est_saisie_retiree(s) and _montant(s) > 0]
    manuelles = [
        s for s in saisies if not est_saisie_generee(s) and not s.get("correction_ligne") and _montant(s) > 0
    ]
    alertes: list[dict] = []
    for auto in automatiques:
        for manuelle in manuelles:
            if _montant(auto) != _montant(manuelle) or manuelle.get("name") == auto.get("name"):
                continue
            alertes.append(
                {
                    "code": CODE_ALERTE_DOUBLON_PRIME,
                    "critique": False,
                    "severity": "warning",
                    "message": (
                        f"« {manuelle.get('name')} » ({_euros(_montant(manuelle))} €), saisie à la main, "
                        f"a le même montant que « {auto.get('name')} », versée par une règle automatique : "
                        "si c'est la même prime, elle est payée deux fois. Retirez la saisie à la main "
                        "dans « Primes du mois » ; sinon, ignorez cette alerte."
                    ),
                }
            )
    return alertes
