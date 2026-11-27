"""Ce que le bulletin et « Primes du mois » disent des paniers générés (L19, 27/11).

- Jours travaillés sans heure d'arrivée que la règle « par jour travaillé » ne
  compte pas : relus au calendrier, par la règle elle-même (génération des
  variables en simulation, sans rien écrire), à chaque bulletin et à chaque
  ouverture de l'écran. Rien n'est stocké : une heure d'arrivée corrigée ou une
  absence posée éteint l'alerte, et l'alerte reste vraie quand le panier du
  mois tombe à 0. (La première version écrivait la remarque dans la
  description de la saisie, que la détection des heures sup lit : relecture du
  27/11.)
- Panier généré dont le montant a été changé à la main sans changer le nombre :
  la part réintégrée reste calculée sur le nombre ; le bulletin le dit.

Alertes non bloquantes.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.core.logging import get_logger
from app.modules.monthly_inputs.domain.rules import (
    PREFIXE_SAISIE_GENEREE,
    est_saisie_generee,
    est_saisie_retiree,
)

logger = get_logger("modules.payroll_variables.alertes_paniers")

CODE_ALERTE_JOURS_SANS_HEURE_D_ARRIVEE = "jours_sans_heure_d_arrivee"
CODE_ALERTE_PANIER_MONTANT_SANS_NOMBRE = "panier_montant_sans_nombre"
CODE_ALERTE_JOURS_NON_VERIFIES = "jours_sans_heure_d_arrivee_non_verifies"

#: Les règles dont le nombre de jours se lit au calendrier.
TYPES_PAR_JOUR_TRAVAILLE = ("per_worked_day",)
#: Les règles dont le montant est nombre × montant de la règle.
TYPES_NOMBRE_FOIS_MONTANT = ("per_worked_day", "per_shift_type")


def _jour_mois(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _euros(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",")


def _nombre(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


def jours_sans_heure_d_arrivee(
    company_id: str, year: int, month: int, employee_id: str | None = None
) -> list[dict[str, Any]]:
    """Par salarié et par règle, les jours travaillés sans heure d'arrivée que
    la règle ne compte pas. Lecture seule (génération en simulation)."""
    from app.modules.payroll_variables.application.generate_monthly import (
        generate_monthly_variables,
    )

    res = generate_monthly_variables(
        str(company_id),
        year,
        month,
        dry_run=True,
        employee_id=employee_id,
        types_de_regle=TYPES_PAR_JOUR_TRAVAILLE,
    )
    sortie: list[dict[str, Any]] = []
    for item in res.get("preview") or []:
        details = item.get("details") or {}
        dates = details.get("dates_sans_heure_de_debut") or []
        if dates:
            sortie.append(
                {
                    "employee_id": str(item.get("employee_id")),
                    "first_name": item.get("first_name"),
                    "last_name": item.get("last_name"),
                    "rule_label": item.get("rule_label") or item.get("rule_code"),
                    "dates": list(dates),
                    # Aucun jour de la fenêtre n'a d'heure d'arrivée (aucun
                    # badge importé) : une seule phrase, sans les dates.
                    "aucun_badge": bool(details.get("aucun_badge")),
                }
            )
    return sortie


def phrase_aucune_heure_d_arrivee(regle: Any, nombre: int) -> str:
    """Aucun badge du mois : une phrase par salarié et par règle, sans dates."""
    jours = "jour travaillé" if nombre == 1 else "jours travaillés"
    rien = "aucun panier compté" if "panier" in str(regle).lower() else "aucun jour compté"
    return (
        f"{regle} : aucune heure d'arrivée sur la période ({nombre} {jours}), {rien} : "
        "importez les pointages ou saisissez les heures d'arrivée au calendrier."
    )


def phrase_jours_sans_heure_d_arrivee(regle: Any, dates: list[str], aucun_badge: bool = False) -> str:
    if aucun_badge:
        return phrase_aucune_heure_d_arrivee(regle, len(dates))
    n = len(dates)
    jours = "jour travaillé" if n == 1 else "jours travaillés"
    comptes = "non compté" if n == 1 else "non comptés"
    liste = ", ".join(_jour_mois(d) for d in dates)
    return (
        f"{regle} : {n} {jours} sans heure d'arrivée, {comptes} ({liste}) : "
        "heure d'arrivée à saisir au calendrier, ou absence à poser."
    )


def _code_de_la_saisie(saisie: Mapping[str, Any]) -> str:
    return str(saisie.get("description") or "")[len(PREFIXE_SAISIE_GENEREE):].strip()


def alertes_de_montant_sans_le_nombre(
    saisies: Iterable[Mapping[str, Any]], regles: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Un panier généré dont le montant n'est plus nombre × montant de la règle."""
    par_code = {
        str(r.get("code") or "").strip(): r
        for r in regles
        if r.get("rule_type") in TYPES_NOMBRE_FOIS_MONTANT
        and r.get("amount") is not None
        and not (r.get("conditions") or {}).get("heures_par_jour")
    }
    alertes: list[dict[str, Any]] = []
    for saisie in saisies:
        if not isinstance(saisie, Mapping) or not est_saisie_generee(saisie) or est_saisie_retiree(saisie):
            continue
        nom = str(saisie.get("name") or "")
        if "panier" not in nom.lower() and "repas" not in nom.lower():
            continue
        regle = par_code.get(_code_de_la_saisie(saisie))
        try:
            nombre = float(saisie.get("payroll_quantity"))
            montant = round(float(saisie.get("amount") or 0.0), 2)
            unitaire = float(regle["amount"]) if regle else None
        except (TypeError, ValueError):
            continue
        if unitaire is None or montant <= 0 or nombre <= 0:
            continue
        if abs(round(nombre * unitaire, 2) - montant) < 0.005:
            continue
        alertes.append(
            {
                "code": CODE_ALERTE_PANIER_MONTANT_SANS_NOMBRE,
                "critique": False,
                "severity": "warning",
                "message": (
                    f"{nom} : montant modifié à la main ({_euros(montant)} €) sans changer le nombre "
                    f"de paniers ({_nombre(nombre)}) : la part réintégrée est calculée sur "
                    f"{_nombre(nombre)} paniers ; corrigez le nombre dans Primes du mois"
                ),
            }
        )
    return alertes


