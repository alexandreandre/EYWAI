"""Ce que le bulletin et « Primes du mois » disent des paniers générés (L19, 27/11).

- Jours travaillés sans heure d'arrivée que la règle « par jour travaillé » ne
  compte pas : relus au calendrier, par la règle elle-même (génération des
  variables en simulation, sans rien écrire), à chaque bulletin et à chaque
  ouverture de l'écran. Rien n'est stocké : une heure d'arrivée corrigée ou une
  absence posée éteint l'alerte, et l'alerte reste vraie quand le panier du
  mois tombe à 0. (La première version écrivait la remarque dans la
  description de la saisie, que la détection des heures sup lit : relecture du
  27/11.)
- Les mêmes jours relevés par plusieurs règles (panier de jour, panier de
  nuit, prime de nuit) : dits une fois par salarié, avec les règles nommées ;
  une phrase par groupe de jours identiques (L23, 28/11).
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


def regrouper_jours_sans_heure_d_arrivee(lignes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Une ligne par salarié et par groupe de jours identiques, qui nomme les
    règles concernées (dans l'ordre reçu, sans doublon). Les jours ne changent
    pas : seule la façon de les dire change (L23, 28/11)."""
    groupes: dict[tuple[str, tuple[str, ...], bool], dict[str, Any]] = {}
    for ligne in lignes:
        cle = (str(ligne.get("employee_id")), tuple(ligne.get("dates") or []), bool(ligne.get("aucun_badge")))
        groupe = groupes.get(cle)
        if groupe is None:
            groupe = groupes[cle] = {
                "employee_id": cle[0],
                "first_name": ligne.get("first_name"),
                "last_name": ligne.get("last_name"),
                "rule_labels": [],
                "dates": list(cle[1]),
                "aucun_badge": cle[2],
            }
        regle = ligne.get("rule_label")
        if regle and regle not in groupe["rule_labels"]:
            groupe["rule_labels"].append(regle)
    return [
        {**g, "rule_label": ", ".join(g["rule_labels"]) or None}
        for g in groupes.values()
    ]


def _regles(regles: Any) -> list[str]:
    if isinstance(regles, (list, tuple)):
        return [str(r) for r in regles if r] or ["Prime"]
    return [str(regles or "Prime")]


def phrase_aucune_heure_d_arrivee(regles: Any, nombre: int) -> str:
    """Aucun badge du mois : une phrase par salarié, qui nomme les règles, sans dates."""
    noms = _regles(regles)
    jours = "jour travaillé" if nombre == 1 else "jours travaillés"
    tout_panier = all("panier" in n.lower() for n in noms)
    rien = "aucun panier compté" if tout_panier else "aucun jour compté"
    return (
        f"{', '.join(noms)} : aucune heure d'arrivée sur la période ({nombre} {jours}), {rien} : "
        "importez les pointages ou saisissez les heures d'arrivée au calendrier."
    )


def phrase_jours_sans_heure_d_arrivee(regles: Any, dates: list[str], aucun_badge: bool = False) -> str:
    """Les jours d'un groupe, avec les règles qui ne les comptent pas."""
    if aucun_badge:
        return phrase_aucune_heure_d_arrivee(regles, len(dates))
    n = len(dates)
    jours = "jour travaillé" if n == 1 else "jours travaillés"
    ces_jours = "ce jour-là" if n == 1 else "ces jours-là"
    liste = ", ".join(_jour_mois(d) for d in dates)
    return (
        f"{', '.join(_regles(regles))} : {n} {jours} sans heure d'arrivée ({liste}) : "
        f"aucun compté {ces_jours}. Importez les pointages ou saisissez l'heure d'arrivée au calendrier."
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
        and not _conditions(r).get("heures_par_jour")
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
        # Neutre : le montant ou le nombre a pu changer seul (relecture du 27/11).
        alertes.append(
            {
                "code": CODE_ALERTE_PANIER_MONTANT_SANS_NOMBRE,
                "critique": False,
                "severity": "warning",
                "message": (
                    f"{nom} : {_euros(montant)} € pour {_nombre(nombre)} "
                    f"{'panier' if nombre == 1 else 'paniers'} à {_euros(unitaire)} € : "
                    "le montant et le nombre ne correspondent pas."
                ),
            }
        )
    return alertes


def _conditions(regle: Mapping[str, Any]) -> Mapping[str, Any]:
    conditions = regle.get("conditions")
    return conditions if isinstance(conditions, Mapping) else {}


def alertes_des_paniers_du_mois(
    company_id: str, employee_id: str, year: int, month: int, saisies: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Les alertes de paniers du bulletin, aux deux générateurs. Une lecture qui
    échoue est dite, jamais tue ; rien ici n'arrête le bulletin."""
    try:
        return _alertes_des_paniers_du_mois(company_id, employee_id, year, month, saisies)
    except Exception as exc:  # noqa: BLE001 — dit sur le bulletin
        logger.warning("Alertes de paniers non calculées : %s", exc)
        return [alerte_paniers_non_verifiee()]


def _alertes_des_paniers_du_mois(
    company_id: str, employee_id: str, year: int, month: int, saisies: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    # Le dépôt de la génération : celui qu'elle lit (et que les tests remplacent).
    from app.modules.payroll_variables.application import generate_monthly as gm

    try:
        regles = [r for r in gm.repo.list_rules(str(company_id)) if r.get("enabled")]
    except Exception as exc:  # noqa: BLE001 — dit sur le bulletin
        logger.warning("Règles de variables illisibles pour les alertes de paniers : %s", exc)
        return [alerte_paniers_non_verifiee()]
    alertes: list[dict[str, Any]] = []
    if any(
        r.get("rule_type") in TYPES_PAR_JOUR_TRAVAILLE
        and r.get("conditions") is not None
        and not isinstance(r.get("conditions"), Mapping)
        for r in regles
    ):
        # Conditions illisibles : on ne sait pas si la règle lit l'heure d'arrivée.
        alertes.append(alerte_paniers_non_verifiee())
    if any(
        r.get("rule_type") in TYPES_PAR_JOUR_TRAVAILLE and _conditions(r).get("plages_debut")
        for r in regles
    ):
        try:
            jours = jours_sans_heure_d_arrivee(company_id, year, month, employee_id)
        except Exception as exc:  # noqa: BLE001 — dit sur le bulletin
            logger.warning("Jours sans heure d'arrivée non relus : %s", exc)
            jours = None
            alertes.append(alerte_paniers_non_verifiee())
        for g in regrouper_jours_sans_heure_d_arrivee(jours or []):
            alertes.append(
                {
                    "code": CODE_ALERTE_JOURS_SANS_HEURE_D_ARRIVEE,
                    "critique": False,
                    "severity": "warning",
                    "message": phrase_jours_sans_heure_d_arrivee(
                        g["rule_labels"], g["dates"], g["aucun_badge"]
                    ),
                }
            )
    alertes.extend(alertes_de_montant_sans_le_nombre(saisies or [], regles))
    return alertes


def alerte_paniers_non_verifiee() -> dict[str, Any]:
    """Les jours sans heure d'arrivée n'ont pas pu être relus : dit, jamais tu."""
    return {
        "code": CODE_ALERTE_JOURS_NON_VERIFIES,
        "critique": False,
        "severity": "warning",
        "message": (
            "Paniers : les jours travaillés sans heure d'arrivée n'ont pas pu être relus au "
            "calendrier ; vérifiez-les dans Primes du mois."
        ),
    }