def alertes_des_paniers_du_mois(
    company_id: str, employee_id: str, year: int, month: int, saisies: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Les alertes de paniers du bulletin, aux deux générateurs. Une lecture qui
    échoue est dite, jamais tue."""
    # Le dépôt de la génération : celui qu'elle lit (et que les tests remplacent).
    from app.modules.payroll_variables.application import generate_monthly as gm

    try:
        regles = [r for r in gm.repo.list_rules(str(company_id)) if r.get("enabled")]
    except Exception as exc:  # noqa: BLE001 — dit sur le bulletin
        logger.warning("Règles de variables illisibles pour les alertes de paniers : %s", exc)
        return [_alerte_non_verifiee()]
    alertes: list[dict[str, Any]] = []
    if any(
        r.get("rule_type") in TYPES_PAR_JOUR_TRAVAILLE and (r.get("conditions") or {}).get("plages_debut")
        for r in regles
    ):
        try:
            jours = jours_sans_heure_d_arrivee(company_id, year, month, employee_id)
        except Exception as exc:  # noqa: BLE001 — dit sur le bulletin
            logger.warning("Jours sans heure d'arrivée non relus : %s", exc)
            jours = None
            alertes.append(_alerte_non_verifiee())
        for j in jours or []:
            alertes.append(
                {
                    "code": CODE_ALERTE_JOURS_SANS_HEURE_D_ARRIVEE,
                    "critique": False,
                    "severity": "warning",
                    "message": phrase_jours_sans_heure_d_arrivee(
                        j["rule_label"], j["dates"], j.get("aucun_badge", False)
                    ),
                }
            )
    alertes.extend(alertes_de_montant_sans_le_nombre(saisies or [], regles))
    return alertes


def _alerte_non_verifiee() -> dict[str, Any]:
    return {
        "code": CODE_ALERTE_JOURS_NON_VERIFIES,
        "critique": False,
        "severity": "warning",
        "message": (
            "Paniers : les jours travaillés sans heure d'arrivée n'ont pas pu être relus au "
            "calendrier ; vérifiez-les dans Primes du mois."
        ),
    }
